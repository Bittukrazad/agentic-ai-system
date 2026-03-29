"""agents/communication_agent.py — Coordinates inter-agent messaging via event bus"""
from typing import Any, Dict

from agents.base_agent import BaseAgent
from communication.event_bus import EventBus
from communication.message_queue import MessageQueue


class CommunicationAgent(BaseAgent):
    """
    Acts as the message bus coordinator between agents.
    Publishes results to event_bus, manages ordering in message_queue.
    Ensures agents never overwrite each other's outputs.
    """

    def __init__(self):
        super().__init__()
        self.event_bus = EventBus()
        self.queue = MessageQueue()

    async def coordinate(self, step: Dict, state) -> Dict[str, Any]:
        """Publish a step result to the event bus and queue"""
        workflow_id = state.workflow_id
        step_id = step.get("id", "unknown")
        event_type = step.get("event_type", "workflow_step")
        payload = {
            "workflow_id": workflow_id,
            "step_id": step_id,
            "workflow_type": state.workflow_type,
            "outputs": state.outputs,
        }

        EventBus.publish(event_type, payload)
        self.queue.enqueue(workflow_id, {"step": step_id, "payload": payload})

        self.log_action(
            action="MESSAGE_PUBLISHED",
            workflow_id=workflow_id,
            step_name=step_id,
            input_summary=f"event={event_type}",
            output_summary="published to event_bus + queue",
            confidence=1.0,
        )
        return {"status": "ok", "event_published": event_type}

    async def broadcast_completion(self, workflow_id: str, result: Dict):
        """Broadcast workflow completion to all subscribers"""
        EventBus.publish("workflow_completed", {
            "workflow_id": workflow_id,
            "result": result,
        })
        self.logger.info(f"Broadcast completion | workflow={workflow_id}")

    async def send_alert(self, workflow_id: str, alert_type: str, message: str):
        """Send a system alert through the event bus"""
        EventBus.publish("system_alert", {
            "workflow_id": workflow_id,
            "alert_type": alert_type,
            "message": message,
        })
        self.log_action(
            action="ALERT_SENT",
            workflow_id=workflow_id,
            step_name="alert",
            input_summary=f"type={alert_type}",
            output_summary=message[:80],
            confidence=1.0,
        )