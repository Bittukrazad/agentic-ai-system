"""communication/message_queue.py — Message queue for serialising concurrent workflows"""
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# In-process queue: {workflow_id: deque of messages}
# For production: replace with Redis List (LPUSH / BRPOP)
_queues: Dict[str, deque] = {}


class MessageQueue:
    """
    Per-workflow FIFO message queue.
    Ensures agents processing the same workflow don't overwrite
    each other's outputs when running concurrently.

    Production replacement:
        import redis
        r = redis.from_url(config.REDIS_URL)
        r.lpush(f"queue:{workflow_id}", json.dumps(message))
        msg = r.brpop(f"queue:{workflow_id}", timeout=30)
    """

    def enqueue(self, workflow_id: str, message: Dict[str, Any]):
        """Add a message to the workflow's queue"""
        if workflow_id not in _queues:
            _queues[workflow_id] = deque(maxlen=500)

        envelope = {
            "workflow_id": workflow_id,
            "message": message,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        _queues[workflow_id].append(envelope)
        logger.debug(f"Enqueued | workflow={workflow_id} | queue_size={len(_queues[workflow_id])}")

    def dequeue(self, workflow_id: str) -> Optional[Dict]:
        """Pop the next message from the workflow's queue"""
        q = _queues.get(workflow_id)
        if q:
            try:
                return q.popleft()
            except IndexError:
                return None
        return None

    def peek(self, workflow_id: str) -> Optional[Dict]:
        """Look at the next message without removing it"""
        q = _queues.get(workflow_id)
        if q:
            try:
                return q[0]
            except IndexError:
                return None
        return None

    def queue_length(self, workflow_id: str) -> int:
        return len(_queues.get(workflow_id, []))

    def drain(self, workflow_id: str) -> List[Dict]:
        """Remove and return all messages for a workflow"""
        q = _queues.pop(workflow_id, deque())
        return list(q)

    def clear_all(self):
        _queues.clear()