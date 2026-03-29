"""memory/short_term_memory.py — In-memory store scoped to a single workflow run"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# In-process store: {key: value}
# Replace with Redis in production for multi-process deployments
_store: Dict[str, Any] = {}

# Human approval registry: {workflow_id: {step: approval_info}}
_approvals: Dict[str, Dict] = {}


class ShortTermMemory:
    """
    Fast in-process key-value store for active workflow state.
    Cleared after workflow completion in production; persists for demo/debug.
    For multi-instance deployments, swap _store for a Redis client.
    """

    @staticmethod
    def init():
        """Called on app startup"""
        _store.clear()
        _approvals.clear()

    @staticmethod
    def set(key: str, value: Any):
        _store[key] = value

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        return _store.get(key, default)

    @staticmethod
    def delete(key: str):
        _store.pop(key, None)

    @staticmethod
    def set_state(workflow_id: str, state_dict: Dict):
        _store[f"state:{workflow_id}"] = state_dict

    @staticmethod
    def get_state(workflow_id: str) -> Optional[Dict]:
        return _store.get(f"state:{workflow_id}")

    @staticmethod
    def set_human_approval(
        workflow_id: str,
        step_name: str,
        approved: bool,
        human_input: Dict,
        approver_id: str,
    ):
        if workflow_id not in _approvals:
            _approvals[workflow_id] = {}
        _approvals[workflow_id][step_name] = {
            "approved": approved,
            "human_input": human_input,
            "approver_id": approver_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Also update the state so exception_handler polling picks it up
        state = _store.get(f"state:{workflow_id}", {})
        state["human_approval"] = approved
        state["human_input"] = human_input
        _store[f"state:{workflow_id}"] = state

    @staticmethod
    def get_human_approval(workflow_id: str, step_name: str) -> Optional[Dict]:
        return _approvals.get(workflow_id, {}).get(step_name)

    @staticmethod
    def all_workflow_ids() -> list:
        return [k.replace("state:", "") for k in _store if k.startswith("state:")]

    @staticmethod
    def clear_workflow(workflow_id: str):
        keys_to_delete = [k for k in _store if workflow_id in k]
        for k in keys_to_delete:
            del _store[k]
        _approvals.pop(workflow_id, None)