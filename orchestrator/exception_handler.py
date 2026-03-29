"""orchestrator/exception_handler.py — Three-level error recovery"""
import asyncio
from datetime import datetime, timezone
from typing import Callable, Any

from app.config import config
from orchestrator.state_manager import WorkflowState, StateManager
from audit.audit_logger import AuditLogger
from communication.event_bus import EventBus
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()


class ExceptionHandler:
    """
    Three-level recovery:
      L1 — retry up to MAX_RETRIES with enriched prompt
      L2 — human gate via Slack/email with SLA window
      L3 — auto-skip after SLA timeout, log TIMEOUT flag
    """

    def __init__(self, state: WorkflowState):
        self.state = state

    async def handle(self, step_name: str, error: str, retry_fn: Callable) -> Any:
        """Called when an agent step fails. Returns result or raises SkipStep."""
        self.state.mark_step_failed(step_name, error)
        StateManager.save(self.state)

        audit.log(
            agent_id="exception_handler",
            action="FAILURE_DETECTED",
            workflow_id=self.state.workflow_id,
            step_name=step_name,
            input_summary=f"error: {error[:120]}",
            output_summary=f"retry_count={self.state.retry_count}",
            confidence=0.0,
        )

        # Level 1: retry
        if self.state.retry_count <= config.MAX_RETRIES:
            logger.info(f"L1 retry {self.state.retry_count}/{config.MAX_RETRIES} | step={step_name}")
            await asyncio.sleep(1 * self.state.retry_count)   # back-off
            audit.log(
                agent_id="exception_handler",
                action="RETRY_ATTEMPT",
                workflow_id=self.state.workflow_id,
                step_name=step_name,
                output_summary=f"attempt={self.state.retry_count}",
                confidence=0.0,
            )
            try:
                result = await retry_fn(enriched=True)
                audit.log(
                    agent_id="exception_handler",
                    action="RETRY_SUCCESS",
                    workflow_id=self.state.workflow_id,
                    step_name=step_name,
                    output_summary="recovered on retry",
                    confidence=1.0,
                )
                return result
            except Exception as e:
                return await self.handle(step_name, str(e), retry_fn)

        # Level 2: human gate
        logger.warning(f"L2 human gate triggered | step={step_name} | workflow={self.state.workflow_id}")
        self.state.human_gate_pending = True
        self.state.human_gate_step = step_name
        StateManager.save(self.state)

        audit.log(
            agent_id="exception_handler",
            action="HUMAN_GATE_TRIGGERED",
            workflow_id=self.state.workflow_id,
            step_name=step_name,
            output_summary=f"awaiting human approval | SLA={config.SLA_TIMEOUT_MINUTES}min",
            confidence=0.0,
        )

        EventBus.publish("human_gate_required", {
            "workflow_id": self.state.workflow_id,
            "step_name": step_name,
            "error": error,
            "retry_count": self.state.retry_count,
        })

        # Wait for human response within SLA window
        deadline = config.SLA_TIMEOUT_MINUTES * 60
        waited = 0
        poll_interval = 5
        while waited < deadline:
            await asyncio.sleep(poll_interval)
            waited += poll_interval
            fresh = StateManager.load(self.state.workflow_id)
            if fresh and fresh.human_approval is not None:
                if fresh.human_approval:
                    logger.info(f"Human approved step={step_name}")
                    audit.log(
                        agent_id="exception_handler",
                        action="HUMAN_APPROVED",
                        workflow_id=self.state.workflow_id,
                        step_name=step_name,
                        output_summary="human approved, resuming",
                        confidence=1.0,
                    )
                    self.state.human_gate_pending = False
                    self.state.human_approval = None
                    return fresh.human_input
                else:
                    raise StepSkipped(f"Human rejected step: {step_name}")

        # Level 3: timeout auto-skip
        logger.error(f"L3 SLA timeout | step={step_name} | workflow={self.state.workflow_id}")
        audit.log(
            agent_id="exception_handler",
            action="SLA_TIMEOUT_SKIP",
            workflow_id=self.state.workflow_id,
            step_name=step_name,
            output_summary="no human response within SLA window, auto-skipping",
            confidence=0.0,
        )
        self.state.human_gate_pending = False
        StateManager.save(self.state)
        raise StepSkipped(f"SLA timeout for step: {step_name}")


class StepSkipped(Exception):
    """Raised when a step is skipped (human rejection or SLA timeout)"""
    pass