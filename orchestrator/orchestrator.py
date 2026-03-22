"""
Orchestrator Module - Central workflow execution controller.

Provides:
- Workflow loading and initialization
- Step-by-step execution coordination
- Agent communication
- State persistence
- Error recovery
- SLA monitoring
"""

import json
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import asyncio

from utils.logger import get_logger
from utils.helpers import (
    load_json_file, get_iso_now, iso_to_datetime, get_timestamp_seconds
)
from audit.audit_logger import AuditLogger
from orchestrator.state_manager import StateManager
from orchestrator.exception_handler import ExceptionHandler, RoutingStrategy
from orchestrator.sla_manager import SLAManager
from orchestrator.workflow_engine import WorkflowEngine
from core.retry import RetryConfig, retry_with_backoff

logger = get_logger(__name__)


class Orchestrator:
    """
    Central orchestrator for multi-agent workflow execution.
    
    Responsibilities:
    - Load workflow definitions
    - Coordinate agent execution
    - Track state and progress
    - Handle failures intelligently
    - Monitor SLAs
    - Maintain audit trail
    """
    
    def __init__(
        self,
        workflows_dir: str,
        state_file: str,
        trace_log_file: str,
        decision_log_file: str,
        max_retries: int = 3
    ):
        """
        Initialize orchestrator.
        
        Args:
            workflows_dir: Path to workflow definitions
            state_file: Path to state persistence file
            trace_log_file: Path to trace logs
            decision_log_file: Path to decision logs
            max_retries: Default max retries
        """
        self.workflows_dir = workflows_dir
        self.max_retries = max_retries
        
        # Initialize subsystems
        self.state_manager = StateManager(state_file)
        self.audit_logger = AuditLogger(trace_log_file, decision_log_file)
        self.exception_handler = ExceptionHandler(max_retries)
        self.sla_manager = SLAManager()
        self.workflow_engine = WorkflowEngine()
        
        # Workflow cache
        self.loaded_workflows = {}
        
        logger.info(
            "Orchestrator initialized",
            extra={"workflows_dir": workflows_dir}
        )
    
    def load_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Load workflow definition from file.
        
        Args:
            workflow_id: Workflow identifier (matches filename)
            
        Returns:
            Workflow definition or None
        """
        if workflow_id in self.loaded_workflows:
            return self.loaded_workflows[workflow_id]
        
        # Try multiple file patterns
        patterns = [
            f"{self.workflows_dir}/{workflow_id}.json",
            f"{self.workflows_dir}/{workflow_id}_workflow.json"
        ]
        
        for pattern in patterns:
            path = Path(pattern)
            if path.exists():
                try:
                    workflow = load_json_file(pattern)
                    self.loaded_workflows[workflow_id] = workflow
                    logger.info(f"Workflow loaded", extra={"workflow_id": workflow_id})
                    return workflow
                except Exception as e:
                    logger.error(
                        f"Failed to load workflow",
                        extra={"workflow_id": workflow_id, "error": str(e)}
                    )
        
        logger.warning(f"Workflow not found", extra={"workflow_id": workflow_id})
        return None
    
    def initialize_workflow(
        self,
        workflow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Initialize workflow execution.
        
        Args:
            workflow_id: Workflow to execute
            trigger_data: Data passed to workflow
            
        Returns:
            Root trace ID or None on error
        """
        # Load workflow definition
        workflow_def = self.load_workflow(workflow_id)
        if not workflow_def:
            return None
        
        # Validate workflow
        valid, error = self.workflow_engine.validate_workflow_definition(workflow_def)
        if not valid:
            logger.error(f"Invalid workflow definition: {error}")
            return None
        
        # Create state
        workflow_name = workflow_def.get("name", workflow_id)
        sla_hours = workflow_def.get("sla_hours", 24)
        total_steps = len(workflow_def.get("steps", []))
        
        self.state_manager.create_workflow_state(
            workflow_id,
            workflow_name,
            sla_hours,
            total_steps
        )
        
        # Create SLA
        start_time = get_iso_now()
        self.sla_manager.create_workflow_sla(
            workflow_id,
            workflow_name,
            sla_hours,
            start_time
        )
        
        # Log workflow start
        root_trace_id = self.audit_logger.log_workflow_start(
            workflow_id,
            workflow_name,
            sla_hours
        )
        
        logger.info(
            f"Workflow initialized",
            extra={
                "workflow_id": workflow_id,
                "total_steps": total_steps,
                "root_trace_id": root_trace_id
            }
        )
        
        return root_trace_id
    
    def execute_workflow(
        self,
        workflow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute workflow end-to-end.
        
        Args:
            workflow_id: Workflow to execute
            trigger_data: Input data
            
        Returns:
            Tuple of (success, result)
        """
        start_timestamp = time.time()
        result = {
            "workflow_id": workflow_id,
            "status": "initializing",
            "steps_completed": 0,
            "steps_failed": 0
        }
        
        try:
            # Initialize
            root_trace_id = self.initialize_workflow(workflow_id, trigger_data)
            if not root_trace_id:
                result["status"] = "failed"
                result["error"] = "Failed to initialize workflow"
                return False, result
            
            # Get workflow definition
            workflow_def = self.loaded_workflows.get(workflow_id)
            if not workflow_def:
                result["status"] = "failed"
                result["error"] = "Workflow definition not found"
                return False, result
            
            # Get first step
            current_step = self.workflow_engine.get_first_step(workflow_def)
            if not current_step:
                result["status"] = "failed"
                result["error"] = "No steps in workflow"
                return False, result
            
            # Create status tracking
            workflow_state = self.state_manager.get_workflow_state(workflow_id)
            if workflow_state is None:
                logger.error(f"Workflow state not found: {workflow_id}")
                result["status"] = "failed"
                result["error"] = "Workflow state not initialized"
                return False, result
            
            step_outputs = {}
            
            # Execute steps
            result["status"] = "executing"
            
            while current_step and workflow_state["status"] == "running":
                step_id = current_step["step_id"]
                
                # Check dependencies
                deps_met, dep_error = self.workflow_engine.resolve_step_dependencies(
                    step_id,
                    workflow_def,
                    workflow_state["steps"]
                )
                
                if not deps_met:
                    logger.error(f"Dependencies not met: {dep_error}")
                    current_step = None
                    break
                
                # Execute step
                success, step_result = self._execute_step(
                    workflow_id,
                    current_step,
                    step_outputs,
                    root_trace_id
                )
                
                if success:
                    result["steps_completed"] += 1
                    step_outputs[step_id] = step_result.get("outputs", {})
                else:
                    result["steps_failed"] += 1
                
                # Determine next step
                next_step_id, routing_reason = self.workflow_engine.determine_next_step(
                    current_step,
                    step_result.get("outputs", {}),
                    workflow_def,
                    workflow_state,
                    step_failed=not success
                )
                
                logger.info(
                    f"Step routing decision",
                    extra={
                        "workflow_id": workflow_id,
                        "current_step": step_id,
                        "next_step": next_step_id,
                        "reason": routing_reason
                    }
                )
                
                # Get next step
                if next_step_id:
                    current_step = self.workflow_engine.get_step_by_id(next_step_id, workflow_def)
                else:
                    current_step = None
            
            # Complete workflow
            duration = time.time() - start_timestamp
            success = result["steps_failed"] == 0
            
            self.state_manager.complete_workflow(
                workflow_id,
                status="completed" if success else "failed"
            )
            
            sla_result = self.sla_manager.complete_workflow_sla(
                workflow_id,
                get_iso_now()
            )
            
            self.audit_logger.log_workflow_end(
                workflow_id,
                status="completed" if success else "failed",
                duration_seconds=duration,
                parent_trace_id=root_trace_id
            )
            
            result["status"] = "completed" if success else "failed"
            result["duration_seconds"] = round(duration, 3)
            result["sla_result"] = sla_result
            
            logger.info(
                f"Workflow execution complete",
                extra={
                    "workflow_id": workflow_id,
                    "status": result["status"],
                    "duration": duration,
                    "steps_completed": result["steps_completed"]
                }
            )
            
            return success, result
        
        except Exception as e:
            duration = time.time() - start_timestamp
            
            logger.error(
                f"Workflow execution error",
                extra={
                    "workflow_id": workflow_id,
                    "error": str(e),
                    "duration": duration
                }
            )
            
            self.state_manager.complete_workflow(
                workflow_id,
                status="failed",
                error=str(e)
            )
            
            result["status"] = "failed"
            result["error"] = str(e)
            result["duration_seconds"] = round(duration, 3)
            
            return False, result
    
    def _execute_step(
        self,
        workflow_id: str,
        step: Dict[str, Any],
        previous_outputs: Dict[str, Any],
        root_trace_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute individual step.
        
        Args:
            workflow_id: Workflow ID
            step: Step definition
            previous_outputs: Outputs from previous steps
            root_trace_id: Root trace ID for audit
            
        Returns:
            Tuple of (success, result)
        """
        step_id = step["step_id"]
        agent = step["agent"]
        action = step["action"]
        parameters = step.get("parameters", {})
        timeout_seconds = step.get("timeout_seconds", 300)
        max_retries = step.get("retries", self.max_retries)
        
        start_time = get_iso_now()
        
        # Create SLA for step
        self.sla_manager.create_step_sla(
            workflow_id,
            step_id,
            step.get("name", step_id),
            timeout_seconds,
            start_time
        )
        
        # Update state
        self.state_manager.update_step_state(
            workflow_id,
            step_id,
            step.get("name", step_id),
            agent,
            "running"
        )
        
        start_timestamp = time.time()
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                # Log step start
                step_trace_id = self.audit_logger.log_agent_action(
                    workflow_id,
                    step_id,
                    agent,
                    action,
                    parameters,
                    {},
                    "started",
                    0,
                    parent_trace_id=root_trace_id
                )
                
                # Execute agent action (mock implementation)
                # In production, would route to actual agent
                result = self._mock_agent_execution(agent, action, parameters)
                
                duration = time.time() - start_timestamp
                
                # Update state with success
                self.state_manager.update_step_state(
                    workflow_id,
                    step_id,
                    step.get("name", step_id),
                    agent,
                    "completed",
                    inputs=parameters,
                    outputs=result,
                    duration_seconds=duration
                )
                
                # Log success
                self.audit_logger.log_agent_action(
                    workflow_id,
                    step_id,
                    agent,
                    action,
                    parameters,
                    result,
                    "completed",
                    duration,
                    parent_trace_id=root_trace_id
                )
                
                logger.info(
                    f"Step executed successfully",
                    extra={
                        "workflow_id": workflow_id,
                        "step_id": step_id,
                        "agent": agent,
                        "duration": round(duration, 3)
                    }
                )
                
                return True, {"outputs": result}
            
            except Exception as e:
                last_error = e
                duration = time.time() - start_timestamp
                
                # Classify error
                decision = self.exception_handler.handle_exception(
                    e,
                    workflow_id,
                    step_id,
                    step.get("name", step_id),
                    retry_count,
                    max_retries,
                    has_fallback=bool(step.get("fallback_steps"))
                )
                
                if decision["should_retry"]:
                    retry_count += 1
                    self.state_manager.mark_step_retry(workflow_id, step_id)
                    
                    self.audit_logger.log_retry(
                        workflow_id,
                        step_id,
                        agent,
                        action,
                        retry_count,
                        1.0,  # delay
                        str(e),
                        parent_trace_id=root_trace_id
                    )
                    
                    logger.warning(
                        f"Step retry",
                        extra={
                            "workflow_id": workflow_id,
                            "step_id": step_id,
                            "retry_count": retry_count
                        }
                    )
                    
                    time.sleep(1.0)  # Simple delay
                else:
                    # Don't retry
                    break
        
        # Update state with failure
        duration = time.time() - start_timestamp
        self.state_manager.update_step_state(
            workflow_id,
            step_id,
            step.get("name", step_id),
            agent,
            "failed",
            error=str(last_error),
            duration_seconds=duration
        )
        
        logger.error(
            f"Step execution failed",
            extra={
                "workflow_id": workflow_id,
                "step_id": step_id,
                "error": str(last_error)
            }
        )
        
        return False, {"error": str(last_error)}
    
    def _mock_agent_execution(
        self,
        agent: str,
        action: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mock agent execution (replace with actual routing).
        
        Args:
            agent: Agent name
            action: Action to perform
            parameters: Action parameters
            
        Returns:
            Action result
        """
        # Simulated execution
        return {
            "agent": agent,
            "action": action,
            "status": "completed",
            "result": "Success",
            "timestamp": get_iso_now()
        }
    
    def get_workflow_progress(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow execution progress.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Progress information
        """
        progress = self.state_manager.get_workflow_progress(workflow_id)
        sla_status = self.sla_manager.check_workflow_sla(workflow_id)
        
        return {
            **progress,
            "sla_status": sla_status
        }
    
    def get_workflow_history(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get full workflow execution history.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            History information
        """
        return {
            "workflow_id": workflow_id,
            "state": self.state_manager.get_workflow_state(workflow_id),
            "audit_trace": self.audit_logger.get_trace_for_workflow(workflow_id),
            "decisions": self.audit_logger.get_decisions_for_workflow(workflow_id),
            "errors": self.exception_handler.get_error_history(workflow_id)
        }
