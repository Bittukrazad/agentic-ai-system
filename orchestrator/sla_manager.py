"""orchestrator/sla_manager.py — SLA clock tracking and breach detection"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.config import config
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()

# SLA durations per workflow type (hours)
SLA_DURATIONS = {
    "meeting": 1,
    "onboarding": 48,
    "procurement": 72,
    "contract": 96,
}


class SLAManager:
    """Tracks SLA deadlines and calculates remaining time"""

    def __init__(self, workflow_id: str, workflow_type: str):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        hours = SLA_DURATIONS.get(workflow_type, 24)
        self.start_time = datetime.now(timezone.utc)
        self.deadline = self.start_time + timedelta(hours=hours)
        logger.info(f"SLA started | workflow={workflow_id} | deadline={self.deadline.isoformat()} | {hours}h")

    def remaining_minutes(self) -> float:
        now = datetime.now(timezone.utc)
        remaining = (self.deadline - now).total_seconds() / 60
        return max(0.0, remaining)

    def is_breached(self) -> bool:
        return datetime.now(timezone.utc) > self.deadline

    def breach_probability(self, completed_fraction: float) -> float:
        """
        Rough probability estimate: if elapsed time > completed fraction of SLA,
        breach is likely.
        """
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        total = (self.deadline - self.start_time).total_seconds()
        time_fraction = elapsed / total if total > 0 else 0
        if completed_fraction <= 0:
            return time_fraction
        # If we're spending more time than steps completed would suggest
        overrun = time_fraction / (completed_fraction + 0.001)
        return min(1.0, overrun * 0.5)

    def log_warning(self):
        remaining = self.remaining_minutes()
        audit.log(
            agent_id="sla_manager",
            action="SLA_WARNING",
            workflow_id=self.workflow_id,
            step_name="sla_check",
            output_summary=f"SLA breach risk: {remaining:.1f} minutes remaining",
            confidence=0.0,
        )
        logger.warning(f"SLA WARNING | workflow={self.workflow_id} | {remaining:.1f}min remaining")