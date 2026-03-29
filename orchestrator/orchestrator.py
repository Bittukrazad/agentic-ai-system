"""orchestrator/orchestrator.py — Main workflow controller"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from orchestrator.state_manager import WorkflowState, StateManager
from orchestrator.workflow_engine import WorkflowEngine
from orchestrator.exception_handler import ExceptionHandler, StepSkipped
from orchestrator.sla_manager import SLAManager
from agents.data_agent import DataAgent
from agents.decision_agent import DecisionAgent
from agents.action_agent import ActionAgent
from agents.verification_agent import VerificationAgent
from agents.monitoring_agent import MonitoringAgent
from agents.communication_agent import CommunicationAgent
from meeting_intelligence.transcript_parser import TranscriptParser
from meeting_intelligence.decision_extractor import DecisionExtractor
from meeting_intelligence.task_generator import TaskGenerator
from meeting_intelligence.owner_assigner import OwnerAssigner
from meeting_intelligence.progress_tracker import ProgressTracker
from meeting_intelligence.escalation_manager import EscalationManager
from audit.audit_logger import AuditLogger
from communication.event_bus import EventBus
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()


class Orchestrator:
    """
    The brain of the system.
    - Selects workflow type and loads step definitions
    - Dispatches each step to the right agent
    - Manages state, SLA clock, and exception recovery
    """

    def __init__(self):
        self.engine = WorkflowEngine()
        self.data_agent = DataAgent()
        self.decision_agent = DecisionAgent()
        self.action_agent = ActionAgent()
        self.verification_agent = VerificationAgent()
        self.monitoring_agent = MonitoringAgent()
        self.comm_agent = CommunicationAgent()

    async def run_workflow(self, workflow_id: str, workflow_type: str, payload: dict, priority: str = "normal"):
        """Entry point for any workflow execution"""
        logger.info(f"=== Workflow START | id={workflow_id} | type={workflow_type} ===")

        state = WorkflowState(workflow_id, workflow_type, payload, priority)
        StateManager.save(state)

        sla = SLAManager(workflow_id, workflow_type)
        audit.log(
            agent_id="orchestrator",
            action="WORKFLOW_STARTED",
            workflow_id=workflow_id,
            step_name="init",
            input_summary=f"type={workflow_type} priority={priority}",
            output_summary=f"SLA deadline: {sla.deadline.isoformat()}",
            confidence=1.0,
        )

        # Load steps
        if workflow_type == "meeting":
            await self._run_meeting_workflow(state, sla)
        else:
            await self._run_enterprise_workflow(state, sla)

        state.status = "completed"
        StateManager.save(state)
        audit.log(
            agent_id="orchestrator",
            action="WORKFLOW_COMPLETED",
            workflow_id=workflow_id,
            step_name="done",
            output_summary=f"completed_steps={len(state.completed_steps)} tasks={len(state.tasks)}",
            confidence=1.0,
        )
        logger.info(f"=== Workflow DONE | id={workflow_id} ===")
        EventBus.publish("workflow_completed", {"workflow_id": workflow_id, "type": workflow_type})

    # ── Meeting Workflow ─────────────────────────────────────────────────
    async def _run_meeting_workflow(self, state: WorkflowState, sla: SLAManager):
        wid = state.workflow_id
        transcript = state.payload.get("transcript", "")

        steps = [
            ("parse_transcript",   self._step_parse_transcript),
            ("extract_decisions",  self._step_extract_decisions),
            ("generate_tasks",     self._step_generate_tasks),
            ("assign_owners",      self._step_assign_owners),
            ("notify_owners",      self._step_notify_owners),
            ("track_progress",     self._step_track_progress),
        ]

        for step_id, step_fn in steps:
            state.current_step = step_id
            StateManager.save(state)

            if sla.remaining_minutes() < 5:
                sla.log_warning()

            exc_handler = ExceptionHandler(state)
            try:
                await step_fn(state, exc_handler)
                state.mark_step_complete(step_id)
                StateManager.save(state)
                audit.log(
                    agent_id="orchestrator",
                    action="STEP_COMPLETE",
                    workflow_id=wid,
                    step_name=step_id,
                    output_summary=f"tasks_so_far={len(state.tasks)}",
                    confidence=1.0,
                )
            except StepSkipped as e:
                logger.warning(f"Step skipped: {step_id} | {e}")
                audit.log(
                    agent_id="orchestrator",
                    action="STEP_SKIPPED",
                    workflow_id=wid,
                    step_name=step_id,
                    output_summary=str(e),
                    confidence=0.0,
                )

    async def _step_parse_transcript(self, state: WorkflowState, exc: ExceptionHandler):
        parser = TranscriptParser()
        async def run(enriched=False):
            return parser.parse(state.payload.get("transcript", ""))
        try:
            result = await run()
            state.fetched_data["parsed_transcript"] = result
        except Exception as e:
            await exc.handle("parse_transcript", str(e), run)

    async def _step_extract_decisions(self, state: WorkflowState, exc: ExceptionHandler):
        extractor = DecisionExtractor()
        async def run(enriched=False):
            context = state.fetched_data.get("parsed_transcript", {})
            return await extractor.extract(context, enriched=enriched)
        try:
            result = await run()
            state.fetched_data["extracted"] = result
            for d in result.get("decisions", []):
                state.add_decision(d)
        except Exception as e:
            result = await exc.handle("extract_decisions", str(e), run)
            if result:
                state.fetched_data["extracted"] = result

    async def _step_generate_tasks(self, state: WorkflowState, exc: ExceptionHandler):
        generator = TaskGenerator()
        async def run(enriched=False):
            extracted = state.fetched_data.get("extracted", {})
            return generator.generate(extracted)
        try:
            tasks = await run()
            for task in tasks:
                state.add_task(task)
        except Exception as e:
            await exc.handle("generate_tasks", str(e), run)

    async def _step_assign_owners(self, state: WorkflowState, exc: ExceptionHandler):
        assigner = OwnerAssigner()
        async def run(enriched=False):
            return assigner.assign(state.tasks)
        try:
            state.tasks = await run()
        except Exception as e:
            await exc.handle("assign_owners", str(e), run)

    async def _step_notify_owners(self, state: WorkflowState, exc: ExceptionHandler):
        async def run(enriched=False):
            for task in state.tasks:
                await self.action_agent.notify_task_owner(task, state.workflow_id)
                state.add_action({"type": "notification", "task_id": task.get("id"), "owner": task.get("owner")})
            return True
        try:
            await run()
        except Exception as e:
            await exc.handle("notify_owners", str(e), run)

    async def _step_track_progress(self, state: WorkflowState, exc: ExceptionHandler):
        tracker = ProgressTracker()
        tracker.register_tasks(state.workflow_id, state.tasks)
        escalator = EscalationManager()
        stalled = tracker.get_stalled()
        for task in stalled:
            await escalator.escalate(task, state.workflow_id)
        logger.info(f"Progress tracking set up | workflow={state.workflow_id} | tasks={len(state.tasks)}")

    # ── Enterprise Workflow ──────────────────────────────────────────────
    async def _run_enterprise_workflow(self, state: WorkflowState, sla: SLAManager):
        wid = state.workflow_id
        steps = self.engine.get_steps(state.workflow_type)

        if not steps:
            logger.warning(f"No steps found for workflow type: {state.workflow_type}")
            return

        for step in steps:
            step_id = self.engine.get_step_id(step)
            step_name = self.engine.get_step_name(step)
            agent_name = self.engine.get_step_agent(step)

            state.current_step = step_id
            StateManager.save(state)

            if sla.remaining_minutes() < 10:
                sla.log_warning()

            exc_handler = ExceptionHandler(state)
            try:
                result = await self._dispatch_agent(agent_name, step, state, exc_handler)
                state.mark_step_complete(step_id)
                if result:
                    state.outputs[step_id] = result
                StateManager.save(state)
                audit.log(
                    agent_id="orchestrator",
                    action="STEP_COMPLETE",
                    workflow_id=wid,
                    step_name=step_id,
                    output_summary=str(result)[:120] if result else "ok",
                    confidence=1.0,
                )
            except StepSkipped as e:
                if self.engine.is_critical(step):
                    state.status = "failed"
                    StateManager.save(state)
                    logger.error(f"Critical step skipped — aborting | {step_id}")
                    return
                logger.warning(f"Non-critical step skipped: {step_id}")

    async def _dispatch_agent(self, agent_name: str, step: dict, state: WorkflowState, exc: ExceptionHandler):
        """Route a step to the correct specialist agent"""
        params = step.get("params", {})

        if agent_name == "data_agent":
            async def run(enriched=False):
                return await self.data_agent.fetch(step.get("source", ""), params, state)
            try:
                return await run()
            except Exception as e:
                return await exc.handle(step["id"], str(e), run)

        elif agent_name == "decision_agent":
            async def run(enriched=False):
                return await self.decision_agent.decide(step.get("prompt_key", ""), state, enriched=enriched)
            try:
                result = await run()
                # Verify output
                verified = await self.verification_agent.verify(result, state)
                if not verified["passed"]:
                    raise ValueError(f"Verification failed: score={verified['score']:.2f}")
                state.add_decision(result)
                return result
            except Exception as e:
                return await exc.handle(step["id"], str(e), run)

        elif agent_name == "action_agent":
            async def run(enriched=False):
                return await self.action_agent.execute(step.get("action_type", ""), params, state)
            try:
                result = await run()
                state.add_action({"step": step["id"], "result": str(result)[:80]})
                return result
            except Exception as e:
                return await exc.handle(step["id"], str(e), run)

        elif agent_name == "communication_agent":
            return await self.comm_agent.coordinate(step, state)

        else:
            logger.warning(f"Unknown agent: {agent_name}")
            return None