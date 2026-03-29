"""health_monitoring/bottleneck_predictor.py — Predicts SLA breach probability"""
from datetime import datetime, timezone
from typing import Dict

from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()

# Trigger rerouting if breach probability exceeds this threshold
BREACH_TRIGGER_THRESHOLD = 0.70

# Active workflow SLA registry {workflow_id: SLAManager}
_sla_registry: Dict = {}


class BottleneckPredictor:
    """
    Estimates the probability of an SLA breach using:
      - Time elapsed vs SLA total duration
      - Steps completed vs total steps
    If probability > BREACH_TRIGGER_THRESHOLD, triggers reroute_engine.
    """

    _scheduler = None

    @classmethod
    def start_scheduler(cls):
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from app.config import config
            cls._scheduler = AsyncIOScheduler()
            cls._scheduler.add_job(
                cls._scheduled_predict,
                "interval",
                minutes=config.HEALTH_CHECK_INTERVAL_MINUTES,
                id="bottleneck_predictor",
            )
            cls._scheduler.start()
            logger.info("BottleneckPredictor scheduler started")
        except Exception as e:
            logger.warning(f"BottleneckPredictor scheduler not started: {e}")

    @classmethod
    def stop_scheduler(cls):
        if cls._scheduler:
            cls._scheduler.shutdown(wait=False)

    @classmethod
    async def _scheduled_predict(cls):
        logger.debug("BottleneckPredictor scheduled check running")

    @staticmethod
    def register_sla(workflow_id: str, sla_manager):
        _sla_registry[workflow_id] = sla_manager

    def predict(self, workflow_id: str, completed_steps: int, total_steps: int) -> float:
        """
        Returns breach probability 0.0–1.0.
        Simple heuristic: if time_fraction >> completion_fraction, breach is likely.
        """
        sla = _sla_registry.get(workflow_id)
        if not sla:
            return 0.0

        prob = sla.breach_probability(completed_steps / max(total_steps, 1))

        if prob >= BREACH_TRIGGER_THRESHOLD:
            logger.warning(
                f"BREACH PREDICTED | workflow={workflow_id} prob={prob:.2f} "
                f"steps={completed_steps}/{total_steps}"
            )
            audit.log(
                agent_id="bottleneck_predictor",
                action="BREACH_PREDICTED",
                workflow_id=workflow_id,
                step_name="sla_check",
                output_summary=f"prob={prob:.2f} steps={completed_steps}/{total_steps}",
                confidence=prob,
            )
            self._trigger_reroute(workflow_id, prob)

        return prob

    def _trigger_reroute(self, workflow_id: str, probability: float):
        from health_monitoring.reroute_engine import RerouteEngine
        RerouteEngine().reroute(workflow_id, reason=f"breach_probability={probability:.2f}")