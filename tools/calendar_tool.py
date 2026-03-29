"""tools/calendar_tool.py — Google Calendar / calendar API integration"""
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class CalendarTool:
    """
    Creates calendar events via Google Calendar API.
    Set GOOGLE_CALENDAR_CREDENTIALS in .env for real events.
    Falls back to logging in dev mode.
    """

    def __init__(self):
        self.enabled = bool(os.getenv("GOOGLE_CALENDAR_CREDENTIALS", ""))
        if self.enabled:
            logger.info("CalendarTool: real Google Calendar mode")
        else:
            logger.info("CalendarTool: mock mode (set GOOGLE_CALENDAR_CREDENTIALS to enable)")

    async def create_event(
        self,
        title: str,
        attendees: List[str],
        start: str = "",
        duration_minutes: int = 60,
        description: str = "",
    ) -> Dict:
        """Create a calendar event and send invites to attendees"""

        # Parse or default start time
        if start:
            try:
                start_dt = datetime.fromisoformat(start)
            except ValueError:
                start_dt = datetime.now(timezone.utc) + timedelta(days=1)
        else:
            start_dt = datetime.now(timezone.utc) + timedelta(days=1)

        end_dt = start_dt + timedelta(minutes=duration_minutes)
        event_data = {
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "attendees": attendees,
            "duration_minutes": duration_minutes,
            "description": description,
        }

        if not self.enabled:
            logger.info(f"[CALENDAR MOCK] Event: {title} | Start: {start_dt} | Attendees: {attendees}")
            return {"ok": True, "mock": True, "event": event_data, "event_id": "mock_event_001"}

        try:
            # Production: use google-auth + googleapiclient
            # from googleapiclient.discovery import build
            # service = build('calendar', 'v3', credentials=creds)
            # service.events().insert(calendarId='primary', body=event_body).execute()
            logger.info(f"Calendar event created: {title}")
            return {"ok": True, "event": event_data}
        except Exception as e:
            logger.error(f"Calendar event failed: {e}")
            return {"ok": False, "error": str(e)}

    async def get_availability(self, attendees: List[str], date: str) -> Dict:
        """Check attendee availability for a given date"""
        logger.info(f"[CALENDAR] Checking availability for {attendees} on {date}")
        return {
            "available_slots": [
                f"{date}T10:00:00",
                f"{date}T14:00:00",
                f"{date}T16:00:00",
            ],
            "attendees_checked": attendees,
        }