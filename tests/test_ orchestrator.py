"""tests/test_orchestrator.py — Unit tests for orchestrator and state management"""
import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state_manager import WorkflowState, StateManager
from orchestrator.sla_manager import SLAManager
from memory.short_term_memory import ShortTermMemory


class TestWorkflowState(unittest.TestCase):

    def setUp(self):
        ShortTermMemory.init()
        self.state = WorkflowState(
            workflow_id="wf_test_001",
            workflow_type="meeting",
            payload={"transcript": "Alice: Let's test this."},
        )

    def test_initial_status(self):
        self.assertEqual(self.state.status, "running")
        self.assertEqual(self.state.retry_count, 0)
        self.assertEqual(self.state.completed_steps, [])

    def test_mark_step_complete(self):
        self.state.mark_step_complete("parse_transcript")
        self.assertIn("parse_transcript", self.state.completed_steps)
        self.assertEqual(self.state.retry_count, 0)  # reset after success

    def test_mark_step_failed(self):
        self.state.mark_step_failed("extract_decisions", "LLM error")
        self.assertEqual(self.state.retry_count, 1)
        self.assertEqual(self.state.last_error, "LLM error")
        self.assertEqual(len(self.state.error_history), 1)

    def test_multiple_failures_increment_retry(self):
        self.state.mark_step_failed("step_a", "error 1")
        self.state.mark_step_failed("step_a", "error 2")
        self.assertEqual(self.state.retry_count, 2)
        self.assertEqual(self.state.total_retries, 2)

    def test_retry_resets_after_success(self):
        self.state.mark_step_failed("step_a", "error")
        self.state.mark_step_complete("step_a")
        self.assertEqual(self.state.retry_count, 0)

    def test_add_task(self):
        task = {"id": "t1", "title": "Test task", "owner": "Alice"}
        self.state.add_task(task)
        self.assertEqual(len(self.state.tasks), 1)
        self.assertEqual(self.state.tasks[0]["title"], "Test task")

    def test_to_dict_and_from_dict(self):
        self.state.mark_step_complete("step_1")
        self.state.add_task({"id": "t1", "title": "Task"})
        d = self.state.to_dict()
        restored = WorkflowState.from_dict(d)
        self.assertEqual(restored.workflow_id, self.state.workflow_id)
        self.assertEqual(restored.completed_steps, ["step_1"])
        self.assertEqual(len(restored.tasks), 1)


class TestStateManager(unittest.TestCase):

    def setUp(self):
        ShortTermMemory.init()

    def test_save_and_load(self):
        state = WorkflowState("wf_save_001", "onboarding", {})
        state.mark_step_complete("fetch_employee")
        StateManager.save(state)
        loaded = StateManager.load("wf_save_001")
        self.assertIsNotNone(loaded)
        self.assertIn("fetch_employee", loaded.completed_steps)

    def test_load_nonexistent(self):
        result = StateManager.load("wf_does_not_exist")
        self.assertIsNone(result)

    def test_update_status(self):
        state = WorkflowState("wf_status_001", "procurement", {})
        StateManager.save(state)
        StateManager.update_status("wf_status_001", "completed")
        data = ShortTermMemory.get_state("wf_status_001")
        self.assertEqual(data["status"], "completed")


class TestSLAManager(unittest.TestCase):

    def test_sla_not_breached_immediately(self):
        sla = SLAManager("wf_sla_001", "meeting")
        self.assertFalse(sla.is_breached())

    def test_remaining_minutes_positive(self):
        sla = SLAManager("wf_sla_002", "meeting")
        remaining = sla.remaining_minutes()
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 61)  # meeting SLA is 1 hour

    def test_breach_probability_at_start(self):
        sla = SLAManager("wf_sla_003", "onboarding")
        prob = sla.breach_probability(0.0)
        # At the very start, probability should be low
        self.assertLess(prob, 0.5)

    def test_sla_durations(self):
        for wf_type, expected_hours in [("meeting", 1), ("onboarding", 48), ("procurement", 72), ("contract", 96)]:
            sla = SLAManager(f"wf_{wf_type}", wf_type)
            remaining = sla.remaining_minutes()
            self.assertAlmostEqual(remaining, expected_hours * 60, delta=2)


class TestShortTermMemory(unittest.TestCase):

    def setUp(self):
        ShortTermMemory.init()

    def test_set_and_get(self):
        ShortTermMemory.set("test_key", {"value": 42})
        result = ShortTermMemory.get("test_key")
        self.assertEqual(result["value"], 42)

    def test_get_missing_key(self):
        result = ShortTermMemory.get("nonexistent_key", default="fallback")
        self.assertEqual(result, "fallback")

    def test_set_state_and_get_state(self):
        ShortTermMemory.set_state("wf_001", {"status": "running", "step": "parse"})
        state = ShortTermMemory.get_state("wf_001")
        self.assertEqual(state["status"], "running")

    def test_human_approval_flow(self):
        ShortTermMemory.set_state("wf_approval", {"status": "running"})
        ShortTermMemory.set_human_approval(
            workflow_id="wf_approval",
            step_name="decide_access",
            approved=True,
            human_input={"access_level": "DEVELOPER"},
            approver_id="manager_001",
        )
        approval = ShortTermMemory.get_human_approval("wf_approval", "decide_access")
        self.assertIsNotNone(approval)
        self.assertTrue(approval["approved"])
        self.assertEqual(approval["approver_id"], "manager_001")

    def test_all_workflow_ids(self):
        ShortTermMemory.set_state("wf_a", {"status": "running"})
        ShortTermMemory.set_state("wf_b", {"status": "completed"})
        ids = ShortTermMemory.all_workflow_ids()
        self.assertIn("wf_a", ids)
        self.assertIn("wf_b", ids)

    def test_clear_workflow(self):
        ShortTermMemory.set_state("wf_clear", {"data": "x"})
        ShortTermMemory.set("wf_clear:data:source", {"stuff": 1})
        ShortTermMemory.clear_workflow("wf_clear")
        self.assertIsNone(ShortTermMemory.get_state("wf_clear"))


if __name__ == "__main__":
    unittest.main(verbosity=2)