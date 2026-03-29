"""orchestrator/state_manager.py — Persists and retrieves WorkflowState"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.short_term_memory import ShortTermMemory
from utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowState:
    """Shared state object passed between all agents in a workflow run"""

    def __init__(self, workflow_id: str, workflow_type: str, payload: dict, priority: str = "normal"):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.payload = payload
        self.priority = priority

        self.status: str = "running"
        self.current_step: str = ""
        self.completed_steps: List[str] = []
        self.failed_steps: List[str] = []
        self.retry_count: int = 0
        self.total_retries: int = 0

        self.fetched_data: Dict[str, Any] = {}
        self.decisions: List[Dict] = []
        self.actions_taken: List[Dict] = []
        self.tasks: List[Dict] = []
        self.outputs: Dict[str, Any] = {}

        self.human_gate_pending: bool = False
        self.human_gate_step: str = ""
        self.human_approval: Optional[bool] = None
        self.human_input: Dict = {}

        self.sla_start: str = datetime.now(timezone.utc).isoformat()
        self.sla_deadline: Optional[str] = None
        self.sla_remaining_minutes: Optional[float] = None

        self.error_history: List[Dict] = []
        self.last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        state = cls.__new__(cls)
        state.__dict__.update(data)
        return state

    def mark_step_complete(self, step_name: str):
        if step_name not in self.completed_steps:
            self.completed_steps.append(step_name)
        self.retry_count = 0
        logger.debug(f"Step complete: {step_name} | workflow={self.workflow_id}")

    def mark_step_failed(self, step_name: str, error: str):
        self.retry_count += 1
        self.total_retries += 1
        self.last_error = error
        self.error_history.append({
            "step": step_name,
            "error": error,
            "retry_count": self.retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.warning(f"Step failed: {step_name} | retry={self.retry_count} | error={error[:80]}")

    def add_task(self, task: dict):
        self.tasks.append(task)

    def add_decision(self, decision: dict):
        self.decisions.append(decision)

    def add_action(self, action: dict):
        self.actions_taken.append(action)


class StateManager:
    """Persists WorkflowState to short-term memory and database"""

    @staticmethod
    def save(state: WorkflowState):
        ShortTermMemory.set_state(state.workflow_id, state.to_dict())

    @staticmethod
    def load(workflow_id: str) -> Optional[WorkflowState]:
        data = ShortTermMemory.get_state(workflow_id)
        if data:
            return WorkflowState.from_dict(data)
        return None

    @staticmethod
    def update_status(workflow_id: str, status: str):
        data = ShortTermMemory.get_state(workflow_id) or {}
        data["status"] = status
        ShortTermMemory.set_state(workflow_id, data)

    @staticmethod
    def update_step(workflow_id: str, step_name: str):
        data = ShortTermMemory.get_state(workflow_id) or {}
        data["current_step"] = step_name
        ShortTermMemory.set_state(workflow_id, data)