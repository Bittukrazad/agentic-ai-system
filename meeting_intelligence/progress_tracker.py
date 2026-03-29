"""meeting_intelligence/progress_tracker.py — Tracks task completion and detects stalls"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from memory.short_term_memory import ShortTermMemory
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()

# Stall threshold: task not updated within this many hours is flagged
STALL_THRESHOLD_HOURS = 24


class ProgressTracker:
    """
    Registers tasks for a workflow run and polls for stalls.
    Stall = task status still 'pending' with no update past deadline.
    Called by APScheduler on a schedule.
    """

    def register_tasks(self, workflow_id: str, tasks: List[Dict]):
        """Store tasks in short-term memory for polling"""
        key = f"tracker:{workflow_id}:tasks"
        ShortTermMemory.set(key, tasks)
        logger.info(f"Registered {len(tasks)} tasks for tracking | workflow={workflow_id}")
        audit.log(
            agent_id="progress_tracker",
            action="TASKS_REGISTERED",
            workflow_id=workflow_id,
            step_name="register",
            output_summary=f"{len(tasks)} tasks registered",
            confidence=1.0,
        )

    def update_task_status(self, workflow_id: str, task_id: str, status: str, note: str = ""):
        """Called when a task owner marks a task done/in-progress"""
        key = f"tracker:{workflow_id}:tasks"
        tasks = ShortTermMemory.get(key) or []
        for task in tasks:
            if task.get("id") == task_id:
                task["status"] = status
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                task["status_note"] = note
                break
        ShortTermMemory.set(key, tasks)
        audit.log(
            agent_id="progress_tracker",
            action="TASK_STATUS_UPDATED",
            workflow_id=workflow_id,
            step_name="update",
            input_summary=f"task_id={task_id}",
            output_summary=f"status={status}",
            confidence=1.0,
        )

    def get_all_tasks(self, workflow_id: str) -> List[Dict]:
        key = f"tracker:{workflow_id}:tasks"
        return ShortTermMemory.get(key) or []

    def get_stalled(self, workflow_id: Optional[str] = None) -> List[Dict]:
        """Return tasks that are stalled (pending past deadline)"""
        stalled = []
        now = datetime.now(timezone.utc)

        if workflow_id:
            tasks = self.get_all_tasks(workflow_id)
            for task in tasks:
                if self._is_stalled(task, now):
                    stalled.append(task)
        return stalled

    def _is_stalled(self, task: Dict, now: datetime) -> bool:
        if task.get("status") in ("done", "cancelled", "skipped"):
            return False
        deadline_str = task.get("deadline", "")
        if not deadline_str:
            return False
        try:
            deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            return now > deadline
        except ValueError:
            return False

    def get_completion_stats(self, workflow_id: str) -> Dict:
        tasks = self.get_all_tasks(workflow_id)
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("status") == "done")
        stalled = sum(1 for t in tasks if self._is_stalled(t, datetime.now(timezone.utc)))
        pending = total - done - stalled
        return {
            "total": total,
            "done": done,
            "pending": pending,
            "stalled": stalled,
            "completion_pct": round((done / total * 100) if total else 0, 1),
        }