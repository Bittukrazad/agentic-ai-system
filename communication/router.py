"""communication/router.py — Routes messages and events to the correct handler"""
from typing import Any, Callable, Dict, List, Optional

from communication.event_bus import EventBus
from communication.message_queue import MessageQueue
from utils.logger import get_logger

logger = get_logger(__name__)


# Route registry: {route_key: handler_fn}
_routes: Dict[str, Callable] = {}


class MessageRouter:
    """
    Central router that maps event types and message categories
    to the correct handler function or agent.

    Responsibilities:
      - Register routes at startup (event_type → handler)
      - On EventBus publish, route to the correct handler
      - Manage priority routing (CRITICAL > HIGH > NORMAL)
      - Dead-letter queue for unroutable messages

    Usage:
        router = MessageRouter()
        router.register("workflow_completed", my_handler)
        router.register("human_gate_required", notify_human)
        router.start()          # subscribes all routes to EventBus
    """

    def __init__(self):
        self.queue = MessageQueue()
        self._dead_letter: List[Dict] = []

    # ── Route Registration ────────────────────────────────────────────────
    def register(self, event_type: str, handler: Callable, priority: str = "normal"):
        """Register a handler for an event type"""
        _routes[event_type] = {"handler": handler, "priority": priority}
        logger.debug(f"Route registered: {event_type} → {handler.__name__} [{priority}]")

    def start(self):
        """Subscribe all registered routes to the EventBus"""
        for event_type, config in _routes.items():
            EventBus.subscribe(event_type, self._make_dispatcher(event_type, config["handler"]))
        logger.info(f"MessageRouter started with {len(_routes)} routes")

    def _make_dispatcher(self, event_type: str, handler: Callable) -> Callable:
        """Wrap a handler so it can be called by the EventBus"""
        def dispatcher(evt_type: str, payload: Dict):
            try:
                logger.debug(f"Routing: {evt_type} → {handler.__name__}")
                return handler(payload)
            except Exception as e:
                logger.error(f"Route handler failed: {evt_type} | {handler.__name__} | {e}")
                self._dead_letter.append({"event_type": evt_type, "payload": payload, "error": str(e)})
        return dispatcher

    # ── Built-in Default Routes ───────────────────────────────────────────
    def register_default_routes(self):
        """Register the system's default event routing table"""
        self.register("workflow_completed",  self._handle_workflow_completed,  priority="normal")
        self.register("workflow_failed",      self._handle_workflow_failed,     priority="high")
        self.register("human_gate_required",  self._handle_human_gate,          priority="high")
        self.register("system_alert",         self._handle_system_alert,        priority="high")
        self.register("sla_breach_risk",      self._handle_sla_breach_risk,     priority="critical")
        self.register("task_stalled",         self._handle_task_stalled,        priority="high")
        self.register("step_complete",        self._handle_step_complete,       priority="normal")
        self.start()
        logger.info("Default routes registered and active")

    # ── Default Handlers ──────────────────────────────────────────────────
    def _handle_workflow_completed(self, payload: Dict):
        wf_id = payload.get("workflow_id", "")
        wf_type = payload.get("type", "")
        logger.info(f"[ROUTER] Workflow completed | id={wf_id} type={wf_type}")
        # Trigger post-completion hooks: dashboard refresh, metrics update
        self.queue.enqueue(wf_id, {"event": "workflow_completed", "payload": payload})

    def _handle_workflow_failed(self, payload: Dict):
        wf_id = payload.get("workflow_id", "")
        error = payload.get("error", "unknown")
        logger.error(f"[ROUTER] Workflow FAILED | id={wf_id} | error={error}")
        self.queue.enqueue(wf_id, {"event": "workflow_failed", "payload": payload})

    def _handle_human_gate(self, payload: Dict):
        wf_id = payload.get("workflow_id", "")
        step  = payload.get("step_name", "")
        logger.warning(f"[ROUTER] Human gate required | workflow={wf_id} | step={step}")
        # In production: push to notification service (Slack, email, PagerDuty)
        self.queue.enqueue(wf_id, {"event": "human_gate", "step": step, "payload": payload})

    def _handle_system_alert(self, payload: Dict):
        alert_type = payload.get("alert_type", "")
        message    = payload.get("message", "")
        logger.warning(f"[ROUTER] System alert | type={alert_type} | msg={message[:80]}")

    def _handle_sla_breach_risk(self, payload: Dict):
        wf_id = payload.get("workflow_id", "")
        prob  = payload.get("probability", 0)
        logger.critical(f"[ROUTER] SLA BREACH RISK | workflow={wf_id} | prob={prob:.0%}")
        # Fast-path: immediately trigger reroute engine
        try:
            from health_monitoring.reroute_engine import RerouteEngine
            RerouteEngine().reroute(wf_id, reason=f"sla_breach_risk prob={prob:.2f}", strategy="skip_non_critical")
        except Exception as e:
            logger.error(f"Reroute failed: {e}")

    def _handle_task_stalled(self, payload: Dict):
        task  = payload.get("task", {})
        wf_id = payload.get("workflow_id", "")
        logger.warning(f"[ROUTER] Task stalled | task={task.get('id')} | workflow={wf_id}")

    def _handle_step_complete(self, payload: Dict):
        step = payload.get("step_id", "")
        wf   = payload.get("workflow_id", "")
        logger.debug(f"[ROUTER] Step complete | step={step} | workflow={wf}")

    # ── Dead-Letter Inspection ────────────────────────────────────────────
    def get_dead_letters(self) -> List[Dict]:
        """Return unroutable or failed messages for inspection"""
        return list(self._dead_letter)

    def clear_dead_letters(self):
        self._dead_letter.clear()

    # ── Direct Routing (bypass EventBus) ─────────────────────────────────
    def route_direct(self, event_type: str, payload: Dict) -> bool:
        """Route a message directly without going through EventBus pub/sub"""
        route = _routes.get(event_type)
        if not route:
            logger.warning(f"No route registered for: {event_type}")
            self._dead_letter.append({"event_type": event_type, "payload": payload, "error": "no_route"})
            return False
        try:
            route["handler"](payload)
            return True
        except Exception as e:
            logger.error(f"Direct route failed: {event_type} | {e}")
            return False


# Module-level singleton — import and use directly
default_router = MessageRouter()