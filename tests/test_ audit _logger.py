"""tests/test_audit_logger.py — Unit tests for the audit trail"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from audit.audit_logger import AuditLogger


class TestAuditLogger(unittest.TestCase):

    def setUp(self):
        self.audit = AuditLogger()
        self.wf_id = "wf_audit_test_001"

    def test_log_creates_entry(self):
        before = len(self.audit.get_trail(self.wf_id))
        self.audit.log(
            agent_id="test_agent",
            action="TEST_ACTION",
            workflow_id=self.wf_id,
            step_name="test_step",
            output_summary="test output",
            confidence=0.9,
        )
        after = len(self.audit.get_trail(self.wf_id))
        self.assertEqual(after, before + 1)

    def test_entry_has_required_fields(self):
        self.audit.log(
            agent_id="data_agent",
            action="DATA_FETCHED",
            workflow_id=self.wf_id,
            step_name="fetch_employee",
            input_summary="employee_id=EMP001",
            output_summary="name=Alice",
            confidence=1.0,
            retry_count=0,
        )
        trail = self.audit.get_trail(self.wf_id)
        entry = trail[-1]
        self.assertIn("timestamp", entry)
        self.assertIn("workflow_id", entry)
        self.assertIn("agent_id", entry)
        self.assertIn("action", entry)
        self.assertIn("confidence", entry)
        self.assertEqual(entry["agent_id"], "data_agent")
        self.assertEqual(entry["action"], "DATA_FETCHED")

    def test_get_trail_filters_by_workflow(self):
        other_wf = "wf_other_999"
        self.audit.log("agent_a", "ACTION_A", self.wf_id, "step_a", confidence=1.0)
        self.audit.log("agent_b", "ACTION_B", other_wf, "step_b", confidence=1.0)
        trail = self.audit.get_trail(self.wf_id)
        for entry in trail:
            self.assertEqual(entry["workflow_id"], self.wf_id)

    def test_get_recent_returns_n_entries(self):
        wf_id = "wf_recent_test"
        for i in range(10):
            self.audit.log("agent", f"ACTION_{i}", wf_id, "step", confidence=0.8)
        recent = self.audit.get_recent(limit=5)
        self.assertLessEqual(len(recent), 5)

    def test_confidence_clamped_to_float(self):
        self.audit.log("agent", "ACTION", self.wf_id, "step", confidence=0.753)
        trail = self.audit.get_trail(self.wf_id)
        entry = trail[-1]
        self.assertIsInstance(entry["confidence"], float)

    def test_get_failures(self):
        wf_id = "wf_failures"
        self.audit.log("exc_handler", "FAILURE_DETECTED", wf_id, "step", confidence=0.0)
        self.audit.log("exc_handler", "RETRY_ATTEMPT", wf_id, "step", confidence=0.0)
        self.audit.log("orchestrator", "STEP_COMPLETE", wf_id, "step", confidence=1.0)
        failures = self.audit.get_failures(wf_id)
        self.assertEqual(len(failures), 2)

    def test_summary(self):
        wf_id = "wf_summary_test"
        self.audit.log("agent_a", "STEP_COMPLETE", wf_id, "step_1", confidence=0.9)
        self.audit.log("agent_b", "STEP_COMPLETE", wf_id, "step_2", confidence=0.8)
        summary = self.audit.summary(wf_id)
        self.assertEqual(summary["workflow_id"], wf_id)
        self.assertGreaterEqual(summary["total_entries"], 2)
        self.assertIn("agent_a", summary["agents_involved"])

    def test_input_output_truncated(self):
        long_text = "x" * 500
        self.audit.log("agent", "ACTION", self.wf_id, "step",
                       input_summary=long_text, output_summary=long_text, confidence=1.0)
        trail = self.audit.get_trail(self.wf_id)
        entry = trail[-1]
        self.assertLessEqual(len(entry["input_summary"]), 203)   # 200 + "..."
        self.assertLessEqual(len(entry["output_summary"]), 203)


if __name__ == "__main__":
    unittest.main(verbosity=2)