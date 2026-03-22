"""
Base Agent Module - Foundation for all agents in the multi-agent system.

This module provides the abstract base class for all agents, implementing:
- Structured message passing
- Audit logging
- Error handling
- State management
- Agent communication patterns
"""

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class AgentStatus(Enum):
    """Agent operational status."""
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    RETRY = "retry"
    ESCALATED = "escalated"


class Message:
    """
    Structured message format for agent communication.
    
    Mandatory format as per specification:
    - workflow_id: Unique workflow identifier
    - step_id: Step identifier within workflow
    - from_agent: Sender agent name
    - to_agent: Recipient agent name
    - action: Action to perform
    - payload: Action data
    - status: Current message status
    - timestamp: ISO format timestamp
    """
    
    def __init__(
        self,
        workflow_id: str,
        step_id: str,
        from_agent: str,
        to_agent: str,
        action: str,
        payload: Dict[str, Any],
        status: str = "pending",
        timestamp: Optional[str] = None,
        message_id: Optional[str] = None
    ):
        """Initialize a structured message."""
        self.message_id = message_id or str(uuid.uuid4())
        self.workflow_id = workflow_id
        self.step_id = step_id
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.action = action
        self.payload = payload
        self.status = status
        self.timestamp = timestamp or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_id": self.message_id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "action": self.action,
            "payload": self.payload,
            "status": self.status,
            "timestamp": self.timestamp
        }
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create Message from dictionary."""
        return cls(
            workflow_id=data.get("workflow_id") or "",
            step_id=data.get("step_id") or "",
            from_agent=data.get("from_agent") or "",
            to_agent=data.get("to_agent") or "",
            action=data.get("action") or "",
            payload=data.get("payload", {}),
            status=data.get("status", "pending"),
            timestamp=data.get("timestamp"),
            message_id=data.get("message_id")
        )


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent system.
    
    Provides:
    - Structured message handling
    - Audit logging
    - Error handling with retry logic
    - State management
    - Standardized agent interface
    """
    
    def __init__(self, agent_name: str, max_retries: int = 3):
        """
        Initialize base agent.
        
        Args:
            agent_name: Unique identifier for this agent
            max_retries: Maximum retry attempts for failed operations
        """
        self.agent_name = agent_name
        self.max_retries = max_retries
        self.state = {}
        self.message_history = []
        self.error_count = 0
    
    @abstractmethod
    def process_message(self, message: Message) -> Message:
        """
        Process incoming message and return response.
        
        This method must be implemented by all subclasses.
        
        Args:
            message: Incoming Message object
            
        Returns:
            Message: Response message with action result
        """
        pass
    
    def send_message(
        self,
        workflow_id: str,
        step_id: str,
        to_agent: str,
        action: str,
        payload: Dict[str, Any]
    ) -> Message:
        """
        Create and send a message to another agent.
        
        Args:
            workflow_id: Workflow identifier
            step_id: Step identifier
            to_agent: Recipient agent name
            action: Action to perform
            payload: Action data
            
        Returns:
            Message: Created message object
        """
        message = Message(
            workflow_id=workflow_id,
            step_id=step_id,
            from_agent=self.agent_name,
            to_agent=to_agent,
            action=action,
            payload=payload,
            status=AgentStatus.PENDING.value
        )
        self._log_message(message, direction="outgoing")
        return message
    
    def handle_message(self, message: Message) -> Message:
        """
        Handle incoming message and produce response.
        
        Implements retry logic and error handling.
        
        Args:
            message: Incoming message
            
        Returns:
            Message: Response message
        """
        self._log_message(message, direction="incoming")
        
        try:
            response = self.process_message(message)
            response.status = AgentStatus.SUCCESS.value
            self.error_count = 0
            self._log_message(response, direction="outgoing")
            return response
        
        except Exception as e:
            self.error_count += 1
            
            if self.error_count < self.max_retries:
                response = Message(
                    workflow_id=message.workflow_id,
                    step_id=message.step_id,
                    from_agent=self.agent_name,
                    to_agent=message.from_agent,
                    action="retry",
                    payload={"error": str(e), "retry_count": self.error_count},
                    status=AgentStatus.RETRY.value
                )
            else:
                response = Message(
                    workflow_id=message.workflow_id,
                    step_id=message.step_id,
                    from_agent=self.agent_name,
                    to_agent=message.from_agent,
                    action="escalate",
                    payload={"error": str(e), "retry_attempts": self.error_count},
                    status=AgentStatus.ESCALATED.value
                )
            
            self._log_message(response, direction="outgoing")
            return response
    
    def update_state(self, key: str, value: Any) -> None:
        """
        Update agent state.
        
        Args:
            key: State key
            value: State value
        """
        self.state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Retrieve agent state.
        
        Args:
            key: State key
            default: Default value if key not found
            
        Returns:
            State value or default
        """
        return self.state.get(key, default)
    
    def _log_message(self, message: Message, direction: str = "internal") -> None:
        """
        Log message for audit trail.
        
        Args:
            message: Message to log
            direction: "incoming", "outgoing", or "internal"
        """
        log_entry = {
            "agent": self.agent_name,
            "direction": direction,
            "message": message.to_dict(),
            "logged_at": datetime.utcnow().isoformat()
        }
        self.message_history.append(log_entry)
    
    def get_message_history(self) -> list:
        """
        Retrieve message history for this agent.
        
        Returns:
            List of logged messages
        """
        return self.message_history
    
    def clear_history(self) -> None:
        """Clear message history for this session."""
        self.message_history = []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize agent state to dictionary.
        
        Returns:
            Dictionary representation of agent
        """
        return {
            "agent_name": self.agent_name,
            "state": self.state,
            "error_count": self.error_count,
            "message_count": len(self.message_history)
        }
