"""
Audit Logger Module - Append-only audit trail for compliance and debugging.

Provides:
- Trace log (all operations)
- Decision log (autonomous decisions only)
- Structured JSONL format
- UUID tracking for root cause analysis
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid
from utils.helpers import append_jsonl_file, load_jsonl_file, get_iso_now


class AuditLogger:
    """
    Centralized audit logging system for complete system transparency.
    
    Maintains two append-only streams:
    1. trace_logs.jsonl - All operations and state changes
    2. decision_logs.jsonl - Only autonomous decision reasoning
    """
    
    def __init__(self, trace_log_file: str, decision_log_file: str):
        """
        Initialize audit logger.
        
        Args:
            trace_log_file: Path to trace logs (JSONL format)
            decision_log_file: Path to decision logs (JSONL format)
        """
        self.trace_log_file = trace_log_file
        self.decision_log_file = decision_log_file
        
        # Ensure files and directories exist
        Path(trace_log_file).parent.mkdir(parents=True, exist_ok=True)
        Path(decision_log_file).parent.mkdir(parents=True, exist_ok=True)
        
        if not Path(trace_log_file).exists():
            Path(trace_log_file).touch()
        if not Path(decision_log_file).exists():
            Path(decision_log_file).touch()
    
    def log_message_sent(
        self,
        message_id: str,
        workflow_id: str,
        from_agent: str,
        to_agent: str,
        action: str,
        payload: Dict[str, Any],
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log outgoing message.
        
        Args:
            message_id: Unique message identifier
            workflow_id: Workflow ID
            from_agent: Sender agent
            to_agent: Recipient agent
            action: Action being performed
            payload: Message payload
            parent_trace_id: Parent trace ID for root cause analysis
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "message_sent",
            "message_id": message_id,
            "workflow_id": workflow_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "action": action,
            "payload_summary": self._summarize_payload(payload)
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_message_received(
        self,
        message_id: str,
        workflow_id: str,
        agent: str,
        action: str,
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log incoming message at agent.
        
        Args:
            message_id: Unique message identifier
            workflow_id: Workflow ID
            agent: Receiving agent
            action: Action expected
            parent_trace_id: Parent trace ID
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "message_received",
            "message_id": message_id,
            "workflow_id": workflow_id,
            "agent": agent,
            "action": action
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_agent_action(
        self,
        workflow_id: str,
        step_id: str,
        agent: str,
        action: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        status: str,
        duration_seconds: float,
        parent_trace_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> str:
        """
        Log agent action execution.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            agent: Agent name
            action: Action performed
            inputs: Input parameters
            outputs: Output results
            status: Execution status (success, failed, etc.)
            duration_seconds: Execution time
            parent_trace_id: Parent trace ID
            error: Error message if failed
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "agent_action",
            "workflow_id": workflow_id,
            "step_id": step_id,
            "agent": agent,
            "action": action,
            "inputs_summary": self._summarize_payload(inputs),
            "outputs_summary": self._summarize_payload(outputs),
            "status": status,
            "duration_seconds": round(duration_seconds, 3),
            "error": error
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_decision(
        self,
        workflow_id: str,
        step_id: str,
        agent: str,
        decision_type: str,
        context: Dict[str, Any],
        decision_result: Dict[str, Any],
        reasoning: str,
        confidence_score: Optional[float] = None,
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log autonomous decision (for decision_logs.jsonl).
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            agent: Decision-making agent
            decision_type: Type of decision
            context: Context for decision
            decision_result: Actual decision made
            reasoning: Explanation of reasoning
            confidence_score: Confidence level (0-1)
            parent_trace_id: Parent trace ID
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "autonomous_decision",
            "workflow_id": workflow_id,
            "step_id": step_id,
            "agent": agent,
            "decision_type": decision_type,
            "context_summary": self._summarize_payload(context),
            "decision_result": decision_result,
            "reasoning": reasoning,
            "confidence_score": confidence_score
        }
        
        # Log to both traces and decisions
        append_jsonl_file(self.trace_log_file, log_entry)
        append_jsonl_file(self.decision_log_file, log_entry)
        
        return trace_id
    
    def log_workflow_step(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        status: str,
        start_time: str,
        end_time: Optional[str] = None,
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log workflow step execution.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            step_name: Human-readable step name
            status: Step status
            start_time: ISO start time
            end_time: ISO end time (optional)
            parent_trace_id: Parent trace ID
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "workflow_step",
            "workflow_id": workflow_id,
            "step_id": step_id,
            "step_name": step_name,
            "status": status,
            "start_time": start_time,
            "end_time": end_time
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_workflow_start(
        self,
        workflow_id: str,
        workflow_name: str,
        sla_hours: float
    ) -> str:
        """
        Log workflow execution start.
        
        Args:
            workflow_id: Workflow ID
            workflow_name: Human-readable name
            sla_hours: SLA target in hours
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "timestamp": get_iso_now(),
            "event_type": "workflow_started",
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "sla_hours": sla_hours
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_workflow_end(
        self,
        workflow_id: str,
        status: str,
        duration_seconds: float,
        error: Optional[str] = None,
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log workflow execution end.
        
        Args:
            workflow_id: Workflow ID
            status: Final status
            duration_seconds: Total execution time
            error: Error message if failed
            parent_trace_id: Root trace ID
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "workflow_ended",
            "workflow_id": workflow_id,
            "status": status,
            "duration_seconds": round(duration_seconds, 3),
            "error": error
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_retry(
        self,
        workflow_id: str,
        step_id: str,
        agent: str,
        action: str,
        attempt_number: int,
        delay_seconds: float,
        error_reason: str,
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log retry attempt.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            agent: Agent performing retry
            action: Action being retried
            attempt_number: Attempt number
            delay_seconds: Delay before retry
            error_reason: Reason for retry
            parent_trace_id: Parent trace ID
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "retry_attempt",
            "workflow_id": workflow_id,
            "step_id": step_id,
            "agent": agent,
            "action": action,
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds,
            "error_reason": error_reason
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        return trace_id
    
    def log_escalation(
        self,
        workflow_id: str,
        step_id: str,
        reason: str,
        escalated_to: str,
        parent_trace_id: Optional[str] = None
    ) -> str:
        """
        Log escalation event.
        
        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            reason: Escalation reason
            escalated_to: Escalation target
            parent_trace_id: Parent trace ID
            
        Returns:
            Trace ID for this log entry
        """
        trace_id = str(uuid.uuid4())
        
        log_entry = {
            "trace_id": trace_id,
            "parent_trace_id": parent_trace_id,
            "timestamp": get_iso_now(),
            "event_type": "escalation",
            "workflow_id": workflow_id,
            "step_id": step_id,
            "reason": reason,
            "escalated_to": escalated_to
        }
        
        append_jsonl_file(self.trace_log_file, log_entry)
        append_jsonl_file(self.decision_log_file, log_entry)
        
        return trace_id
    
    def get_trace_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get all audit logs for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            List of audit entries
        """
        all_logs = load_jsonl_file(self.trace_log_file)
        return [log for log in all_logs if log.get("workflow_id") == workflow_id]
    
    def get_decisions_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get all decisions for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            List of decision entries
        """
        all_decisions = load_jsonl_file(self.decision_log_file)
        return [dec for dec in all_decisions if dec.get("workflow_id") == workflow_id]
    
    def _summarize_payload(self, payload: Dict[str, Any], max_length: int = 100) -> str:
        """
        Create concise summary of payload for logging.
        
        Args:
            payload: Payload to summarize
            max_length: Maximum summary length
            
        Returns:
            Summarized payload
        """
        payload_str = json.dumps(payload, default=str)
        if len(payload_str) > max_length:
            return payload_str[:max_length] + "..."
        return payload_str
