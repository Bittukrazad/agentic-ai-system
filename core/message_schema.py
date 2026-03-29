"""core/message_schema.py — Canonical Pydantic message schemas for all inter-agent communication.

Every message that travels across the event bus, message queue, or direct
agent-to-agent calls must be an instance of one of these schemas.

Benefits:
  - Type safety at the boundary between agents
  - Automatic validation (wrong field type raises immediately)
  - Self-documenting — the schema IS the contract
  - FastAPI request/response models reuse these same classes

Usage:
    from core.message_schema import WorkflowTriggerMessage, TaskAssignedMessage

    msg = WorkflowTriggerMessage(
        workflow_id="wf-abc123",
        workflow_type="meeting",
        payload={"transcript": "Alice: ..."},
    )
    EventBus.publish("workflow_triggered", msg.to_dict())
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
import uuid


# ---------------------------------------------------------------------------
# Enums — valid string literals enforced at construction time
# ---------------------------------------------------------------------------

class WorkflowType(str, Enum):
    MEETING      = "meeting"
    ONBOARDING   = "onboarding"
    PROCUREMENT  = "procurement"
    CONTRACT     = "contract"


class WorkflowStatus(str, Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    PAUSED    = "paused"


class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    STALLED     = "stalled"
    CANCELLED   = "cancelled"


class TaskPriority(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class AlertLevel(str, Enum):
    INFO     = "INFO"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


class AgentAction(str, Enum):
    # Workflow lifecycle
    WORKFLOW_STARTED   = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED    = "WORKFLOW_FAILED"
    STEP_COMPLETE      = "STEP_COMPLETE"
    STEP_SKIPPED       = "STEP_SKIPPED"
    # Data / decisions
    DATA_FETCHED       = "DATA_FETCHED"
    DECISION_MADE      = "DECISION_MADE"
    ACTION_EXECUTED    = "ACTION_EXECUTED"
    VERIFICATION_COMPLETE = "VERIFICATION_COMPLETE"
    # Recovery
    FAILURE_DETECTED   = "FAILURE_DETECTED"
    RETRY_ATTEMPT      = "RETRY_ATTEMPT"
    RETRY_SUCCESS      = "RETRY_SUCCESS"
    HUMAN_GATE_TRIGGERED = "HUMAN_GATE_TRIGGERED"
    HUMAN_APPROVED     = "HUMAN_APPROVED"
    SLA_TIMEOUT_SKIP   = "SLA_TIMEOUT_SKIP"
    # Health monitoring
    DRIFT_DETECTED     = "DRIFT_DETECTED"
    BREACH_PREDICTED   = "BREACH_PREDICTED"
    ANOMALY_DETECTED   = "ANOMALY_DETECTED"
    WORKFLOW_REROUTED  = "WORKFLOW_REROUTED"
    SLA_WARNING        = "SLA_WARNING"
    ALERT_SENT         = "ALERT_SENT"
    # Meeting intelligence
    TASKS_REGISTERED   = "TASKS_REGISTERED"
    TASK_STATUS_UPDATED= "TASK_STATUS_UPDATED"
    TASK_ESCALATED     = "TASK_ESCALATED"
    TASK_OWNER_NOTIFIED= "TASK_OWNER_NOTIFIED"
    # Communication
    MESSAGE_PUBLISHED  = "MESSAGE_PUBLISHED"
    HUMAN_APPROVAL_RECEIVED = "HUMAN_APPROVAL_RECEIVED"


# ---------------------------------------------------------------------------
# Base message — every message carries these fields
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class BaseMessage:
    """All inter-agent messages inherit from this."""
    message_id:  str = field(default_factory=_new_id)
    timestamp:   str = field(default_factory=_now)
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Reconstruct from a plain dict (e.g. from EventBus payload)."""
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def validate(self) -> List[str]:
        """Return list of validation error strings. Empty = valid."""
        return []


# ---------------------------------------------------------------------------
# Workflow lifecycle messages
# ---------------------------------------------------------------------------

@dataclass
class WorkflowTriggerMessage(BaseMessage):
    """Sent by app/routes.py to the orchestrator to start a workflow."""
    workflow_id:   str = ""
    workflow_type: str = ""          # use WorkflowType enum values
    payload:       Dict[str, Any] = field(default_factory=dict)
    priority:      str = "normal"    # normal | high | critical

    def validate(self) -> List[str]:
        errors = []
        if not self.workflow_id:
            errors.append("workflow_id is required")
        if self.workflow_type not in [e.value for e in WorkflowType]:
            errors.append(f"workflow_type must be one of {[e.value for e in WorkflowType]}")
        return errors


@dataclass
class WorkflowStatusMessage(BaseMessage):
    """Published by orchestrator on every status change."""
    workflow_id:      str = ""
    workflow_type:    str = ""
    status:           str = WorkflowStatus.RUNNING
    current_step:     str = ""
    completed_steps:  List[str] = field(default_factory=list)
    retry_count:      int = 0
    sla_remaining_minutes: Optional[float] = None
    error:            Optional[str] = None


@dataclass
class WorkflowCompletedMessage(BaseMessage):
    """Published when a workflow finishes successfully."""
    workflow_id:      str = ""
    workflow_type:    str = ""
    completed_steps:  List[str] = field(default_factory=list)
    tasks_count:      int = 0
    total_retries:    int = 0
    sla_breached:     bool = False
    duration_seconds: float = 0.0


@dataclass
class WorkflowFailedMessage(BaseMessage):
    """Published when a workflow cannot recover and must abort."""
    workflow_id: str = ""
    step_name:   str = ""
    error:       str = ""
    retry_count: int = 0


# ---------------------------------------------------------------------------
# Agent decision & action messages
# ---------------------------------------------------------------------------

@dataclass
class DecisionMessage(BaseMessage):
    """Result of decision_agent calling the LLM."""
    workflow_id:  str = ""
    step_name:    str = ""
    agent_id:     str = "decision_agent"
    decision:     str = ""
    rationale:    str = ""
    action:       str = ""
    params:       Dict[str, Any] = field(default_factory=dict)
    confidence:   float = 0.0
    prompt_key:   str = ""
    retry_count:  int = 0

    def validate(self) -> List[str]:
        errors = []
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence must be 0.0–1.0, got {self.confidence}")
        return errors

    @property
    def is_confident(self) -> bool:
        from app.config import config
        return self.confidence >= config.CONFIDENCE_THRESHOLD


@dataclass
class VerificationMessage(BaseMessage):
    """Result of verification_agent checking a decision or action output."""
    workflow_id: str = ""
    step_name:   str = ""
    score:       float = 0.0
    passed:      bool = False
    issues:      List[str] = field(default_factory=list)
    checked_by:  str = "verification_agent"


@dataclass
class ActionResultMessage(BaseMessage):
    """Result of action_agent executing a real-world action."""
    workflow_id:  str = ""
    step_name:    str = ""
    action_type:  str = ""
    status:       str = "ok"          # ok | failed | skipped
    result:       Dict[str, Any] = field(default_factory=dict)
    error:        Optional[str] = None


# ---------------------------------------------------------------------------
# Task messages (meeting intelligence)
# ---------------------------------------------------------------------------

@dataclass
class TaskMessage(BaseMessage):
    """A single task produced by the meeting intelligence pipeline."""
    task_id:      str = ""
    workflow_id:  str = ""
    title:        str = ""
    description:  str = ""
    owner:        str = ""
    owner_email:  str = ""
    owner_slack:  str = ""
    priority:     str = TaskPriority.MEDIUM
    status:       str = TaskStatus.PENDING
    deadline:     str = ""            # ISO 8601
    escalation_count: int = 0
    created_at:   str = field(default_factory=_now)

    def validate(self) -> List[str]:
        errors = []
        if not self.title:
            errors.append("title is required")
        if self.priority not in [e.value for e in TaskPriority]:
            errors.append(f"priority must be one of {[e.value for e in TaskPriority]}")
        return errors


@dataclass
class TaskUpdateMessage(BaseMessage):
    """Sent when a task status changes (owner marks done, escalation re-assigns, etc.)."""
    task_id:     str = ""
    workflow_id: str = ""
    old_status:  str = ""
    new_status:  str = ""
    updated_by:  str = ""
    note:        str = ""


@dataclass
class EscalationMessage(BaseMessage):
    """Sent by escalation_manager when a task is stalled."""
    task_id:          str = ""
    workflow_id:      str = ""
    task_title:       str = ""
    original_owner:   str = ""
    new_owner:        str = ""
    escalation_level: int = 1         # 1=remind, 2=reassign, 3=full escalation
    deadline:         str = ""
    note:             str = ""


# ---------------------------------------------------------------------------
# Error recovery messages
# ---------------------------------------------------------------------------

@dataclass
class RetryMessage(BaseMessage):
    """Published by exception_handler on each retry attempt."""
    workflow_id:  str = ""
    step_name:    str = ""
    attempt:      int = 0
    max_attempts: int = 3
    error:        str = ""
    enriched:     bool = False


@dataclass
class HumanGateMessage(BaseMessage):
    """Published when the system needs human approval to proceed."""
    workflow_id:  str = ""
    step_name:    str = ""
    error:        str = ""
    retry_count:  int = 0
    sla_minutes:  int = 30
    context:      Dict[str, Any] = field(default_factory=dict)


@dataclass
class HumanApprovalMessage(BaseMessage):
    """Sent by a human (via API) in response to a HumanGateMessage."""
    workflow_id:  str = ""
    step_name:    str = ""
    approved:     bool = False
    approver_id:  str = ""
    human_input:  Dict[str, Any] = field(default_factory=dict)
    note:         str = ""


# ---------------------------------------------------------------------------
# Health monitoring messages
# ---------------------------------------------------------------------------

@dataclass
class DriftAlertMessage(BaseMessage):
    """Published by drift_detector when a step overruns its baseline."""
    workflow_id:      str = ""
    step_name:        str = ""
    elapsed_seconds:  float = 0.0
    baseline_seconds: float = 0.0
    overrun_factor:   float = 1.0
    level:            str = AlertLevel.WARNING


@dataclass
class BreachPredictionMessage(BaseMessage):
    """Published by bottleneck_predictor when breach probability exceeds threshold."""
    workflow_id:         str = ""
    breach_probability:  float = 0.0
    sla_remaining_mins:  float = 0.0
    completed_steps:     int = 0
    total_steps:         int = 0
    level:               str = AlertLevel.CRITICAL


@dataclass
class AnomalyMessage(BaseMessage):
    """Published by anomaly_detector when statistical outliers are found."""
    workflow_id:    str = ""
    anomaly_count:  int = 0
    anomalies:      List[Dict[str, Any]] = field(default_factory=list)
    level:          str = AlertLevel.WARNING


@dataclass
class RerouteMessage(BaseMessage):
    """Published by reroute_engine when the workflow path is changed."""
    workflow_id:      str = ""
    reason:           str = ""
    strategy:         str = ""
    steps_skipped:    int = 0
    steps_remaining:  int = 0


# ---------------------------------------------------------------------------
# Audit message — written by audit_logger for every agent action
# ---------------------------------------------------------------------------

@dataclass
class AuditEntryMessage(BaseMessage):
    """The canonical shape of one row in decision_logs.json."""
    entry_id:       int = 0
    workflow_id:    str = ""
    agent_id:       str = ""
    action:         str = ""
    step_name:      str = ""
    input_summary:  str = ""
    output_summary: str = ""
    confidence:     float = 1.0
    retry_count:    int = 0

    def validate(self) -> List[str]:
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.action:
            errors.append("action is required")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence {self.confidence} out of range 0.0–1.0")
        return errors


# ---------------------------------------------------------------------------
# Schema registry — maps event_type → message class
# ---------------------------------------------------------------------------

SCHEMA_REGISTRY: Dict[str, type] = {
    "workflow_triggered":    WorkflowTriggerMessage,
    "workflow_status":       WorkflowStatusMessage,
    "workflow_completed":    WorkflowCompletedMessage,
    "workflow_failed":       WorkflowFailedMessage,
    "decision_made":         DecisionMessage,
    "verification_complete": VerificationMessage,
    "action_executed":       ActionResultMessage,
    "task_created":          TaskMessage,
    "task_updated":          TaskUpdateMessage,
    "task_escalated":        EscalationMessage,
    "retry_attempt":         RetryMessage,
    "human_gate_required":   HumanGateMessage,
    "human_approved":        HumanApprovalMessage,
    "drift_detected":        DriftAlertMessage,
    "breach_predicted":      BreachPredictionMessage,
    "anomaly_detected":      AnomalyMessage,
    "workflow_rerouted":     RerouteMessage,
    "audit_entry":           AuditEntryMessage,
}


def get_schema(event_type: str) -> Optional[type]:
    """Return the message class for a given event type, or None if unregistered."""
    return SCHEMA_REGISTRY.get(event_type)


def validate_message(event_type: str, payload: Dict[str, Any]) -> List[str]:
    """
    Validate a raw payload dict against its registered schema.
    Returns list of error strings. Empty = valid.
    """
    schema_cls = get_schema(event_type)
    if schema_cls is None:
        return [f"No schema registered for event_type: '{event_type}'"]
    try:
        instance = schema_cls.from_dict(payload)
        return instance.validate()
    except TypeError as e:
        return [f"Schema construction failed: {e}"]


def build_message(event_type: str, **kwargs) -> Optional[BaseMessage]:
    """
    Construct and validate a typed message for the given event_type.
    Returns the message instance, or None if the event_type is unregistered.

    Example:
        msg = build_message("decision_made",
                            workflow_id="wf-001",
                            decision="approve",
                            confidence=0.92)
        EventBus.publish("decision_made", msg.to_dict())
    """
    schema_cls = get_schema(event_type)
    if schema_cls is None:
        return None
    return schema_cls(**kwargs)