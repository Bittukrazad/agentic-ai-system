"""agents/action_agent.py — Executes real-world actions via tools"""
from typing import Any, Dict

from agents.base_agent import BaseAgent
from tools.slack_tool import SlackTool
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.db_tool import DBTool


class ActionAgent(BaseAgent):
    """
    Translates decisions into real-world actions.
    Uses: Slack, email, calendar, database writes.
    """

    def __init__(self):
        super().__init__()
        self.slack = SlackTool()
        self.email = EmailTool()
        self.calendar = CalendarTool()
        self.db = DBTool()

    async def execute(self, action_type: str, params: Dict, state) -> Dict[str, Any]:
        """Execute the specified action type"""
        workflow_id = state.workflow_id
        self.logger.info(f"Executing action | type={action_type} | workflow={workflow_id}")

        result = {}
        if action_type == "send_slack":
            result = await self._send_slack(params, workflow_id)
        elif action_type == "send_email":
            result = await self._send_email(params, workflow_id)
        elif action_type == "create_calendar_event":
            result = await self._create_calendar_event(params, workflow_id)
        elif action_type == "write_db":
            result = await self._write_db(params, workflow_id)
        elif action_type == "provision_access":
            result = await self._provision_access(params, state, workflow_id)
        elif action_type == "create_purchase_order":
            result = await self._create_po(params, workflow_id)
        elif action_type == "send_contract":
            result = await self._send_contract(params, workflow_id)
        else:
            result = {"status": "skipped", "reason": f"unknown action type: {action_type}"}

        self.log_action(
            action="ACTION_EXECUTED",
            workflow_id=workflow_id,
            step_name=action_type,
            input_summary=str(params)[:80],
            output_summary=str(result)[:80],
            confidence=1.0 if result.get("status") == "ok" else 0.5,
        )
        return result

    async def notify_task_owner(self, task: Dict, workflow_id: str) -> Dict:
        """Notify an owner about a newly assigned task (meeting intelligence)"""
        owner = task.get("owner", "team@company.com")
        title = task.get("title", "New task assigned")
        deadline = task.get("deadline", "TBD")

        # Try Slack first, fall back to email
        slack_result = await self.slack.send(
            channel=f"@{owner.split('@')[0]}",
            message=f"*New task assigned to you*\n*Task:* {title}\n*Deadline:* {deadline}\n*Workflow:* {workflow_id}",
        )
        if not slack_result.get("ok"):
            await self.email.send(
                to=owner,
                subject=f"Task assigned: {title}",
                body=f"You have been assigned a task:\n\nTitle: {title}\nDeadline: {deadline}\nWorkflow ID: {workflow_id}",
            )

        self.log_action(
            action="TASK_OWNER_NOTIFIED",
            workflow_id=workflow_id,
            step_name="notify_task_owner",
            input_summary=f"task={title[:40]} owner={owner}",
            output_summary="notification sent",
            confidence=1.0,
        )
        return {"status": "ok", "notified": owner}

    async def _send_slack(self, params: Dict, workflow_id: str) -> Dict:
        return await self.slack.send(
            channel=params.get("channel", "#enterprise-alerts"),
            message=params.get("message", "Workflow update"),
        )

    async def _send_email(self, params: Dict, workflow_id: str) -> Dict:
        return await self.email.send(
            to=params.get("to", "team@company.com"),
            subject=params.get("subject", "Workflow notification"),
            body=params.get("body", ""),
        )

    async def _create_calendar_event(self, params: Dict, workflow_id: str) -> Dict:
        return await self.calendar.create_event(
            title=params.get("title", "Meeting"),
            attendees=params.get("attendees", []),
            start=params.get("start", ""),
            duration_minutes=params.get("duration_minutes", 60),
        )

    async def _write_db(self, params: Dict, workflow_id: str) -> Dict:
        return self.db.write(
            table=params.get("table", "workflow_records"),
            data={**params.get("data", {}), "workflow_id": workflow_id},
        )

    async def _provision_access(self, params: Dict, state, workflow_id: str) -> Dict:
        employee = state.fetched_data.get("employee_db", {})
        self.logger.info(f"Provisioning access for {employee.get('name', 'employee')}")
        systems = params.get("systems", ["email", "slack", "github", "jira"])
        return {
            "status": "ok",
            "provisioned": systems,
            "employee": employee.get("name", ""),
            "note": "Access provisioning simulated (integrate with your IAM system)",
        }

    async def _create_po(self, params: Dict, workflow_id: str) -> Dict:
        return {
            "status": "ok",
            "po_number": f"PO-{workflow_id[:8].upper()}",
            "amount": params.get("amount", 0),
            "vendor": params.get("vendor_name", ""),
        }

    async def _send_contract(self, params: Dict, workflow_id: str) -> Dict:
        return await self.email.send(
            to=params.get("counterparty_email", "legal@partner.com"),
            subject=f"Contract for review: {params.get('contract_id', '')}",
            body=f"Please review and sign the attached contract.\nWorkflow: {workflow_id}",
        )