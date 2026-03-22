"""
Calendar Tool - Schedule tasks and manage calendar events.

Provides:
- Event scheduling
- Overdue detection
- Calendar queries
- Time slot availability
- Integration with email/Slack notifications
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
from enum import Enum
from utils.logger import get_logger
from utils.helpers import (
    get_iso_now,
    iso_to_datetime,
    add_hours_to_iso,
    is_past_iso
)

logger = get_logger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(Enum):
    """Event status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class CalendarEvent:
    """Calendar event."""
    
    def __init__(
        self,
        title: str,
        scheduled_at: str,
        priority: EventPriority = EventPriority.MEDIUM,
        duration_minutes: int = 60,
        owner_email: str = "",
        description: str = ""
    ):
        """
        Initialize event.
        
        Args:
            title: Event title
            scheduled_at: ISO timestamp
            priority: Event priority
            duration_minutes: Duration in minutes
            owner_email: Owner email
            description: Event description
        """
        self.event_id = str(uuid.uuid4())
        self.title = title
        self.scheduled_at = scheduled_at
        self.priority = priority
        self.duration_minutes = duration_minutes
        self.owner_email = owner_email
        self.description = description
        self.status = EventStatus.SCHEDULED
        self.created_at = get_iso_now()
        self.completed_at: Optional[str] = None
        self.reminders_sent = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "title": self.title,
            "scheduled_at": self.scheduled_at,
            "priority": self.priority.value,
            "duration_minutes": self.duration_minutes,
            "owner_email": self.owner_email,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "reminders_sent": self.reminders_sent
        }


class CalendarResponse:
    """Calendar operation response."""
    
    def __init__(
        self,
        success: bool,
        data: Dict[str, Any] = None,
        events: List[CalendarEvent] = None,
        error: str = ""
    ):
        """
        Initialize response.
        
        Args:
            success: Whether operation succeeded
            data: Response data
            events: Events list
            error: Error message
        """
        self.success = success
        self.data = data or {}
        self.events = events or []
        self.error = error


class CalendarTool:
    """
    Calendar and task scheduling tool.
    
    Features:
    - Schedule events
    - Track overdue tasks
    - Find free time slots
    - Send reminders
    """
    
    def __init__(self):
        """Initialize calendar tool."""
        self.events: Dict[str, CalendarEvent] = {}
        self.scheduled_count = 0
        self.completed_count = 0
    
    def schedule_event(
        self,
        title: str,
        scheduled_at: str,
        priority: EventPriority = EventPriority.MEDIUM,
        duration_minutes: int = 60,
        owner_email: str = "",
        description: str = ""
    ) -> CalendarResponse:
        """
        Schedule calendar event.
        
        Args:
            title: Event title
            scheduled_at: Event time (ISO format)
            priority: Event priority
            duration_minutes: Duration in minutes
            owner_email: Owner email
            description: Event description
            
        Returns:
            CalendarResponse
        """
        try:
            event = CalendarEvent(
                title=title,
                scheduled_at=scheduled_at,
                priority=priority,
                duration_minutes=duration_minutes,
                owner_email=owner_email,
                description=description
            )
            
            self.events[event.event_id] = event
            self.scheduled_count += 1
            
            logger.info(
                f"Event scheduled",
                extra={
                    "event_id": event.event_id,
                    "title": title,
                    "scheduled_at": scheduled_at
                }
            )
            
            return CalendarResponse(
                success=True,
                data=event.to_dict()
            )
        
        except Exception as e:
            logger.error(f"Schedule error: {str(e)}")
            return CalendarResponse(
                success=False,
                error=str(e)
            )
    
    def complete_event(self, event_id: str) -> CalendarResponse:
        """
        Mark event as completed.
        
        Args:
            event_id: Event ID
            
        Returns:
            CalendarResponse
        """
        if event_id not in self.events:
            return CalendarResponse(
                success=False,
                error=f"Event {event_id} not found"
            )
        
        event = self.events[event_id]
        event.status = EventStatus.COMPLETED
        event.completed_at = get_iso_now()
        self.completed_count += 1
        
        logger.info(
            f"Event completed",
            extra={"event_id": event_id, "title": event.title}
        )
        
        return CalendarResponse(
            success=True,
            data=event.to_dict()
        )
    
    def cancel_event(self, event_id: str) -> CalendarResponse:
        """Cancel event."""
        if event_id not in self.events:
            return CalendarResponse(
                success=False,
                error=f"Event {event_id} not found"
            )
        
        event = self.events[event_id]
        event.status = EventStatus.CANCELLED
        
        logger.info(
            f"Event cancelled",
            extra={"event_id": event_id, "title": event.title}
        )
        
        return CalendarResponse(
            success=True,
            data=event.to_dict()
        )
    
    def get_event(self, event_id: str) -> CalendarResponse:
        """Get event by ID."""
        if event_id not in self.events:
            return CalendarResponse(
                success=False,
                error=f"Event {event_id} not found"
            )
        
        return CalendarResponse(
            success=True,
            data=self.events[event_id].to_dict()
        )
    
    def get_overdue_events(self) -> CalendarResponse:
        """Get overdue events."""
        overdue = [
            event for event in self.events.values()
            if event.status == EventStatus.SCHEDULED
            and is_past_iso(event.scheduled_at)
        ]
        
        for event in overdue:
            event.status = EventStatus.OVERDUE
        
        return CalendarResponse(
            success=True,
            events=overdue
        )
    
    def get_upcoming_events(
        self,
        hours: int = 24
    ) -> CalendarResponse:
        """
        Get upcoming events within timeframe.
        
        Args:
            hours: Lookahead hours
            
        Returns:
            CalendarResponse
        """
        cutoff_time = add_hours_to_iso(get_iso_now(), hours)
        
        upcoming = [
            event for event in self.events.values()
            if event.status in [EventStatus.SCHEDULED, EventStatus.IN_PROGRESS]
            and event.scheduled_at <= cutoff_time
            and event.scheduled_at >= get_iso_now()
        ]
        
        # Sort by time
        upcoming.sort(key=lambda e: e.scheduled_at)
        
        return CalendarResponse(
            success=True,
            events=upcoming
        )
    
    def get_events_by_priority(
        self,
        priority: EventPriority
    ) -> CalendarResponse:
        """Get events by priority."""
        events = [
            event for event in self.events.values()
            if event.priority == priority
            and event.status in [EventStatus.SCHEDULED, EventStatus.OVERDUE]
        ]
        
        return CalendarResponse(
            success=True,
            events=events
        )
    
    def find_available_slots(
        self,
        date: str,
        duration_minutes: int = 60,
        working_hours: tuple = (9, 17)
    ) -> CalendarResponse:
        """
        Find available time slots.
        
        Args:
            date: Date (YYYY-MM-DD)
            duration_minutes: Required slot duration
            working_hours: (start_hour, end_hour)
            
        Returns:
            CalendarResponse with available slots
        """
        try:
            # Parse date
            start = datetime.fromisoformat(f"{date}T{working_hours[0]:02d}:00:00")
            end = datetime.fromisoformat(f"{date}T{working_hours[1]:02d}:00:00")
            
            # Get events on this date
            day_events = [
                event for event in self.events.values()
                if event.scheduled_at.startswith(date)
                and event.status in [EventStatus.SCHEDULED, EventStatus.IN_PROGRESS]
            ]
            
            # Find gaps
            available_slots = []
            current = start
            
            for event in sorted(day_events, key=lambda e: e.scheduled_at):
                event_time = iso_to_datetime(event.scheduled_at)
                gap_duration = (event_time - current).total_seconds() / 60
                
                if gap_duration >= duration_minutes:
                    available_slots.append({
                        "start": current.isoformat(),
                        "end": event_time.isoformat(),
                        "duration_minutes": int(gap_duration)
                    })
                
                # Move current to after this event
                event_end = event_time + timedelta(minutes=event.duration_minutes)
                if event_end > current:
                    current = event_end
            
            # Check remaining time
            gap_duration = (end - current).total_seconds() / 60
            if gap_duration >= duration_minutes:
                available_slots.append({
                    "start": current.isoformat(),
                    "end": end.isoformat(),
                    "duration_minutes": int(gap_duration)
                })
            
            return CalendarResponse(
                success=True,
                data={"available_slots": available_slots}
            )
        
        except Exception as e:
            logger.error(f"Slot finding error: {str(e)}")
            return CalendarResponse(
                success=False,
                error=str(e)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get calendar statistics."""
        return {
            "total_events": len(self.events),
            "scheduled_count": self.scheduled_count,
            "completed_count": self.completed_count,
            "overdue_events": len([
                e for e in self.events.values()
                if e.status == EventStatus.OVERDUE
            ])
        }


# Global calendar tool instance
_calendar_tool: Optional[CalendarTool] = None


def get_calendar_tool() -> CalendarTool:
    """Get or create global calendar tool."""
    global _calendar_tool
    if _calendar_tool is None:
        _calendar_tool = CalendarTool()
    return _calendar_tool
        return [
            task for task in self.tasks
            if self.is_overdue(task["scheduled_at"]) and task["status"] != "completed"
        ]

    def mark_completed(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "completed"
                return task
        return None

    def get_all_tasks(self):
        return self.tasks

    def get_task_stats(self):
        total = len(self.tasks)
        overdue = len(self.get_overdue_tasks())

        return {
            "total_tasks": total,
            "overdue_tasks": overdue,
            "efficiency": (total - overdue) / max(1, total)
        }