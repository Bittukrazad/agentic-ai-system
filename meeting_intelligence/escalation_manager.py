"""meeting_intelligence/escalation_manager.py — Escalates stalled tasks"""
from datetime import datetime, timezone
from typing import Dict, List

from tools.slack_tool import SlackTool
from tools.email_tool import EmailTool
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit  = AuditLogger()

MANAGER_EMAIL = "manager@company.com"
MANAGER_SLACK = "#manager-alerts"


class EscalationManager:
    """
    3-level escalation for stalled tasks:
      L1 (escalation_count=0) — Reminder DM to original owner
      L2 (escalation_count=1) — Re-assign to manager + alert
      L3 (escalation_count=2+) — Critical alert to all stakeholders

    Every level:
      - Sends Slack message with interactive buttons
      - Sends email notification
      - Logs to audit trail
    """

    def __init__(self):
        self.slack = SlackTool()
        self.email = EmailTool()

    async def escalate(self, task: Dict, workflow_id: str):
        """Run escalation sequence for a single stalled task"""
        task_id        = task.get("id", "unknown")
        title          = task.get("title", "Unknown task")
        owner          = task.get("owner", "Unknown")
        escalation_count = task.get("escalation_count", 0)

        logger.warning(
            f"Escalating task={task_id} | owner={owner} | "
            f"level=L{escalation_count + 1}"
        )

        if escalation_count == 0:
            await self._level1_remind_owner(task, workflow_id)
        elif escalation_count == 1:
            await self._level2_reassign_manager(task, workflow_id)
        else:
            await self._level3_critical_alert(task, workflow_id)

        # Update escalation metadata
        task["escalation_count"]    = escalation_count + 1
        task["last_escalated_at"]   = datetime.now(timezone.utc).isoformat()

        audit.log(
            agent_id="escalation_manager",
            action="TASK_ESCALATED",
            workflow_id=workflow_id,
            step_name="escalate",
            input_summary=f"task={task_id} | owner={owner} | attempt={escalation_count + 1}",
            output_summary=f"escalation_level=L{escalation_count + 1}",
            confidence=1.0,
        )

    # ── L1: Remind original owner ─────────────────────────────────────────────

    async def _level1_remind_owner(self, task: Dict, workflow_id: str):
        """L1 — Send reminder DM to original owner with Mark Done button"""
        owner_slack = task.get("owner_slack", MANAGER_SLACK)
        owner_email = task.get("owner_email", MANAGER_EMAIL)
        owner_name  = task.get("owner", "Team member")
        title       = task.get("title", "task")
        deadline    = task.get("deadline", "")[:10]
        task_id     = task.get("id", "unknown")

        slack_msg = (
            f"Reminder — your task is overdue\n"
            f"Task: {title}\n"
            f"Original deadline: {deadline}\n"
            f"Workflow: {workflow_id}\n\n"
            f"Please update status:\n"
            f"  Reply 'done {task_id}' if complete\n"
            f"  Reply 'help {task_id}' if you need assistance"
        )
        email_body = (
            f"Hi {owner_name},\n\n"
            f"This is a reminder that the following task is overdue:\n\n"
            f"Task: {title}\n"
            f"Original deadline: {deadline}\n"
            f"Workflow: {workflow_id}\n\n"
            f"Please complete the task or let your manager know if you need help.\n\n"
            f"Agentic AI System"
        )

        # Send Slack with interactive button
        await self.slack.send_escalation(task, workflow_id, level=1)

        # Send email as backup
        await self.email.send(
            to=owner_email,
            subject=f"[Reminder] Task overdue: {title}",
            body=email_body,
        )

        logger.info(f"L1 reminder sent | task={task_id} | owner={owner_name} | slack={owner_slack}")

    # ── L2: Re-assign to manager ──────────────────────────────────────────────

    async def _level2_reassign_manager(self, task: Dict, workflow_id: str):
        """L2 — Re-assign to manager, notify both owner and manager"""
        original_owner       = task.get("owner", "Unknown")
        original_owner_slack = task.get("owner_slack", "")
        original_owner_email = task.get("owner_email", MANAGER_EMAIL)
        title                = task.get("title", "task")
        deadline             = task.get("deadline", "")[:10]
        task_id              = task.get("id", "unknown")

        # Re-assign ownership to manager
        task["owner"]       = "Manager"
        task["owner_email"] = MANAGER_EMAIL
        task["owner_slack"] = MANAGER_SLACK

        # Notify manager via Slack with buttons
        await self.slack.send_escalation(task, workflow_id, level=2)

        # Also notify manager via email
        await self.email.send(
            to=MANAGER_EMAIL,
            subject=f"[Action Required] Task re-assigned to you: {title}",
            body=(
                f"Hi Manager,\n\n"
                f"The following task has been re-assigned to you because "
                f"the original owner did not respond:\n\n"
                f"Task: {title}\n"
                f"Original owner: {original_owner}\n"
                f"Original deadline: {deadline}\n"
                f"Workflow: {workflow_id}\n\n"
                f"Please take action immediately.\n\n"
                f"Agentic AI System"
            ),
        )

        # Notify original owner that task was re-assigned
        if original_owner_slack:
            await self.slack.send(
                channel=original_owner_slack,
                message=(
                    f"Your task has been re-assigned to the manager "
                    f"due to no response.\n"
                    f"Task: {title}\n"
                    f"Please coordinate with your manager."
                ),
            )

        logger.warning(
            f"L2 re-assign | task={task_id} | "
            f"{original_owner} → Manager"
        )

    # ── L3: Critical alert ────────────────────────────────────────────────────

    async def _level3_critical_alert(self, task: Dict, workflow_id: str):
        """L3 — Critical alert to manager channel and all stakeholders"""
        title     = task.get("title", "task")
        owner     = task.get("owner", "Unknown")
        deadline  = task.get("deadline", "")[:10]
        task_id   = task.get("id", "unknown")
        esc_count = task.get("escalation_count", 2)

        # Send critical escalation to manager channel
        await self.slack.send_escalation(task, workflow_id, level=3)

        # Send critical email
        await self.email.send(
            to=MANAGER_EMAIL,
            subject=f"[CRITICAL] Escalation #{esc_count + 1}: {title}",
            body=(
                f"CRITICAL ESCALATION\n\n"
                f"Task: {title}\n"
                f"Current owner: {owner}\n"
                f"Original deadline: {deadline}\n"
                f"Escalation count: {esc_count + 1}\n"
                f"Workflow: {workflow_id}\n\n"
                f"This task has been escalated {esc_count + 1} times "
                f"with no resolution. Immediate action required.\n\n"
                f"Agentic AI System"
            ),
        )

        logger.error(
            f"L3 critical escalation | task={task_id} | "
            f"owner={owner} | count={esc_count + 1}"
        )

    # ── Batch escalation ──────────────────────────────────────────────────────

    async def escalate_all_stalled(self, stalled_tasks: List[Dict], workflow_id: str):
        """Escalate all stalled tasks in a workflow"""
        if not stalled_tasks:
            return
        logger.warning(
            f"Running batch escalation | "
            f"workflow={workflow_id} | count={len(stalled_tasks)}"
        )
        for task in stalled_tasks:
            await self.escalate(task, workflow_id)