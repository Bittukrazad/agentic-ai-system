"""
Email Tool - Send emails via SMTP with retry logic and logging.

Provides:
- SMTP email sending with configurable host/port
- HTML and plain text support
- CC/BCC support
- Attachment support
- Retry logic for transient failures
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional, List
from pathlib import Path
import asyncio
from utils.logger import get_logger
from app.config import Settings

logger = get_logger(__name__)


class EmailResponse:
    """Email sending response."""
    
    def __init__(
        self,
        success: bool,
        message_id: str = "",
        to: List[str] = None,
        error: str = ""
    ):
        """
        Initialize response.
        
        Args:
            success: Whether email was sent
            message_id: Email message ID
            to: Recipients list
            error: Error message if failed
        """
        self.success = success
        self.message_id = message_id
        self.to = to or []
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message_id": self.message_id,
            "to": self.to,
            "error": self.error
        }


class EmailTool:
    """
    Email sending tool with SMTP support.
    
    Features:
    - SMTP connection pooling
    - HTML and plain text
    - CC/BCC support
    - Attachments
    - Retry with exponential backoff
    """
    
    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        use_tls: bool = True,
        from_email: str = "noreply@company.com",
        max_retries: int = 3
    ):
        """
        Initialize email tool.
        
        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP user
            smtp_password: SMTP password
            use_tls: Use TLS encryption
            from_email: Sender email
            max_retries: Maximum retry attempts
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_tls = use_tls
        self.from_email = from_email
        self.max_retries = max_retries
        self.sent_count = 0
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None
    ) -> EmailResponse:
        """
        Send email asynchronously.
        
        Args:
            to: Recipient addresses
            subject: Email subject
            body: Email body
            html: Whether body is HTML
            cc: CC recipients
            bcc: BCC recipients
            attachments: Attachment paths
            
        Returns:
            EmailResponse
        """
        # Normalize inputs
        if isinstance(to, str):
            to = [to]
        cc = cc or []
        bcc = bcc or []
        attachments = attachments or []
        
        # Try sending with retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Create message
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.from_email
                msg["To"] = ", ".join(to)
                
                if cc:
                    msg["Cc"] = ", ".join(cc)
                
                # Add body
                part = MIMEText(body, "html" if html else "plain")
                msg.attach(part)
                
                # Add attachments
                for attachment_path in attachments:
                    if Path(attachment_path).exists():
                        self._attach_file(msg, attachment_path)
                
                # Send via SMTP
                all_recipients = to + cc + bcc
                await self._send_smtp(msg, all_recipients)
                
                self.sent_count += 1
                
                logger.info(
                    f"Email sent successfully",
                    extra={
                        "to": to,
                        "subject": subject,
                        "attempt": attempt + 1
                    }
                )
                
                return EmailResponse(
                    success=True,
                    message_id=msg["Subject"],
                    to=to
                )
            
            except Exception as e:
                last_error = e
                
                logger.warning(
                    f"Email send failed",
                    extra={
                        "to": to,
                        "error": str(e),
                        "attempt": attempt + 1
                    }
                )
                
                # Retry with backoff
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(
            f"Email send exhausted retries",
            extra={"to": to, "subject": subject, "error": str(last_error)}
        )
        
        return EmailResponse(
            success=False,
            to=to,
            error=str(last_error)
        )
    
    async def _send_smtp(self, message: MIMEMultipart, recipients: List[str]):
        """Send message via SMTP."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_smtp_blocking, message, recipients)
    
    def _send_smtp_blocking(self, message: MIMEMultipart, recipients: List[str]):
        """Blocking SMTP send."""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                
                server.sendmail(self.from_email, recipients, message.as_string())
        
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            raise
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str):
        """Attach file to message."""
        path = Path(file_path)
        
        try:
            with open(path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {path.name}"
            )
            msg.attach(part)
        
        except Exception as e:
            logger.warning(f"Failed to attach {file_path}: {str(e)}")
    
    async def send_batch(
        self,
        recipients: Dict[str, Dict[str, Any]]
    ) -> Dict[str, EmailResponse]:
        """
        Send emails to multiple recipients.
        
        Args:
            recipients: {email: {subject, body, ...}, ...}
            
        Returns:
            Responses by recipient
        """
        results = {}
        
        for to_email, params in recipients.items():
            response = await self.send_email(
                to=[to_email],
                subject=params.get("subject", ""),
                body=params.get("body", ""),
                html=params.get("html", False),
                cc=params.get("cc"),
                bcc=params.get("bcc"),
                attachments=params.get("attachments")
            )
            results[to_email] = response
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get email statistics."""
        return {
            "total_sent": self.sent_count,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port
        }


# Global email tool instance
_email_tool: Optional[EmailTool] = None


def get_email_tool(config: Optional[Settings] = None) -> EmailTool:
    """Get or create global email tool."""
    global _email_tool
    
    if _email_tool is None:
        if config is None:
            config = Settings()
        
        _email_tool = EmailTool(
            smtp_host=config.smtp_host or "localhost",
            smtp_port=config.smtp_port or 587,
            smtp_user=config.smtp_user or "",
            smtp_password=config.smtp_password or "",
            use_tls=config.smtp_use_tls or True,
            from_email=config.smtp_from_email or "noreply@company.com"
        )
    
    return _email_tool

    def send_delay_alert(self, task):
        return self.send_email(
            to=task.get("assigned_to", self.default_recipient),
            subject="Task Delay Alert",
            message=(
                f"Task '{task.get('task')}' is delayed.\n"
                f"Priority: {task.get('priority', 'N/A')}\n"
                f"Please take action immediately."
            )
        )

    def send_completion_alert(self, task):
        return self.send_email(
            to=task.get("assigned_to", self.default_recipient),
            subject="Task Completed",
            message=(
                f"Task '{task.get('task')}' has been completed successfully.\n"
                f"Completed At: {datetime.now().isoformat()}"
            )
        )

    def send_summary(self, stats):
        return self.send_email(
            to=self.default_recipient,
            subject="Workflow Summary",
            message=(
                f"Total Tasks: {stats.get('total_tasks')}\n"
                f"Completed: {stats.get('completed_tasks')}\n"
                f"Delayed: {stats.get('delayed_tasks')}\n"
                f"Efficiency: {stats.get('efficiency'):.2f}"
            )
        )