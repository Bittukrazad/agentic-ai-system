"""
Event Bus Module - Async pub/sub system for system-wide broadcasting.

Provides:
- Event subscription management
- Async event publishing
- Event filtering
- Subscriber notifications
"""

from typing import Dict, List, Callable, Any, Optional
import asyncio
from datetime import datetime
from enum import Enum
from utils.logger import get_logger
from utils.helpers import get_iso_now

logger = get_logger(__name__)


class EventType(Enum):
    """System event types."""
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    SLA_BREACH = "sla_breach"
    SLA_WARNING = "sla_warning"
    AGENT_REGISTERED = "agent_registered"
    AGENT_ERROR = "agent_error"
    RETRY_TRIGGERED = "retry_triggered"
    ESCALATION_TRIGGERED = "escalation_triggered"


class Event:
    """System event with metadata."""
    
    def __init__(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any],
        timestamp: Optional[str] = None
    ):
        """
        Initialize event.
        
        Args:
            event_type: Event type
            source: Event source (agent/system name)
            data: Event data
            timestamp: ISO timestamp
        """
        self.event_type = event_type
        self.source = source
        self.data = data
        self.timestamp = timestamp or get_iso_now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp
        }


class EventSubscription:
    """Event subscription with filter."""
    
    def __init__(
        self,
        subscriber_id: str,
        event_types: List[EventType],
        handler: Callable,
        filter_func: Optional[Callable] = None
    ):
        """
        Initialize subscription.
        
        Args:
            subscriber_id: Unique subscriber identifier
            event_types: Event types to subscribe to
            handler: Async handler function
            filter_func: Optional filter function
        """
        self.subscriber_id = subscriber_id
        self.event_types = event_types
        self.handler = handler
        self.filter_func = filter_func
        self.created_at = get_iso_now()


class EventBus:
    """
    Async event bus for system-wide event broadcasting.
    
    Provides:
    - Publish events to all subscribers
    - Subscribe to specific event types
    - Filter events by criteria
    - Async handler execution
    """
    
    def __init__(self):
        """Initialize event bus."""
        self.subscriptions: Dict[EventType, List[EventSubscription]] = {
            event_type: [] for event_type in EventType
        }
        self.event_history: List[Event] = []
        self.max_history_size = 1000
    
    def subscribe(
        self,
        subscriber_id: str,
        event_types: List[EventType],
        handler: Callable,
        filter_func: Optional[Callable] = None
    ) -> bool:
        """
        Subscribe to events.
        
        Args:
            subscriber_id: Subscriber identifier
            event_types: Event types to subscribe to
            handler: Async handler function(event)
            filter_func: Optional filter function(event) -> bool
            
        Returns:
            Success status
        """
        subscription = EventSubscription(
            subscriber_id,
            event_types,
            handler,
            filter_func
        )
        
        for event_type in event_types:
            self.subscriptions[event_type].append(subscription)
        
        logger.info(
            f"Subscriber registered",
            extra={
                "subscriber_id": subscriber_id,
                "event_types": [et.value for et in event_types]
            }
        )
        
        return True
    
    def unsubscribe(self, subscriber_id: str) -> int:
        """
        Unsubscribe from all events.
        
        Args:
            subscriber_id: Subscriber to remove
            
        Returns:
            Number of subscriptions removed
        """
        count = 0
        for subscriptions in self.subscriptions.values():
            to_remove = [s for s in subscriptions if s.subscriber_id == subscriber_id]
            for subscription in to_remove:
                subscriptions.remove(subscription)
                count += 1
        
        if count > 0:
            logger.info(f"Subscriber unregistered", extra={"subscriber_id": subscriber_id})
        
        return count
    
    async def publish(
        self,
        event: Event
    ) -> Dict[str, Any]:
        """
        Publish event to all subscribers asynchronously.
        
        Args:
            event: Event to publish
            
        Returns:
            Publication results
        """
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
        
        # Get subscribers for this event type
        subscribers = self.subscriptions.get(event.event_type, [])
        
        logger.info(
            f"Event published",
            extra={
                "event_type": event.event_type.value,
                "source": event.source,
                "subscriber_count": len(subscribers)
            }
        )
        
        # Execute handlers asynchronously
        tasks = []
        for subscription in subscribers:
            # Check filter
            if subscription.filter_func and not subscription.filter_func(event):
                continue
            
            # Create task
            tasks.append(self._execute_handler(subscription, event))
        
        # Wait for all handlers
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Track results
        successful = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if isinstance(r, Exception))
        
        return {
            "event_type": event.event_type.value,
            "total_handlers": len(subscribers),
            "successful": successful,
            "failed": failed
        }
    
    async def _execute_handler(
        self,
        subscription: EventSubscription,
        event: Event
    ) -> bool:
        """
        Execute subscriber handler safely.
        
        Args:
            subscription: Event subscription
            event: Event to handle
            
        Returns:
            True if successful
        """
        try:
            # Support both sync and async handlers
            if asyncio.iscoroutinefunction(subscription.handler):
                await subscription.handler(event)
            else:
                subscription.handler(event)
            
            return True
        except Exception as e:
            logger.error(
                f"Handler error",
                extra={
                    "subscriber_id": subscription.subscriber_id,
                    "event_type": event.event_type.value,
                    "error": str(e)
                }
            )
            return False
    
    def get_recent_events(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 20
    ) -> List[Event]:
        """
        Get recent events.
        
        Args:
            event_type: Optional filter by type
            limit: Maximum number to return
            
        Returns:
            Recent events
        """
        events = self.event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def get_subscriber_count(self, event_type: Optional[EventType] = None) -> int:
        """
        Get subscriber count.
        
        Args:
            event_type: Optional filter by event type
            
        Returns:
            Number of subscribers
        """
        if event_type:
            return len(self.subscriptions.get(event_type, []))
        
        total = 0
        for subscribers in self.subscriptions.values():
            total += len(subscribers)
        return total
    
    def get_subscriptions(self, subscriber_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get subscription information.
        
        Args:
            subscriber_id: Optional filter by subscriber
            
        Returns:
            Subscription information
        """
        if subscriber_id:
            subscriptions = {}
            for event_type, subs in self.subscriptions.items():
                for sub in subs:
                    if sub.subscriber_id == subscriber_id:
                        subscriptions[event_type.value] = {
                            "subscriber_id": sub.subscriber_id,
                            "created_at": sub.created_at
                        }
            return subscriptions
        
        return {
            event_type.value: len(subs)
            for event_type, subs in self.subscriptions.items()
        }
    
    def clear_history(self) -> int:
        """Clear event history (for maintenance)."""
        count = len(self.event_history)
        self.event_history = []
        return count


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
