"""
Message Schema Module - Pydantic models for structured agent communication.

Defines:
- AgentMessage: Universal message format for inter-agent communication
- MessageStatus: Enumeration for message processing states
- Validation and serialization for audit trail compliance
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
import uuid


class MessageStatus(Enum):
    """Message processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class AgentMessage(BaseModel):
    """
    Universal structured message format for inter-agent communication.
    
    Ensures:
    - Unique tracking with UUID
    - Workflow context preservation
    - Audit trail compliance
    - Type safety with Pydantic validation
    """
    
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique message identifier")
    workflow_id: str = Field(..., description="Associated workflow identifier")
    step_id: str = Field(..., description="Associated workflow step")
    from_agent: str = Field(..., description="Sender agent name")
    to_agent: str = Field(..., description="Recipient agent name")
    action: str = Field(..., description="Action to perform")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action data")
    status: MessageStatus = Field(default=MessageStatus.PENDING, description="Current status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message creation time")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    error_message: Optional[str] = Field(default=None, description="Error details if failed")
    parent_message_id: Optional[str] = Field(default=None, description="Parent message ID for tracing")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    @validator("status", pre=True)
    def validate_status(cls, v):
        """Ensure status is valid MessageStatus."""
        if isinstance(v, str):
            return MessageStatus(v)
        return v
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            MessageStatus: lambda v: v.value
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
        return self.dict(by_alias=False, exclude_none=False)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.json(by_alias=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary."""
        return cls(**data)
    
    def mark_processing(self) -> "AgentMessage":
        """Mark message as being processed."""
        self.status = MessageStatus.PROCESSING
        return self
    
    def mark_success(self) -> "AgentMessage":
        """Mark message as successfully processed."""
        self.status = MessageStatus.SUCCESS
        return self
    
    def mark_failed(self, error: str) -> "AgentMessage":
        """Mark message as failed."""
        self.status = MessageStatus.FAILED
        self.error_message = error
        return self
    
    def mark_retrying(self) -> "AgentMessage":
        """Mark message for retry."""
        self.status = MessageStatus.RETRYING
        self.retry_count += 1
        return self
    
    def mark_escalated(self, reason: str) -> "AgentMessage":
        """Mark message as escalated."""
        self.status = MessageStatus.ESCALATED
        self.error_message = reason
        return self


class WorkflowDefinition(BaseModel):
    """Workflow definition structure."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    name: str = Field(..., description="Human-readable workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    steps: List[Dict[str, Any]] = Field(..., description="Ordered workflow steps")
    sla_hours: float = Field(default=24, description="SLA target in hours")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Workflow metadata")


class StepDefinition(BaseModel):
    """Individual workflow step definition."""
    step_id: str = Field(..., description="Step identifier")
    name: str = Field(..., description="Step name")
    agent: str = Field(..., description="Agent to execute this step")
    action: str = Field(..., description="Action for the agent")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    timeout_seconds: int = Field(default=300, description="Step timeout")
    retries: int = Field(default=3, description="Maximum retries")
    dependencies: List[str] = Field(default_factory=list, description="Prerequisite step IDs")
    condition: Optional[Dict[str, Any]] = Field(default=None, description="Conditional execution logic")
    fallback_steps: Optional[List[str]] = Field(default=None, description="Fallback step IDs on failure")
    next_step_id: Optional[str] = Field(default=None, description="Next step ID (linear flow)")
