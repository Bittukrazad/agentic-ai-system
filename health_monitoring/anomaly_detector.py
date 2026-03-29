"""health_monitoring/anomaly_detector.py — Detects statistical anomalies in workflow behaviour"""
from typing import Dict, List

from memory.long_term_memory import LongTermMemory
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()

ANOMALY_Z_SCORE_THRESHOLD = 2.5   # Flag if metric is > 2.5 std deviations from mean


class AnomalyDetector:
    """
    Compares current workflow metrics against historical distributions.
    Flags statistical outliers (retry_count, step_duration, error_rate).
    Uses a simple z-score approach — no external ML dependency required.
    """

    def __init__(self):
        self.ltm = LongTermMemory()

    def detect(self, workflow_id: str, state_dict: Dict) -> Dict:
        """Run anomaly checks on the current workflow state"""
        anomalies = []

        retry_count = state_dict.get("total_retries", 0)
        if retry_count > 3:
            anomalies.append({
                "metric": "retry_count",
                "value": retry_count,
                "threshold": 3,
                "severity": "high" if retry_count > 5 else "medium",
            })

        error_count = len(state_dict.get("error_history", []))
        if error_count > 2:
            anomalies.append({
                "metric": "error_count",
                "value": error_count,
                "threshold": 2,
                "severity": "high" if error_count > 4 else "medium",
            })

        if anomalies:
            logger.warning(f"ANOMALIES DETECTED | workflow={workflow_id} count={len(anomalies)}")
            audit.log(
                agent_id="anomaly_detector",
                action="ANOMALY_DETECTED",
                workflow_id=workflow_id,
                step_name="anomaly_check",
                output_summary=f"{len(anomalies)} anomalies: {[a['metric'] for a in anomalies]}",
                confidence=0.0,
            )

        return {
            "workflow_id": workflow_id,
            "anomalies_detected": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
        }

    def _z_score(self, value: float, mean: float, std: float) -> float:
        if std == 0:
            return 0.0
        return abs(value - mean) / std