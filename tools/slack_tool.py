"""tools/slack_tool.py — Slack API integration with interactive buttons"""
import os
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SlackTool:
    """
    Sends messages to Slack channels and DMs.
    - With real SLACK_BOT_TOKEN: sends actual Slack messages with buttons
    - Without token: logs messages locally (demo/dev mode)

    Supports:
      - Plain text messages
      - Rich formatted messages
      - Interactive button messages (Mark Done / In Progress / Need Help)
      - Task assignment notifications
      - Escalation alerts
      - Manager summary messages
    """

    def __init__(self):
        self.token   = os.getenv("SLACK_BOT_TOKEN", "")
        self.channel = os.getenv("SLACK_CHANNEL", "#enterprise-alerts")
        self.esc_ch  = os.getenv("SLACK_ESCALATION_CHANNEL", "#manager-alerts")
        self.health  = os.getenv("SLACK_HEALTH_CHANNEL", "#workflow-health")
        self._client = None

        if self.token and self.token.startswith("xoxb-"):
            try:
                from slack_sdk.web.async_client import AsyncWebClient
                self._client = AsyncWebClient(token=self.token)
                logger.info("Slack client initialised with real token")
            except ImportError:
                logger.warning("slack_sdk not installed — using HTTP fallback")

    # ── Core send ─────────────────────────────────────────────────────────────

    async def send(self, channel: str, message: str, blocks: Optional[List] = None) -> Dict:
        """Send a plain or block-kit message"""
        if self._client:
            try:
                response = await self._client.chat_postMessage(
                    channel=channel,
                    text=message,
                    blocks=blocks,
                )
                return {"ok": True, "ts": response.get("ts")}
            except Exception as e:
                logger.warning(f"Slack API error: {e}")
                return {"ok": False, "error": str(e)}

        # Dev / demo mode — log instead of sending
        logger.info(f"[SLACK MOCK] → {channel}\n{message}")
        return {"ok": True, "mock": True, "channel": channel}

    # ── Task assignment message with buttons ──────────────────────────────────

    async def send_task_assignment(
        self,
        task: Dict,
        workflow_id: str,
    ) -> Dict:
        """
        Send a task assignment DM to the owner with interactive buttons.
        Employee sees:  [✅ Mark Done]  [🔄 In Progress]  [⚠️ Need Help]
        """
        owner_slack = task.get("owner_slack", self.channel)
        title       = task.get("title", "Task assigned")
        deadline    = task.get("deadline", "No deadline set")
        task_id     = task.get("id", "unknown")
        owner_name  = task.get("owner", "Team member")
        priority    = task.get("priority", "medium").upper()

        # Format deadline nicely
        try:
            from datetime import datetime
            dl = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            deadline_str = dl.strftime("%A, %d %B %Y at %I:%M %p")
        except Exception:
            deadline_str = deadline

        plain_msg = (
            f"New task assigned to you\n"
            f"Task: {title}\n"
            f"Deadline: {deadline_str}\n"
            f"Priority: {priority}\n"
            f"Workflow: {workflow_id}\n\n"
            f"Reply with:\n"
            f"  done {task_id}        — to mark complete\n"
            f"  progress {task_id}    — to mark in progress\n"
            f"  help {task_id}        — to request help"
        )

        # Block Kit — rich interactive message (only used with real token)
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "New Task Assigned"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Hi *{owner_name}*! You have a new task:\n\n"
                        f"*{title}*"
                    ),
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Deadline:*\n{deadline_str}"},
                    {"type": "mrkdwn", "text": f"*Priority:*\n{priority}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Mark Done"},
                        "style": "primary",
                        "value": f"done|{task_id}|{workflow_id}",
                        "action_id": "task_done",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "In Progress"},
                        "value": f"progress|{task_id}|{workflow_id}",
                        "action_id": "task_progress",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Need Help"},
                        "style": "danger",
                        "value": f"help|{task_id}|{workflow_id}",
                        "action_id": "task_help",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Task ID: `{task_id}` | Workflow: `{workflow_id[:12]}...`"},
                ],
            },
        ]

        logger.info(f"[SLACK] Task assignment → {owner_slack} | task={task_id} | owner={owner_name}")
        return await self.send(channel=owner_slack, message=plain_msg, blocks=blocks)

    # ── Manager summary ───────────────────────────────────────────────────────

    async def send_manager_summary(
        self,
        tasks: List[Dict],
        workflow_id: str,
        meeting_title: str = "Meeting",
    ) -> Dict:
        """
        Send a summary of all tasks to the manager channel.
        Manager sees all tasks, owners, and deadlines in one message.
        """
        total   = len(tasks)
        summary = "\n".join(
            f"  • {t.get('title','')[:60]} → *{t.get('owner','?')}* (due {t.get('deadline','?')[:10]})"
            for t in tasks
        )

        plain_msg = (
            f"Meeting processed: {meeting_title}\n"
            f"Total tasks created: {total}\n\n"
            f"{summary}\n\n"
            f"Workflow ID: {workflow_id}"
        )

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Meeting Intelligence — {total} Tasks Created"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Meeting:* {meeting_title}\n*Tasks extracted:* {total}"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary},
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Workflow: `{workflow_id[:12]}...` | View dashboard: http://localhost:8501"},
                ],
            },
        ]

        logger.info(f"[SLACK] Manager summary → {self.channel} | tasks={total}")
        return await self.send(channel=self.channel, message=plain_msg, blocks=blocks)

    # ── Escalation alerts ─────────────────────────────────────────────────────

    async def send_escalation(
        self,
        task: Dict,
        workflow_id: str,
        level: int = 1,
    ) -> Dict:
        """Send escalation alert to manager channel"""
        title        = task.get("title", "Unknown task")
        owner        = task.get("owner", "Unknown")
        deadline     = task.get("deadline", "unknown")[:10]
        esc_count    = task.get("escalation_count", 0) + 1

        level_labels = {1: "Reminder", 2: "Re-assigned to Manager", 3: "CRITICAL — Immediate Action"}
        level_emoji  = {1: "warning", 2: "rotating_light", 3: "fire"}

        label = level_labels.get(level, "Escalation")

        plain_msg = (
            f"ESCALATION L{level}: {label}\n"
            f"Task: {title}\n"
            f"Original owner: {owner}\n"
            f"Original deadline: {deadline}\n"
            f"Escalation count: {esc_count}\n"
            f"Workflow: {workflow_id}"
        )

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Escalation L{level} — {label}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Task:*\n{title}"},
                    {"type": "mrkdwn", "text": f"*Original owner:*\n{owner}"},
                    {"type": "mrkdwn", "text": f"*Deadline:*\n{deadline}"},
                    {"type": "mrkdwn", "text": f"*Escalation count:*\n{esc_count}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Mark Done"},
                        "style": "primary",
                        "value": f"done|{task.get('id','?')}|{workflow_id}",
                        "action_id": "task_done",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reassign"},
                        "value": f"reassign|{task.get('id','?')}|{workflow_id}",
                        "action_id": "task_reassign",
                    },
                ],
            },
        ]

        logger.warning(f"[SLACK] Escalation L{level} → {self.esc_ch} | task={task.get('id')} | owner={owner}")
        return await self.send(channel=self.esc_ch, message=plain_msg, blocks=blocks)

    # ── Health alerts ─────────────────────────────────────────────────────────

    async def send_health_alert(self, alert_type: str, message: str) -> Dict:
        """Send SLA drift or health alert to health channel"""
        plain_msg = f"[{alert_type}] {message}"
        logger.info(f"[SLACK] Health alert → {self.health} | {alert_type}")
        return await self.send(channel=self.health, message=plain_msg)

    # ── Legacy rich send (backwards compatible) ───────────────────────────────

    async def send_rich(self, channel: str, title: str, body: str, color: str = "#534AB7") -> Dict:
        """Send a formatted message — kept for backwards compatibility"""
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n{body}"},
            }
        ]
        return await self.send(channel=channel, message=f"{title}\n{body}", blocks=blocks)