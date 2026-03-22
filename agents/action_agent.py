"""
Action Agent Module - Responsible for executing autonomous actions and operations.

This agent handles:
- Sending emails and communications
- Creating/updating database records
- Sending Slack messages
- Calendar management
- API operations
- Task execution
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
from base_agent import BaseAgent, Message, AgentStatus


class ActionAgent(BaseAgent):
    """
    Action Agent for autonomous execution of operations and tasks.
    
    Capabilities:
    - Send emails
    - Create/update records
    - Send messages (Slack, Teams)
    - Manage calendars
    - Execute API calls
    - Create tasks and workflows
    - Generate documents
    """
    
    def __init__(self, agent_name: str = "action_agent", max_retries: int = 3):
        """
        Initialize Action Agent.
        
        Args:
            agent_name: Agent identifier
            max_retries: Maximum retry attempts
        """
        super().__init__(agent_name, max_retries)
        self.action_log = []
        self.execution_status = {}
    
    def process_message(self, message: Message) -> Message:
        """
        Process incoming action request message.
        
        Supported actions:
        - send_email: Send email to recipient
        - send_slack_message: Send message to Slack
        - create_record: Create database record
        - update_record: Update database record
        - schedule_calendar_event: Add calendar event
        - execute_task: Execute workflow task
        - generate_document: Generate document
        - notify_user: Send user notification
        
        Args:
            message: Incoming message with action request
            
        Returns:
            Message: Response with action result
        """
        action = message.action
        payload = message.payload
        
        try:
            execution_id = f"exec_{message.workflow_id}_{message.step_id}_{datetime.utcnow().timestamp()}"
            
            if action == "send_email":
                result = self._send_email(payload)
            
            elif action == "send_slack_message":
                result = self._send_slack_message(payload)
            
            elif action == "create_record":
                result = self._create_record(payload)
            
            elif action == "update_record":
                result = self._update_record(payload)
            
            elif action == "schedule_calendar_event":
                result = self._schedule_calendar_event(payload)
            
            elif action == "execute_task":
                result = self._execute_task(payload)
            
            elif action == "generate_document":
                result = self._generate_document(payload)
            
            elif action == "notify_user":
                result = self._notify_user(payload)
            
            elif action == "get_action_status":
                result = self._get_action_status(payload)
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            # Log action execution
            self._log_action(execution_id, action, payload, result)
            self.execution_status[execution_id] = "completed"
            
            response = Message(
                workflow_id=message.workflow_id,
                step_id=message.step_id,
                from_agent=self.agent_name,
                to_agent=message.from_agent,
                action=f"{action}_response",
                payload={
                    "result": result,
                    "execution_id": execution_id,
                    "action": action
                },
                status=AgentStatus.SUCCESS.value
            )
            
            return response
        
        except Exception as e:
            raise Exception(f"Action execution error: {str(e)}")
    
    def _send_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send email to recipient.
        
        Args:
            payload: Email details (to, subject, body, etc.)
            
        Returns:
            Email send confirmation
        """
        recipient = payload.get("to")
        subject = payload.get("subject")
        body = payload.get("body")
        cc = payload.get("cc", [])
        bcc = payload.get("bcc", [])
        attachments = payload.get("attachments", [])
        
        # Simulated email sending
        email_id = f"email_{datetime.utcnow().timestamp()}"
        
        result = {
            "email_id": email_id,
            "status": "sent",
            "recipient": recipient,
            "cc": cc,
            "subject": subject,
            "sent_at": datetime.utcnow().isoformat(),
            "attachments_count": len(attachments)
        }
        
        return result
    
    def _send_slack_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send message to Slack channel or user.
        
        Args:
            payload: Message details (channel, text, blocks, etc.)
            
        Returns:
            Slack message confirmation
        """
        channel = payload.get("channel")
        text = payload.get("text")
        blocks = payload.get("blocks", [])
        thread_ts = payload.get("thread_ts")
        
        # Simulated Slack message
        message_id = f"slack_{datetime.utcnow().timestamp()}"
        
        result = {
            "message_id": message_id,
            "status": "posted",
            "channel": channel,
            "text": (text or "")[:50],  # First 50 chars
            "posted_at": datetime.utcnow().isoformat(),
            "thread": thread_ts if thread_ts else None
        }
        
        return result
    
    def _create_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new database record.
        
        Args:
            payload: Record data and metadata
            
        Returns:
            Created record confirmation
        """
        record_type = payload.get("record_type")
        data = payload.get("data", {})
        
        # Generate record ID based on type
        record_id = f"{(record_type or 'rec')[:3]}_{int(datetime.utcnow().timestamp())}"
        
        result = {
            "record_id": record_id,
            "record_type": record_type,
            "status": "created",
            "data_keys": list(data.keys()),
            "created_at": datetime.utcnow().isoformat()
        }
        
        return result
    
    def _update_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing database record.
        
        Args:
            payload: Record ID and updated data
            
        Returns:
            Update confirmation
        """
        record_id = payload.get("record_id")
        record_type = payload.get("record_type")
        updates = payload.get("updates", {})
        
        result = {
            "record_id": record_id,
            "record_type": record_type,
            "status": "updated",
            "fields_updated": list(updates.keys()),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        return result
    
    def _schedule_calendar_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule a calendar event.
        
        Args:
            payload: Event details (title, start, end, attendees, etc.)
            
        Returns:
            Event creation confirmation
        """
        title = payload.get("title")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        attendees = payload.get("attendees", [])
        location = payload.get("location")
        
        # Simulated calendar event
        event_id = f"evt_{datetime.utcnow().timestamp()}"
        
        result = {
            "event_id": event_id,
            "status": "scheduled",
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "attendees_count": len(attendees),
            "location": location,
            "created_at": datetime.utcnow().isoformat()
        }
        
        return result
    
    def _execute_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a workflow task.
        
        Args:
            payload: Task specification and parameters
            
        Returns:
            Task execution result
        """
        task_id = payload.get("task_id")
        task_type = payload.get("task_type")
        parameters = payload.get("parameters", {})
        
        # Simulated task execution
        result = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "executed",
            "parameters_used": list(parameters.keys()),
            "executed_at": datetime.utcnow().isoformat(),
            "output": {}
        }
        
        # Type-specific execution
        if task_type == "approval_workflow":
            result["output"] = self._execute_approval_workflow(parameters)
        elif task_type == "data_processing":
            result["output"] = self._execute_data_processing(parameters)
        elif task_type == "notification":
            result["output"] = self._execute_notification_task(parameters)
        
        return result
    
    def _execute_approval_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute approval workflow task."""
        return {
            "workflow_started": True,
            "approvers": params.get("approvers", []),
            "routing": params.get("routing", "sequential")
        }
    
    def _execute_data_processing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data processing task."""
        return {
            "processing_type": params.get("type"),
            "records_processed": params.get("record_count", 0),
            "status": "completed"
        }
    
    def _execute_notification_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute notification task."""
        return {
            "notification_type": params.get("type"),
            "recipients": len(params.get("recipients", [])),
            "sent": True
        }
    
    def _generate_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a document.
        
        Args:
            payload: Document specification (type, template, data, etc.)
            
        Returns:
            Document generation confirmation
        """
        doc_type = payload.get("document_type")
        template = payload.get("template")
        data = payload.get("data", {})
        format_type = payload.get("format", "pdf")
        
        # Simulated document generation
        doc_id = f"doc_{datetime.utcnow().timestamp()}"
        
        result = {
            "document_id": doc_id,
            "document_type": doc_type,
            "status": "generated",
            "format": format_type,
            "template_used": template,
            "data_fields": list(data.keys()),
            "generated_at": datetime.utcnow().isoformat(),
            "size_bytes": 1024
        }
        
        return result
    
    def _notify_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notification to user.
        
        Args:
            payload: Notification details
            
        Returns:
            Notification confirmation
        """
        user_id = payload.get("user_id")
        notification_type = payload.get("notification_type")
        message = payload.get("message")
        channels = payload.get("channels", ["email"])
        
        # Simulated notification
        notification_id = f"notif_{datetime.utcnow().timestamp()}"
        
        result = {
            "notification_id": notification_id,
            "user_id": user_id,
            "type": notification_type,
            "channels": channels,
            "status": "sent",
            "message_length": len(message or ""),
            "sent_at": datetime.utcnow().isoformat()
        }
        
        return result
    
    def _get_action_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get status of previously executed action.
        
        Args:
            payload: Action/execution ID to check
            
        Returns:
            Action status
        """
        execution_id = payload.get("execution_id")
        
        status = self.execution_status.get(execution_id, "not_found")
        
        return {
            "execution_id": execution_id,
            "status": status,
            "checked_at": datetime.utcnow().isoformat()
        }
    
    def _log_action(self, execution_id: str, action: str, 
                   payload: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Log action execution for audit trail.
        
        Args:
            execution_id: Unique execution identifier
            action: Action performed
            payload: Input payload
            result: Execution result
        """
        log_entry = {
            "execution_id": execution_id,
            "action": action,
            "payload_keys": list(payload.keys()),
            "result": result,
            "logged_at": datetime.utcnow().isoformat()
        }
        self.action_log.append(log_entry)
    
    def get_action_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent action logs.
        
        Args:
            limit: Maximum number of logs to return
            
        Returns:
            Recent action logs
        """
        return self.action_log[-limit:]
    
    def clear_action_log(self) -> None:
        """Clear action log."""
        self.action_log = []
