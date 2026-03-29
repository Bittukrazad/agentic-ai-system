"""agents/monitoring_agent.py — Activates health monitoring subsystem"""
from agents.base_agent import BaseAgent
from health_monitoring.drift_detector import DriftDetector
from health_monitoring.bottleneck_predictor import BottleneckPredictor
from health_monitoring.anomaly_detector import AnomalyDetector


class MonitoringAgent(BaseAgent):
    """
    Activates and coordinates the health_monitoring subsystem.
    Runs parallel to the main workflow via APScheduler.
    """

    def __init__(self):
        super().__init__()
        self.drift = DriftDetector()
        self.bottleneck = BottleneckPredictor()
        self.anomaly = AnomalyDetector()

    async def check_workflow_health(self, state) -> dict:
        """Run all health checks for an active workflow"""
        wid = state.workflow_id
        results = {}

        drift = self.drift.detect(wid, state.current_step, state.completed_steps)
        results["drift"] = drift

        breach_prob = self.bottleneck.predict(wid, len(state.completed_steps), len(state.completed_steps) + 3)
        results["breach_probability"] = breach_prob

        anomaly = self.anomaly.detect(wid, state.to_dict() if hasattr(state, "to_dict") else {})
        results["anomaly"] = anomaly

        self.log_action(
            action="HEALTH_CHECK",
            workflow_id=wid,
            step_name="health_monitor",
            output_summary=f"drift={drift.get('drifted')} breach_prob={breach_prob:.2f}",
            confidence=1.0,
        )
        return results