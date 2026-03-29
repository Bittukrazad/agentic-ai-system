"""health_monitoring/alert_manager.py — Sends health alerts via Slack and email"""
import asyncio
from datetime import datetime, timezone
from typing import Dict

from tools.slack_tool import SlackTool
from tools.email_tool import EmailTool
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()


class AlertManager:
    """
    Sends structured alerts when health monitors detect issues.
    Alert levels: INFO | WARNING | CRITICAL
    Channels: Slack (real-time) + Email (formal record)
    """

    def __init__(self):
        self.slack = SlackTool()
        self.email = EmailTool()

    async def send_drift_alert(self, workflow_id: str, drift_info: Dict):
        step = drift_info.get("step", "unknown")
        overrun = drift_info.get("overrun_factor", 1.0)
        msg = (f"*[WARNING] Process Drift Detected*\n"
               f"Workflow: `{workflow_id}`\n"
               f"Step: `{step}` is running {overrun:.1f}x slower than baseline\n"
               f"Action: Monitoring for SLA breach risk")
        await self._send(workflow_id, msg, "drift_alert", level="WARNING")

    async def send_breach_alert(self, workflow_id: str, probability: float, remaining_minutes: float):
        msg = (f"*[CRITICAL] SLA Breach Risk*\n"
               f"Workflow: `{workflow_id}`\n"
               f"Breach probability: {probability:.0%}\n"
               f"Time remaining: {remaining_minutes:.0f} minutes\n"
               f"Action: Workflow has been rerouted to skip non-critical steps")
        await self._send(workflow_id, msg, "breach_alert", level="CRITICAL")

    async def send_anomaly_alert(self, workflow_id: str, anomalies: list):
        summary = ", ".join(f"{a['metric']}={a['value']}" for a in anomalies)
        msg = (f"*[WARNING] Workflow Anomalies Detected*\n"
               f"Workflow: `{workflow_id}`\n"
               f"Anomalies: {summary}\n"
               f"Action: Increased monitoring activated")
        await self._send(workflow_id, msg, "anomaly_alert", level="WARNING")

    async def send_completion_summary(self, workflow_id: str, stats: Dict):
        msg = (f"*[INFO] Workflow Completed*\n"
               f"Workflow: `{workflow_id}`\n"
               f"Steps completed: {stats.get('completed_steps', 0)}\n"
               f"Tasks created: {stats.get('tasks_count', 0)}\n"
               f"Retries used: {stats.get('total_retries', 0)}\n"
               f"SLA status: {'BREACHED' if stats.get('sla_breached') else 'OK'}")
        await self._send(workflow_id, msg, "completion_summary", level="INFO")

    async def _send(self, workflow_id: str, message: str, alert_type: str, level: str = "INFO"):
        from app.config import config
        channel = config.SLACK_CHANNEL

        slack_result = await self.slack.send(channel=channel, message=message)
        if not slack_result.get("ok"):
            await self.email.send(
                to=config.SMTP_USER or "admin@company.com",
                subject=f"[{level}] Agentic AI Alert: {alert_type}",
                body=message,
            )

        logger.info(f"Alert sent | type={alert_type} level={level} workflow={workflow_id}")
        audit.log(
            agent_id="alert_manager",
            action="ALERT_SENT",
            workflow_id=workflow_id,
            step_name=alert_type,
            output_summary=f"level={level} channel={channel}",
            confidence=1.0,
        )