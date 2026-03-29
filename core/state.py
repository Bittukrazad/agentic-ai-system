"""core/state.py — Canonical WorkflowState TypedDict shared across the entire system.

Every agent, orchestrator step, and health monitor reads and writes
this single state object. It is the source of truth for a workflow run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict


# ---------------------------------------------------------------------------
# TypedDict — strict typing for static analysis and IDE autocomplete
# ---------------------------------------------------------------------------

class TaskDict(TypedDict, total=False):
    id: str
    title: str
    description: str
    owner: str
    owner_email: str
    owner_slack: str
    owner_hint: str
    priority: str                # high | medium | low
    status: str                  # pending | in_progress | done | stalled | cancelled
    deadline: str                # ISO 8601
    deadline_hint: str
    created_at: str
    updated_at: str
    escalation_count: int
    source: str


class DecisionDict(TypedDict, total=False):
    decision: str
    rationale: str
    action: str
    params: Dict[str, Any]
    confidence: float
    prompt_key: str
    agent_id: str
    timestamp: str


class ErrorHistoryEntry(TypedDict):
    step: str
    error: str
    retry_count: int
    timestamp: str


class WorkflowStateDict(TypedDict, total=False):
    # Identity
    workflow_id: str
    workflow_type: str           # meeting | onboarding | procurement | contract
    priority: str                # normal | high | critical

    # Input
    payload: Dict[str, Any]

    # Lifecycle
    status: str                  # running | completed | failed | paused
    current_step: str
    completed_steps: List[str]
    failed_steps: List[str]

    # Retry tracking
    retry_count: int
    total_retries: int
    max_retries: int

    # Data produced during run
    fetched_data: Dict[str, Any]
    decisions: List[DecisionDict]
    actions_taken: List[Dict[str, Any]]
    tasks: List[TaskDict]
    outputs: Dict[str, Any]

    # Human gate
    human_gate_pending: bool
    human_gate_step: str
    human_approval: Optional[bool]
    human_input: Dict[str, Any]

    # SLA
    sla_start: str
    sla_deadline: Optional[str]
    sla_remaining_minutes: Optional[float]
    sla_breached: bool

    # Error history
    error_history: List[ErrorHistoryEntry]
    last_error: Optional[str]


# ---------------------------------------------------------------------------
# Builder — create a fresh WorkflowStateDict with sensible defaults
# ---------------------------------------------------------------------------

def new_state(
    workflow_id: str,
    workflow_type: str,
    payload: Dict[str, Any],
    priority: str = "normal",
    max_retries: int = 3,
) -> WorkflowStateDict:
    """Create a fresh workflow state dict with all fields initialised."""
    return WorkflowStateDict(
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        payload=payload,
        priority=priority,
        status="running",
        current_step="",
        completed_steps=[],
        failed_steps=[],
        retry_count=0,
        total_retries=0,
        max_retries=max_retries,
        fetched_data={},
        decisions=[],
        actions_taken=[],
        tasks=[],
        outputs={},
        human_gate_pending=False,
        human_gate_step="",
        human_approval=None,
        human_input={},
        sla_start=datetime.now(timezone.utc).isoformat(),
        sla_deadline=None,
        sla_remaining_minutes=None,
        sla_breached=False,
        error_history=[],
        last_error=None,
    )


# ---------------------------------------------------------------------------
# Helpers — pure functions that operate on a state dict
# ---------------------------------------------------------------------------

def mark_step_complete(state: WorkflowStateDict, step_name: str) -> WorkflowStateDict:
    if step_name not in state["completed_steps"]:
        state["completed_steps"].append(step_name)
    state["retry_count"] = 0
    return state


def mark_step_failed(state: WorkflowStateDict, step_name: str, error: str) -> WorkflowStateDict:
    state["retry_count"] = state.get("retry_count", 0) + 1
    state["total_retries"] = state.get("total_retries", 0) + 1
    state["last_error"] = error
    entry: ErrorHistoryEntry = {
        "step": step_name,
        "error": error,
        "retry_count": state["retry_count"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state.setdefault("error_history", []).append(entry)
    return state


def completion_fraction(state: WorkflowStateDict, total_steps: int) -> float:
    """What fraction of the workflow is done (0.0–1.0)."""
    done = len(state.get("completed_steps", []))
    return done / max(total_steps, 1)


def is_recovery_exhausted(state: WorkflowStateDict) -> bool:
    return state.get("retry_count", 0) > state.get("max_retries", 3)
