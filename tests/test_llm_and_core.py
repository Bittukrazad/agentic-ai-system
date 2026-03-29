"""tests/test_llm_and_core.py — Tests for core module and LLM client (mock mode)"""
import asyncio
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCoreState(unittest.TestCase):

    def test_new_state_has_required_fields(self):
        from core.state import new_state
        state = new_state("wf_001", "meeting", {"transcript": "hello"})
        self.assertEqual(state["workflow_id"], "wf_001")
        self.assertEqual(state["workflow_type"], "meeting")
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["retry_count"], 0)
        self.assertEqual(state["completed_steps"], [])
        self.assertEqual(state["tasks"], [])

    def test_mark_step_complete(self):
        from core.state import new_state, mark_step_complete
        state = new_state("wf_002", "onboarding", {})
        state = mark_step_complete(state, "fetch_employee")
        self.assertIn("fetch_employee", state["completed_steps"])
        self.assertEqual(state["retry_count"], 0)

    def test_mark_step_failed_increments(self):
        from core.state import new_state, mark_step_failed
        state = new_state("wf_003", "procurement", {})
        state = mark_step_failed(state, "decide_approval", "LLM error")
        self.assertEqual(state["retry_count"], 1)
        self.assertEqual(state["total_retries"], 1)
        self.assertEqual(state["last_error"], "LLM error")
        self.assertEqual(len(state["error_history"]), 1)

    def test_completion_fraction(self):
        from core.state import new_state, mark_step_complete, completion_fraction
        state = new_state("wf_004", "contract", {})
        mark_step_complete(state, "step_1")
        mark_step_complete(state, "step_2")
        frac = completion_fraction(state, total_steps=4)
        self.assertAlmostEqual(frac, 0.5)

    def test_is_recovery_exhausted(self):
        from core.state import new_state, mark_step_failed, is_recovery_exhausted
        state = new_state("wf_005", "meeting", {}, max_retries=3)
        for _ in range(4):
            state = mark_step_failed(state, "some_step", "error")
        self.assertTrue(is_recovery_exhausted(state))

    def test_not_exhausted_within_limit(self):
        from core.state import new_state, mark_step_failed, is_recovery_exhausted
        state = new_state("wf_006", "meeting", {}, max_retries=3)
        state = mark_step_failed(state, "step", "error")
        self.assertFalse(is_recovery_exhausted(state))


class TestCorePrompts(unittest.TestCase):

    def test_list_prompts_returns_keys(self):
        from core.prompts import list_prompts
        keys = list_prompts()
        self.assertIsInstance(keys, list)
        self.assertGreater(len(keys), 0)

    def test_prompt_exists(self):
        from core.prompts import prompt_exists
        self.assertTrue(prompt_exists("extract_decisions"))
        self.assertFalse(prompt_exists("nonexistent_prompt_xyz"))

    def test_register_and_use_new_prompt(self):
        from core.prompts import register_prompt, prompt_exists, render_prompt
        register_prompt("test_custom_prompt", "Hello {name}!")
        self.assertTrue(prompt_exists("test_custom_prompt"))
        rendered = render_prompt("test_custom_prompt", {"name": "Alice"})
        self.assertIn("Alice", rendered)

    def test_validate_context_missing_key(self):
        from core.prompts import validate_context
        missing = validate_context("extract_decisions", {})
        self.assertIn("transcript", missing)

    def test_validate_context_complete(self):
        from core.prompts import validate_context
        missing = validate_context("extract_decisions", {"transcript": "some text"})
        self.assertEqual(missing, [])

    def test_render_prompt_safe_missing_keys(self):
        from core.prompts import render_prompt
        # Should not raise even with empty context
        result = render_prompt("decide_access_level", {})
        self.assertIsInstance(result, str)


class TestLLMClientMock(unittest.TestCase):

    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"

    def test_complete_returns_dict(self):
        from llm.llm_client import LLMClient
        client = LLMClient()
        result = asyncio.run(client.complete("extract decisions from this transcript"))
        self.assertIsInstance(result, dict)

    def test_extraction_mock_response(self):
        from llm.llm_client import LLMClient
        client = LLMClient()
        result = asyncio.run(client.complete("extract decisions action items"))
        self.assertIn("decisions", result)
        self.assertIn("action_items", result)
        self.assertIsInstance(result["action_items"], list)

    def test_access_decision_mock(self):
        from llm.llm_client import LLMClient
        client = LLMClient()
        result = asyncio.run(client.complete("decide access level for employee"))
        self.assertIn("decision", result)
        self.assertIn("confidence", result)
        self.assertGreater(float(result["confidence"]), 0)

    def test_core_llm_client_complete(self):
        from core.llm_client import get_llm_client
        client = get_llm_client()
        result = asyncio.run(client.complete("decide access level for new employee"))
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)

    def test_core_llm_client_estimate_tokens(self):
        from core.llm_client import get_llm_client
        client = get_llm_client()
        tokens = client.estimate_tokens("hello world this is a test")
        self.assertGreater(tokens, 0)


class TestCoreDatabaseFallback(unittest.TestCase):

    def test_create_all_tables_does_not_crash(self):
        """Should work even without SQLAlchemy installed."""
        from core.db import create_all_tables
        # Just ensure it doesn't raise
        create_all_tables()

    def test_get_session_returns_none_without_sqlalchemy(self):
        """In mock mode with no DB, get_session yields None gracefully."""
        from core.db import get_session
        with get_session() as session:
            # session may be None if SQLAlchemy unavailable — that is fine
            pass  # No assertion — just verifying no exception


if __name__ == "__main__":
    unittest.main(verbosity=2)
