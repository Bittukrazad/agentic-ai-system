"""
Slack Tool - Send messages and notifications via Slack API.

Provides:
- Send messages to channels
- Send direct messages
- Message formatting with blocks
- Thread replies
- Reactions
- Retry logic
"""

import httpx
from typing import Dict, Any, Optional, List
import asyncio
from utils.logger import get_logger
from app.config import Settings

logger = get_logger(__name__)


class SlackMessage:
    """Slack message with blocks."""
    
    def __init__(
        self,
        channel: str,
        text: str = "",
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None
    ):
        """
        Initialize message.
        
        Args:
            channel: Channel name or ID
            text: Plain text fallback
            blocks: Message blocks (formatted)
            thread_ts: Parent message timestamp for threads
        """
        self.channel = channel
        self.text = text
        self.blocks = blocks or []
        self.thread_ts = thread_ts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        payload = {
            "channel": self.channel,
            "text": self.text
        }
        
        if self.blocks:
            payload["blocks"] = self.blocks
        
        if self.thread_ts:
            payload["thread_ts"] = self.thread_ts
        
        return payload


class SlackResponse:
    """Slack API response."""
    
    def __init__(
        self,
        success: bool,
        channel: str = "",
        ts: str = "",
        error: str = ""
    ):
        """
        Initialize response.
        
        Args:
            success: Whether message was sent
            channel: Channel
            ts: Message timestamp
            error: Error message if failed
        """
        self.success = success
        self.channel = channel
        self.ts = ts
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "channel": self.channel,
            "ts": self.ts,
            "error": self.error
        }


class SlackTool:
    """
    Slack messaging tool.
    
    Features:
    - Send messages to channels
    - Direct messages
    - Message blocks/formatting
    - Thread replies
    - Reactions
    """
    
    def __init__(
        self,
        token: str = "",
        workspace: str = "company",
        max_retries: int = 3
    ):
        """
        Initialize Slack tool.
        
        Args:
            token: Slack bot token
            workspace: Workspace name
            max_retries: Maximum retry attempts
        """
        self.token = token
        self.workspace = workspace
        self.max_retries = max_retries
        self.api_url = "https://slack.com/api"
        self.sent_count = 0
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def send_message(
        self,
        channel: str,
        text: str = "",
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """
        Send message to channel.
        
        Args:
            channel: Channel name or ID
            text: Plain text message
            blocks: Message blocks (formatted)
            thread_ts: Parent message TS for threads
            
        Returns:
            SlackResponse
        """
        if not self.token:
            logger.warning("Slack token not configured")
            return SlackResponse(
                success=False,
                channel=channel,
                error="Slack token not configured"
            )
        
        payload = {
            "channel": channel,
            "text": text or "Message"
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        if thread_ts:
            payload["thread_ts"] = thread_ts
        
        return await self._api_request(
            "chat.postMessage",
            payload
        )
    
    async def send_direct_message(
        self,
        user_id: str,
        text: str = "",
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> SlackResponse:
        """
        Send direct message to user.
        
        Args:
            user_id: User ID
            text: Message text
            blocks: Message blocks
            
        Returns:
            SlackResponse
        """
        # Open DM channel
        channel_response = await self._api_request(
            "conversations.open",
            {"users": user_id}
        )
        
        if not channel_response.get("ok"):
            return SlackResponse(
                success=False,
                error=channel_response.get("error", "Failed to open DM")
            )
        
        channel = channel_response["channel"]["id"]
        
        return await self.send_message(
            channel=channel,
            text=text,
            blocks=blocks
        )
    
    async def add_reaction(
        self,
        channel: str,
        timestamp: str,
        emoji: str
    ) -> SlackResponse:
        """
        Add emoji reaction to message.
        
        Args:
            channel: Channel
            timestamp: Message timestamp
            emoji: Emoji name (without colons)
            
        Returns:
            SlackResponse
        """
        payload = {
            "channel": channel,
            "name": emoji,
            "timestamp": timestamp
        }
        
        return await self._api_request(
            "reactions.add",
            payload
        )
    
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str = "",
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> SlackResponse:
        """
        Update existing message.
        
        Args:
            channel: Channel
            ts: Message timestamp
            text: New text
            blocks: New blocks
            
        Returns:
            SlackResponse
        """
        payload = {
            "channel": channel,
            "ts": ts,
            "text": text or "Updated"
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        return await self._api_request(
            "chat.update",
            payload
        )
    
    async def _api_request(
        self,
        method: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make Slack API request with retry.
        
        Args:
            method: Slack API method
            payload: Request payload
            
        Returns:
            API response
        """
        url = f"{self.api_url}/{method}"
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self.headers,
                        timeout=30
                    )
                
                data = response.json()
                
                if data.get("ok"):
                    self.sent_count += 1
                    
                    logger.info(
                        f"Slack API call successful",
                        extra={
                            "method": method,
                            "attempt": attempt + 1
                        }
                    )
                    
                    return data
                else:
                    error = data.get("error", "Unknown error")
                    
                    logger.warning(
                        f"Slack API error",
                        extra={
                            "method": method,
                            "error": error,
                            "attempt": attempt + 1
                        }
                    )
                    
                    # Don't retry on permanent errors
                    if error in ["invalid_auth", "token_revoked", "wrong_channel_type"]:
                        return data
                    
                    last_error = error
            
            except Exception as e:
                last_error = str(e)
                
                logger.warning(
                    f"Slack request error",
                    extra={
                        "method": method,
                        "error": str(e),
                        "attempt": attempt + 1
                    }
                )
            
            # Retry with backoff
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        logger.error(
            f"Slack API exhausted retries",
            extra={"method": method, "error": str(last_error)}
        )
        
        return {
            "ok": False,
            "error": str(last_error) or "Request failed"
        }
    
    async def send_batch(
        self,
        messages: List[SlackMessage]
    ) -> List[SlackResponse]:
        """
        Send multiple messages.
        
        Args:
            messages: List of messages
            
        Returns:
            List of responses
        """
        tasks = [
            self.send_message(
                channel=msg.channel,
                text=msg.text,
                blocks=msg.blocks,
                thread_ts=msg.thread_ts
            )
            for msg in messages
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Slack statistics."""
        return {
            "total_sent": self.sent_count,
            "workspace": self.workspace,
            "api_url": self.api_url
        }


# Global Slack tool instance
_slack_tool: Optional[SlackTool] = None


def get_slack_tool(config: Optional[Settings] = None) -> SlackTool:
    """Get or create global Slack tool."""
    global _slack_tool
    
    if _slack_tool is None:
        if config is None:
            config = Settings()
        
        _slack_tool = SlackTool(
            token=config.slack_bot_token or "",
            workspace=config.workspace_name or "company"
        )
    
    return _slack_tool
                else:
                    return {"status": "failed", "error": str(e)}

    def notify_delay(self, task):
        priority = task.get("priority", "medium")

        channel = (
            self.default_channels["critical"]
            if priority == "high"
            else self.default_channels["alert"]
        )

        return self.send_message(
            channel,
            f"Task '{task.get('task')}' is delayed!\nPriority: {priority}"
        )

    def notify_success(self, task):
        return self.send_message(
            self.default_channels["update"],
            f"Task '{task.get('task')}' completed successfully!"
        )

    def notify_escalation(self, task):
        return self.send_message(
            self.default_channels["critical"],
            (
                f"ESCALATION: Task '{task.get('task')}' is critically delayed!\n"
                f"Assigned To: {task.get('assigned_to', 'N/A')}"
            )
        )

    def send_summary(self, stats):
        return self.send_message(
            self.default_channels["update"],
            (
                f"Workflow Summary\n"
                f"Total: {stats.get('total_tasks')}\n"
                f"Completed: {stats.get('completed_tasks')}\n"
                f"Delayed: {stats.get('delayed_tasks')}\n"
                f"Efficiency: {stats.get('efficiency'):.2f}"
            )
        )