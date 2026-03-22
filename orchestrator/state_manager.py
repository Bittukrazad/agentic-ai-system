"""
State Manager Module - Persistent workflow state tracking.

Provides:
- Synchronous JSON state persistence
- Workflow execution tracking
- Step completion tracking
- Failure recovery on restart
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from utils.helpers import load_json_file, save_json_file, get_iso_now
from utils.logger import get_logger

logger = get_logger(__name__)


class StateManager:
    """
    Manages persistent workflow state for recovery and auditability.
    
    Synchronously writes to workflow_state_store.json to ensure
    no context loss on unexpected restarts.
    """
    
    def __init__(self, state_file: str):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to JSON state file
        """
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        state = load_json_file(self.state_file)
        if not state:
            state = {
                "workflows": {},
                "last_updated": get_iso_now()
            }
        return state
    
    def _persist_state(self) -> bool:
        """
        Synchronously persist state to file.
        
        Returns:
            Success status
        """
        self.state["last_updated"] = get_iso_now()
        success = save_json_file(self.state_file, self.state, pretty=True)
        
        if success:
            logger.info(f"State persisted", extra={"state_file": self.state_file})
        else:
            logger.error(f"Failed to persist state", extra={"state_file": self.state_file})
        
        return success
    
    def create_workflow_state(
        self,
        workflow_id: str,
        workflow_name: str,
        sla_hours: float,
        total_steps: int
    ) -> Dict[str, Any]:
        """
        Create new workflow state.
        
        Args:
            workflow_id: Workflow identifier
            workflow_name: Human-readable name
            sla_hours: SLA target in hours
            total_steps: Total number of steps
            
        Returns:
            Created workflow state
        """
        workflow_state = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "status": "running",
            "sla_hours": sla_hours,
            "total_steps": total_steps,
            "started_at": get_iso_now(),
            "completed_at": None,
            "steps": {},
            "current_step_id": None,
            "error": None,
            "retry_count": 0
        }
        
        self.state["workflows"][workflow_id] = workflow_state
        self._persist_state()
        
        logger.info(
            f"Workflow state created",
            extra={
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "total_steps": total_steps
            }
        )
        
        return workflow_state
    
    def get_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve workflow state.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Workflow state or None
        """
        return self.state["workflows"].get(workflow_id)
    
    def update_step_state(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        agent: str,
        status: str,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> bool:
        """
        Update step execution state.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            step_name: Step name
            agent: Executing agent
            status: Step status (running, completed, failed)
            inputs: Input parameters
            outputs: Output results
            error: Error message if failed
            duration_seconds: Execution time
            
        Returns:
            Success status
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            logger.error(f"Workflow not found", extra={"workflow_id": workflow_id})
            return False
        
        step_state = {
            "step_id": step_id,
            "step_name": step_name,
            "agent": agent,
            "status": status,
            "started_at": get_iso_now() if "started_at" not in (self.state["workflows"][workflow_id]["steps"].get(step_id) or {}) else self.state["workflows"][workflow_id]["steps"].get(step_id, {}).get("started_at"),
            "completed_at": get_iso_now() if status in ["completed", "failed"] else None,
            "inputs": inputs,
            "outputs": outputs,
            "error": error,
            "duration_seconds": duration_seconds,
            "retry_count": 0
        }
        
        # Preserve started_at time
        if step_id in workflow["steps"]:
            step_state["started_at"] = workflow["steps"][step_id].get("started_at", step_state["started_at"])
            step_state["retry_count"] = workflow["steps"][step_id].get("retry_count", 0)
        
        self.state["workflows"][workflow_id]["steps"][step_id] = step_state
        self.state["workflows"][workflow_id]["current_step_id"] = step_id
        
        self._persist_state()
        
        logger.info(
            f"Step state updated",
            extra={
                "workflow_id": workflow_id,
                "step_id": step_id,
                "status": status,
                "duration_seconds": duration_seconds
            }
        )
        
        return True
    
    def mark_step_retry(self, workflow_id: str, step_id: str) -> bool:
        """
        Mark step as being retried.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            
        Returns:
            Success status
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            return False
        
        step = workflow["steps"].get(step_id, {})
        if not step:
            return False
        
        step["retry_count"] = step.get("retry_count", 0) + 1
        self.state["workflows"][workflow_id]["steps"][step_id] = step
        self.state["workflows"][workflow_id]["retry_count"] = self.state["workflows"][workflow_id].get("retry_count", 0) + 1
        
        self._persist_state()
        
        logger.info(
            f"Step marked for retry",
            extra={
                "workflow_id": workflow_id,
                "step_id": step_id,
                "retry_count": step["retry_count"]
            }
        )
        
        return True
    
    def complete_workflow(
        self,
        workflow_id: str,
        status: str = "completed",
        error: Optional[str] = None
    ) -> bool:
        """
        Mark workflow as complete.
        
        Args:
            workflow_id: Workflow ID
            status: Final status (completed, failed, cancelled)
            error: Error message if failed
            
        Returns:
            Success status
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            return False
        
        self.state["workflows"][workflow_id]["status"] = status
        self.state["workflows"][workflow_id]["completed_at"] = get_iso_now()
        self.state["workflows"][workflow_id]["error"] = error
        
        self._persist_state()
        
        logger.info(
            f"Workflow completed",
            extra={
                "workflow_id": workflow_id,
                "status": status,
                "error": error
            }
        )
        
        return True
    
    def get_step_state(self, workflow_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """
        Get step execution state.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            
        Returns:
            Step state or None
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            return None
        
        return workflow["steps"].get(step_id)
    
    def get_workflow_steps(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get all steps for workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Dictionary of steps
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            return {}
        
        return workflow.get("steps", {})
    
    def get_failed_steps(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get all failed steps in workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            List of failed step states
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            return []
        
        return [
            step for step in workflow["steps"].values()
            if step.get("status") == "failed"
        ]
    
    def get_all_workflows(self) -> Dict[str, Any]:
        """
        Get all workflow states.
        
        Returns:
            Dictionary of all workflows
        """
        return self.state.get("workflows", {})
    
    def get_workflow_progress(self, workflow_id: str) -> Dict[str, Any]:
        """
        Calculate workflow progress.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Progress metrics
        """
        workflow = self.get_workflow_state(workflow_id)
        if not workflow:
            return {}
        
        total_steps = workflow.get("total_steps", 0)
        completed_steps = len([
            s for s in workflow["steps"].values()
            if s.get("status") == "completed"
        ])
        failed_steps = len([
            s for s in workflow["steps"].values()
            if s.get("status") == "failed"
        ])
        
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return {
            "workflow_id": workflow_id,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "pending_steps": total_steps - completed_steps - failed_steps,
            "progress_percentage": round(progress_percentage, 2),
            "status": workflow.get("status")
        }
    
    def clear_old_workflows(self, days: int = 30) -> int:
        """
        Clear old completed workflows (for maintenance).
        
        Args:
            days: Keep workflows from last N days
            
        Returns:
            Number of workflows removed
        """
        from datetime import timedelta
        from utils.helpers import iso_to_datetime
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        removed = 0
        
        workflows_to_remove = []
        for workflow_id, workflow in self.state["workflows"].items():
            if workflow.get("status") == "completed":
                completed_at = workflow.get("completed_at")
                if completed_at:
                    completed_dt = iso_to_datetime(completed_at)
                    if completed_dt < cutoff_date:
                        workflows_to_remove.append(workflow_id)
        
        for workflow_id in workflows_to_remove:
            del self.state["workflows"][workflow_id]
            removed += 1
        
        if removed > 0:
            self._persist_state()
            logger.info(f"Removed {removed} old workflows")
        
        return removed
