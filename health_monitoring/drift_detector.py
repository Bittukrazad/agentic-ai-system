"""health_monitoring/drift_detector.py — Detects process drift vs historical baseline"""
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from memory.long_term_memory import LongTermMemory
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()

# Active workflow timing registry {workflow_id: {step_id: start_timestamp}}
_step_timers: Dict[str, Dict[str, float]] = {}

# Drift threshold: flag if current step takes > this multiple of baseline
DRIFT_MULTIPLIER = 1.5


class DriftDetector:
    """
    Compares current workflow step durations against stored historical baselines.
    Flags when a step runs > DRIFT_MULTIPLIER × baseline duration.
    Baselines are updated after every successful run via LongTermMemory.
    """

    _scheduler = None

    def __init__(self):
        self.ltm = LongTermMemory()

    @classmethod
    def start_scheduler(cls):
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from app.config import config
            cls._scheduler = AsyncIOScheduler()
            cls._scheduler.add_job(
                cls._scheduled_check,
                "interval",
                minutes=config.HEALTH_CHECK_INTERVAL_MINUTES,
                id="drift_detector",
            )
            cls._scheduler.start()
            logger.info("DriftDetector scheduler started")
        except Exception as e:
            logger.warning(f"DriftDetector scheduler not started: {e}")

    @classmethod
    def stop_scheduler(cls):
        if cls._scheduler:
            cls._scheduler.shutdown(wait=False)

    @classmethod
    async def _scheduled_check(cls):
        logger.debug("DriftDetector scheduled check running")

    def start_step_timer(self, workflow_id: str, step_id: str):
        if workflow_id not in _step_timers:
            _step_timers[workflow_id] = {}
        _step_timers[workflow_id][step_id] = time.monotonic()

    def stop_step_timer(self, workflow_id: str, step_id: str) -> float:
        """Returns elapsed seconds for the step"""
        start = _step_timers.get(workflow_id, {}).pop(step_id, None)
        if start is None:
            return 0.0
        elapsed = time.monotonic() - start
        # Update baseline
        self.ltm.update_step_baseline(workflow_id, step_id, elapsed)
        return elapsed

    def detect(self, workflow_id: str, current_step: str, completed_steps: List[str]) -> Dict:
        """Check if the current step is running longer than the baseline"""
        if not current_step:
            return {"drifted": False}

        start_time = _step_timers.get(workflow_id, {}).get(current_step)
        if start_time is None:
            return {"drifted": False}

        elapsed = time.monotonic() - start_time
        baseline = self.ltm.get_step_baseline(workflow_id, current_step)

        if baseline and elapsed > baseline * DRIFT_MULTIPLIER:
            overrun = elapsed / baseline
            logger.warning(
                f"DRIFT DETECTED | workflow={workflow_id} step={current_step} "
                f"elapsed={elapsed:.1f}s baseline={baseline:.1f}s overrun={overrun:.1f}x"
            )
            audit.log(
                agent_id="drift_detector",
                action="DRIFT_DETECTED",
                workflow_id=workflow_id,
                step_name=current_step,
                output_summary=f"elapsed={elapsed:.1f}s baseline={baseline:.1f}s overrun={overrun:.1f}x",
                confidence=0.0,
            )
            return {
                "drifted": True,
                "step": current_step,
                "elapsed_seconds": elapsed,
                "baseline_seconds": baseline,
                "overrun_factor": overrun,
            }

        return {"drifted": False, "step": current_step, "elapsed_seconds": elapsed}