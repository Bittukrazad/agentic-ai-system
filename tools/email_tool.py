"""tools/email_tool.py — SMTP email integration"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class EmailTool:
    """
    Sends emails via SMTP (Gmail, SendGrid, etc.).
    Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in .env.
    Without credentials, emails are logged locally (demo/dev mode).
    """

    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASS", "")
        self.enabled = bool(self.user and self.password)

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        html: bool = False,
    ) -> Dict:
        """Send an email. Falls back to logging in dev mode."""
        if not self.enabled:
            logger.info(f"[EMAIL MOCK] To: {to} | Subject: {subject}\n{body[:100]}")
            return {"ok": True, "mock": True, "to": to}

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.user
            msg["To"] = to
            if cc:
                msg["Cc"] = ", ".join(cc)

            mime_type = "html" if html else "plain"
            msg.attach(MIMEText(body, mime_type))

            with smtplib.SMTP(self.host, self.port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.user, self.password)
                recipients = [to] + (cc or [])
                server.sendmail(self.user, recipients, msg.as_string())

            logger.info(f"Email sent | to={to} | subject={subject[:40]}")
            return {"ok": True, "to": to}

        except Exception as e:
            logger.error(f"Email send failed | to={to} | error={e}")
            return {"ok": False, "error": str(e)}