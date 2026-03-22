"""
SLA Manager Module - SLA tracking and enforcement.

Provides:
- Workflow-level SLA tracking
- Step-level SLA tracking
- SLA breach detection and alerts
- Progress monitoring
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from utils.helpers import (
    iso_to_datetime, get_utc_now, get_iso_now, sla_status, add_hours_to_iso
)
from utils.logger import get_logger

logger = get_logger(__name__)


class SLAManager:
    """
    Manages SLA compliance tracking for workflows and steps.
    
    Monitors:
    - Workflow-level SLAs
    - Step-level SLAs
    - Critical breach alerts
    """
    
    def __init__(self, sla_check_interval_seconds: int = 600):
        """
        Initialize SLA manager.
        
        Args:
            sla_check_interval_seconds: Interval for SLA checks
        """
        self.sla_check_interval_seconds = sla_check_interval_seconds
        self.sla_records = {}
        self.breach_history = []
    
    def create_workflow_sla(
        self,
        workflow_id: str,
        workflow_name: str,
        sla_hours: float,
        start_time: str
    ) -> Dict[str, Any]:
        """
        Create SLA record for workflow.
        
        Args:
            workflow_id: Workflow ID
            workflow_name: Workflow name
            sla_hours: SLA target in hours
            start_time: ISO start time
            
        Returns:
            SLA record
        """
        sla_deadline = add_hours_to_iso(start_time, sla_hours)
        
        sla_record = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "sla_hours": sla_hours,
            "sla_seconds": sla_hours * 3600,
            "start_time": start_time,
            "deadline": sla_deadline,
            "status": "on_track",
            "breach_alerts_sent": [],
            "last_status_check": get_iso_now(),
            "steps": {}
        }
        
        self.sla_records[workflow_id] = sla_record
        
        logger.info(
            f"Workflow SLA created",
            extra={
                "workflow_id": workflow_id,
                "sla_hours": sla_hours,
                "deadline": sla_deadline
            }
        )
        
        return sla_record
    
    def create_step_sla(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        timeout_seconds: int,
        start_time: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create SLA record for step.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            step_name: Step name
            timeout_seconds: Step timeout
            start_time: ISO start time
            
        Returns:
            Step SLA record or None
        """
        if workflow_id not in self.sla_records:
            logger.warning(
                f"Workflow SLA not found for step",
                extra={"workflow_id": workflow_id, "step_id": step_id}
            )
            return None
        
        deadline_dt = iso_to_datetime(start_time) + timedelta(seconds=timeout_seconds)
        deadline = deadline_dt.isoformat()
        
        step_sla = {
            "step_id": step_id,
            "step_name": step_name,
            "timeout_seconds": timeout_seconds,
            "start_time": start_time,
            "deadline": deadline,
            "status": "on_track"
        }
        
        self.sla_records[workflow_id]["steps"][step_id] = step_sla
        
        return step_sla
    
    def check_workflow_sla(
        self,
        workflow_id: str,
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check workflow SLA status.
        
        Args:
            workflow_id: Workflow ID
            current_time: ISO time to check against (defaults to now)
            
        Returns:
            SLA status information
        """
        if workflow_id not in self.sla_records:
            return {"error": "Workflow SLA not found"}
        
        if current_time is None:
            current_time = get_iso_now()
        
        sla = self.sla_records[workflow_id]
        start_dt = iso_to_datetime(sla["start_time"])
        current_dt = iso_to_datetime(current_time)
        deadline_dt = iso_to_datetime(sla["deadline"])
        
        elapsed_seconds = (current_dt - start_dt).total_seconds()
        seconds_remaining = (deadline_dt - current_dt).total_seconds()
        
        # Determine status
        if seconds_remaining < 0:
            status = "breached"
        elif seconds_remaining < (sla["sla_seconds"] * 0.25):
            status = "critical"
        elif seconds_remaining < (sla["sla_seconds"] * 0.5):
            status = "warning"
        else:
            status = "on_track"
        
        sla["status"] = status
        sla["last_status_check"] = current_time
        
        result = {
            "workflow_id": workflow_id,
            "sla_hours": sla["sla_hours"],
            "elapsed_seconds": round(elapsed_seconds, 1),
            "seconds_remaining": round(seconds_remaining, 1),
            "percentage_used": round((elapsed_seconds / sla["sla_seconds"]) * 100, 1),
            "percentage_remaining": round((seconds_remaining / sla["sla_seconds"]) * 100, 1),
            "status": status,
            "deadline": sla["deadline"]
        }
        
        # Log critical status
        if status in ["critical", "breached"]:
            logger.warning(
                f"SLA status critical",
                extra={
                    "workflow_id": workflow_id,
                    "status": status,
                    "percentage_remaining": result["percentage_remaining"]
                }
            )
            
            breach_alert = {
                "workflow_id": workflow_id,
                "status": status,
                "timestamp": current_time
            }
            
            if breach_alert not in sla["breach_alerts_sent"]:
                sla["breach_alerts_sent"].append(breach_alert)
                self.breach_history.append(breach_alert)
        
        return result
    
    def check_step_sla(
        self,
        workflow_id: str,
        step_id: str,
        current_time: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check step SLA status.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            current_time: ISO time to check against
            
        Returns:
            Step SLA status or None
        """
        if workflow_id not in self.sla_records:
            return None
        
        if step_id not in self.sla_records[workflow_id]["steps"]:
            return None
        
        if current_time is None:
            current_time = get_iso_now()
        
        step_sla = self.sla_records[workflow_id]["steps"][step_id]
        start_dt = iso_to_datetime(step_sla["start_time"])
        current_dt = iso_to_datetime(current_time)
        deadline_dt = iso_to_datetime(step_sla["deadline"])
        
        elapsed_seconds = (current_dt - start_dt).total_seconds()
        seconds_remaining = (deadline_dt - current_dt).total_seconds()
        
        # Determine status
        if seconds_remaining < 0:
            status = "timeout"
        elif seconds_remaining < (step_sla["timeout_seconds"] * 0.1):
            status = "critical"
        else:
            status = "on_track"
        
        step_sla["status"] = status
        
        return {
            "step_id": step_id,
            "step_name": step_sla["step_name"],
            "timeout_seconds": step_sla["timeout_seconds"],
            "elapsed_seconds": round(elapsed_seconds, 1),
            "seconds_remaining": round(seconds_remaining, 1),
            "status": status
        }
    
    def get_all_slas(self) -> Dict[str, Any]:
        """Get all SLA records."""
        return self.sla_records
    
    def get_workflow_sla(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get SLA record for workflow."""
        return self.sla_records.get(workflow_id)
    
    def get_breached_workflows(self) -> List[str]:
        """Get list of workflows with breached SLAs."""
        breached = []
        for workflow_id, sla in self.sla_records.items():
            if sla["status"] == "breached":
                breached.append(workflow_id)
        return breached
    
    def get_critical_workflows(self) -> List[str]:
        """Get list of workflows with critical SLA status."""
        critical = []
        for workflow_id, sla in self.sla_records.items():
            if sla["status"] == "critical":
                critical.append(workflow_id)
        return critical
    
    def complete_workflow_sla(self, workflow_id: str, end_time: str) -> Dict[str, Any]:
        """
        Mark workflow SLA as complete.
        
        Args:
            workflow_id: Workflow ID
            end_time: ISO completion time
            
        Returns:
            Final SLA metrics
        """
        if workflow_id not in self.sla_records:
            return {}
        
        sla = self.sla_records[workflow_id]
        start_dt = iso_to_datetime(sla["start_time"])
        end_dt = iso_to_datetime(end_time)
        deadline_dt = iso_to_datetime(sla["deadline"])
        
        total_seconds = (end_dt - start_dt).total_seconds()
        status = "met" if end_dt <= deadline_dt else "missed"
        
        result = {
            "workflow_id": workflow_id,
            "sla_status": status,
            "total_seconds": round(total_seconds, 1),
            "sla_seconds": sla["sla_seconds"],
            "seconds_over": round((end_dt - deadline_dt).total_seconds(), 1) if status == "missed" else 0,
            "completion_time": end_time
        }
        
        sla["status"] = status
        sla["completed_at"] = end_time
        
        logger.info(
            f"Workflow SLA complete",
            extra={
                "workflow_id": workflow_id,
                "sla_status": status,
                "total_seconds": result["total_seconds"]
            }
        )
        
        return result
    
    def get_breach_history(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get breach history.
        
        Args:
            workflow_id: Optional filter by workflow
            
        Returns:
            List of breach events
        """
        if workflow_id:
            return [b for b in self.breach_history if b.get("workflow_id") == workflow_id]
        return self.breach_history
