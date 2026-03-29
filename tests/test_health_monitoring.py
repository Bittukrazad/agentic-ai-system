"""tests/test_health_monitoring.py — Unit tests for health monitoring subsystem"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from health_monitoring.drift_detector import DriftDetector
from health_monitoring.anomaly_detector import AnomalyDetector
from health_monitoring.reroute_engine import RerouteEngine


class TestDriftDetector(unittest.TestCase):

    def setUp(self):
        self.detector = DriftDetector()

    def test_no_drift_with_no_timer(self):
        result = self.detector.detect("wf_no_timer", "some_step", [])
        self.assertFalse(result["drifted"])

    def test_start_and_stop_timer(self):
        self.detector.start_step_timer("wf_timer_001", "step_a")
        elapsed = self.detector.stop_step_timer("wf_timer_001", "step_a")
        self.assertGreaterEqual(elapsed, 0.0)

    def test_detect_returns_dict(self):
        self.detector.start_step_timer("wf_detect_001", "step_x")
        result = self.detector.detect("wf_detect_001", "step_x", ["prev_step"])
        self.assertIsInstance(result, dict)
        self.assertIn("drifted", result)


class TestAnomalyDetector(unittest.TestCase):

    def setUp(self):
        self.detector = AnomalyDetector()

    def test_no_anomaly_clean_state(self):
        state = {"total_retries": 0, "error_history": []}
        result = self.detector.detect("wf_clean", state)
        self.assertFalse(result["anomalies_detected"])
        self.assertEqual(result["anomaly_count"], 0)

    def test_detects_high_retry_count(self):
        state = {"total_retries": 6, "error_history": [{"step": "s", "error": "e", "retry_count": 6, "timestamp": "now"}]}
        result = self.detector.detect("wf_retries", state)
        self.assertTrue(result["anomalies_detected"])
        metrics = [a["metric"] for a in result["anomalies"]]
        self.assertIn("retry_count", metrics)

    def test_detects_high_error_count(self):
        errors = [{"step": "s", "error": "e", "retry_count": 1, "timestamp": "t"} for _ in range(5)]
        state = {"total_retries": 1, "error_history": errors}
        result = self.detector.detect("wf_errors", state)
        self.assertTrue(result["anomalies_detected"])

    def test_returns_severity(self):
        state = {"total_retries": 8, "error_history": [{}] * 3}
        result = self.detector.detect("wf_severe", state)
        for anomaly in result["anomalies"]:
            self.assertIn("severity", anomaly)
            self.assertIn(anomaly["severity"], ["low", "medium", "high"])


class TestRerouteEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RerouteEngine()
        self.steps = [
            {"id": "step_1", "name": "Fetch data",      "critical": True},
            {"id": "step_2", "name": "Send welcome",    "critical": False},
            {"id": "step_3", "name": "Decide access",   "critical": True},
            {"id": "step_4", "name": "Create calendar", "critical": False},
            {"id": "step_5", "name": "Write DB",        "critical": True},
        ]

    def test_register_and_retrieve_steps(self):
        RerouteEngine.register_workflow("wf_re_001", self.steps)
        retrieved = RerouteEngine.get_active_steps("wf_re_001")
        self.assertEqual(len(retrieved), 5)

    def test_skip_non_critical_strategy(self):
        RerouteEngine.register_workflow("wf_re_002", self.steps)
        self.engine.reroute("wf_re_002", reason="test", strategy="skip_non_critical")
        remaining = RerouteEngine.get_active_steps("wf_re_002")
        # Only critical steps should remain
        self.assertEqual(len(remaining), 3)
        for step in remaining:
            self.assertTrue(step["critical"])

    def test_expedite_strategy_puts_critical_first(self):
        RerouteEngine.register_workflow("wf_re_003", self.steps)
        self.engine.reroute("wf_re_003", reason="test", strategy="expedite")
        remaining = RerouteEngine.get_active_steps("wf_re_003")
        self.assertEqual(len(remaining), 5)
        # First steps should be critical
        self.assertTrue(remaining[0]["critical"])
        self.assertTrue(remaining[1]["critical"])

    def test_no_steps_registered_handles_gracefully(self):
        # Should not raise
        self.engine.reroute("wf_nonexistent", reason="test")

    def test_empty_list_for_unregistered_workflow(self):
        steps = RerouteEngine.get_active_steps("wf_never_registered")
        self.assertEqual(steps, [])


class TestCommunicationRouter(unittest.TestCase):

    def setUp(self):
        from communication.router import MessageRouter
        self.router = MessageRouter()

    def test_register_and_route_direct(self):
        received = []

        def handler(payload):
            received.append(payload)

        self.router.register("test_event_xyz", handler)
        result = self.router.route_direct("test_event_xyz", {"data": "hello"})
        self.assertTrue(result)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["data"], "hello")

    def test_unknown_event_goes_to_dead_letter(self):
        result = self.router.route_direct("completely_unknown_event_abc", {"x": 1})
        self.assertFalse(result)
        dead = self.router.get_dead_letters()
        self.assertGreater(len(dead), 0)

    def test_clear_dead_letters(self):
        self.router.route_direct("no_such_event_999", {})
        self.router.clear_dead_letters()
        self.assertEqual(len(self.router.get_dead_letters()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
