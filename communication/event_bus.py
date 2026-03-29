"""communication/event_bus.py — Async publish/subscribe event bus"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from utils.logger import get_logger

logger = get_logger(__name__)

# Subscriber registry: {event_type: [callback, ...]}
_subscribers: Dict[str, List[Callable]] = {}

# Event history for debugging / replay
_event_history: List[Dict] = []


class EventBus:
    """
    In-process async pub/sub event bus.
    Decouples producers (agents that complete steps) from
    consumers (monitoring, dashboard, communication_agent).

    For production multi-process deployments:
      Replace _subscribers with a Redis Pub/Sub or Kafka topic.
    """

    _instance = None

    @classmethod
    def init(cls):
        """Called on app startup"""
        _subscribers.clear()
        _event_history.clear()
        logger.info("EventBus initialised")

    @classmethod
    def shutdown(cls):
        logger.info("EventBus shutting down")

    @staticmethod
    def subscribe(event_type: str, callback: Callable):
        """Register a callback for an event type"""
        if event_type not in _subscribers:
            _subscribers[event_type] = []
        _subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to '{event_type}' | total={len(_subscribers[event_type])}")

    @staticmethod
    def publish(event_type: str, payload: Dict[str, Any]):
        """Publish an event to all subscribers (fire-and-forget)"""
        event = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _event_history.append(event)

        callbacks = _subscribers.get(event_type, [])
        if not callbacks:
            logger.debug(f"Event published with no subscribers | type={event_type}")
            return

        for cb in callbacks:
            try:
                result = cb(event_type, payload)
                # If callback returns a coroutine, schedule it
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.warning(f"EventBus callback error | event={event_type} | {e}")

        logger.debug(f"Event published | type={event_type} | subscribers={len(callbacks)}")

    @staticmethod
    def get_history(event_type: str = None, limit: int = 100) -> List[Dict]:
        if event_type:
            filtered = [e for e in _event_history if e["event_type"] == event_type]
            return filtered[-limit:]
        return _event_history[-limit:]