"""tests/test_core_message_schema_and_retry.py
Tests for core/message_schema.py and core/retry.py
"""
import asyncio
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════════════
# message_schema tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMessageSchemaEnums(unittest.TestCase):

    def test_workflow_type_values(self):
        from core.message_schema import WorkflowType
        self.assertEqual(WorkflowType.MEETING.value, "meeting")
        self.assertEqual(WorkflowType.ONBOARDING.value, "onboarding")
        self.assertEqual(WorkflowType.PROCUREMENT.value, "procurement")
        self.assertEqual(WorkflowType.CONTRACT.value, "contract")

    def test_task_status_values(self):
        from core.message_schema import TaskStatus
        self.assertEqual(TaskStatus.PENDING.value, "pending")
        self.assertEqual(TaskStatus.DONE.value, "done")
        self.assertEqual(TaskStatus.STALLED.value, "stalled")

    def test_agent_action_enum_completeness(self):
        from core.message_schema import AgentAction
        # Core actions must exist
        required = [
            "WORKFLOW_STARTED", "WORKFLOW_COMPLETED", "DECISION_MADE",
            "RETRY_ATTEMPT", "HUMAN_GATE_TRIGGERED", "DRIFT_DETECTED",
            "BREACH_PREDICTED", "TASK_ESCALATED",
        ]
        for name in required:
            self.assertTrue(hasattr(AgentAction, name), f"AgentAction.{name} missing")

    def test_alert_level_values(self):
        from core.message_schema import AlertLevel
        self.assertEqual(AlertLevel.INFO.value, "INFO")
        self.assertEqual(AlertLevel.WARNING.value, "WARNING")
        self.assertEqual(AlertLevel.CRITICAL.value, "CRITICAL")


class TestBaseMessage(unittest.TestCase):

    def test_auto_generates_message_id(self):
        from core.message_schema import BaseMessage
        m1 = BaseMessage()
        m2 = BaseMessage()
        self.assertNotEqual(m1.message_id, m2.message_id)

    def test_auto_generates_timestamp(self):
        from core.message_schema import BaseMessage
        m = BaseMessage()
        self.assertTrue(m.timestamp.startswith("20"))  # ISO year prefix

    def test_to_dict_returns_dict(self):
        from core.message_schema import BaseMessage
        m = BaseMessage()
        d = m.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("message_id", d)
        self.assertIn("timestamp", d)
        self.assertIn("schema_version", d)

    def test_from_dict_round_trip(self):
        from core.message_schema import BaseMessage
        m = BaseMessage()
        d = m.to_dict()
        restored = BaseMessage.from_dict(d)
        self.assertEqual(restored.message_id, m.message_id)

    def test_from_dict_ignores_unknown_keys(self):
        from core.message_schema import BaseMessage
        d = {"message_id": "abc", "timestamp": "2026-01-01", "unknown_field": "ignored"}
        m = BaseMessage.from_dict(d)
        self.assertEqual(m.message_id, "abc")


class TestWorkflowTriggerMessage(unittest.TestCase):

    def test_valid_message_passes_validation(self):
        from core.message_schema import WorkflowTriggerMessage
        msg = WorkflowTriggerMessage(
            workflow_id="wf-001",
            workflow_type="meeting",
            payload={"transcript": "Alice: hello"},
        )
        errors = msg.validate()
        self.assertEqual(errors, [])

    def test_missing_workflow_id_fails(self):
        from core.message_schema import WorkflowTriggerMessage
        msg = WorkflowTriggerMessage(workflow_type="meeting")
        errors = msg.validate()
        self.assertTrue(any("workflow_id" in e for e in errors))

    def test_invalid_workflow_type_fails(self):
        from core.message_schema import WorkflowTriggerMessage
        msg = WorkflowTriggerMessage(workflow_id="wf-001", workflow_type="invalid_type")
        errors = msg.validate()
        self.assertTrue(any("workflow_type" in e for e in errors))

    def test_to_dict_has_all_fields(self):
        from core.message_schema import WorkflowTriggerMessage
        msg = WorkflowTriggerMessage(workflow_id="wf-001", workflow_type="onboarding")
        d = msg.to_dict()
        self.assertIn("workflow_id", d)
        self.assertIn("workflow_type", d)
        self.assertIn("priority", d)
        self.assertIn("message_id", d)


class TestDecisionMessage(unittest.TestCase):

    def test_valid_confidence_passes(self):
        from core.message_schema import DecisionMessage
        msg = DecisionMessage(
            workflow_id="wf-002", step_name="decide_access",
            decision="DEVELOPER", confidence=0.92,
        )
        errors = msg.validate()
        self.assertEqual(errors, [])

    def test_confidence_out_of_range_fails(self):
        from core.message_schema import DecisionMessage
        msg = DecisionMessage(workflow_id="wf-002", confidence=1.5)
        errors = msg.validate()
        self.assertTrue(any("confidence" in e for e in errors))

    def test_is_confident_property(self):
        from core.message_schema import DecisionMessage
        high = DecisionMessage(workflow_id="wf", confidence=0.9)
        low  = DecisionMessage(workflow_id="wf", confidence=0.3)
        self.assertTrue(high.is_confident)
        self.assertFalse(low.is_confident)


class TestTaskMessage(unittest.TestCase):

    def test_valid_task_passes(self):
        from core.message_schema import TaskMessage
        msg = TaskMessage(
            task_id="t-001", workflow_id="wf-003",
            title="Update deployment docs",
            owner="Alice Johnson", priority="high",
        )
        errors = msg.validate()
        self.assertEqual(errors, [])

    def test_missing_title_fails(self):
        from core.message_schema import TaskMessage
        msg = TaskMessage(task_id="t-001", workflow_id="wf-003")
        errors = msg.validate()
        self.assertTrue(any("title" in e for e in errors))

    def test_invalid_priority_fails(self):
        from core.message_schema import TaskMessage
        msg = TaskMessage(task_id="t-001", workflow_id="wf-003",
                          title="Task", priority="ultra-critical")
        errors = msg.validate()
        self.assertTrue(any("priority" in e for e in errors))


class TestAuditEntryMessage(unittest.TestCase):

    def test_valid_entry_passes(self):
        from core.message_schema import AuditEntryMessage
        msg = AuditEntryMessage(
            workflow_id="wf-004", agent_id="decision_agent",
            action="DECISION_MADE", step_name="decide_access",
            confidence=0.88,
        )
        errors = msg.validate()
        self.assertEqual(errors, [])

    def test_missing_agent_id_fails(self):
        from core.message_schema import AuditEntryMessage
        msg = AuditEntryMessage(workflow_id="wf-004", action="DECISION_MADE")
        errors = msg.validate()
        self.assertTrue(any("agent_id" in e for e in errors))


class TestSchemaRegistry(unittest.TestCase):

    def test_get_schema_returns_correct_class(self):
        from core.message_schema import get_schema, WorkflowTriggerMessage
        cls = get_schema("workflow_triggered")
        self.assertEqual(cls, WorkflowTriggerMessage)

    def test_get_schema_unknown_returns_none(self):
        from core.message_schema import get_schema
        self.assertIsNone(get_schema("totally_unknown_event"))

    def test_validate_message_valid_payload(self):
        from core.message_schema import validate_message
        errors = validate_message("workflow_triggered", {
            "workflow_id": "wf-005", "workflow_type": "meeting",
        })
        self.assertEqual(errors, [])

    def test_validate_message_invalid_payload(self):
        from core.message_schema import validate_message
        errors = validate_message("workflow_triggered", {
            "workflow_type": "bad_type",
        })
        self.assertGreater(len(errors), 0)

    def test_validate_message_unknown_event(self):
        from core.message_schema import validate_message
        errors = validate_message("no_such_event", {})
        self.assertGreater(len(errors), 0)

    def test_build_message_returns_instance(self):
        from core.message_schema import build_message, WorkflowTriggerMessage
        msg = build_message("workflow_triggered",
                             workflow_id="wf-006", workflow_type="meeting")
        self.assertIsInstance(msg, WorkflowTriggerMessage)

    def test_build_message_unknown_returns_none(self):
        from core.message_schema import build_message
        self.assertIsNone(build_message("no_such_event"))

    def test_all_registered_events_have_class(self):
        from core.message_schema import SCHEMA_REGISTRY
        for event_type, cls in SCHEMA_REGISTRY.items():
            self.assertTrue(callable(cls), f"{event_type} maps to non-callable")

    def test_schema_version_present(self):
        from core.message_schema import build_message
        msg = build_message("workflow_triggered",
                             workflow_id="wf-007", workflow_type="contract")
        self.assertEqual(msg.schema_version, "1.0")


# ═══════════════════════════════════════════════════════════════════════════
# retry tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRetryPolicy(unittest.TestCase):

    def test_fixed_backoff(self):
        from core.retry import RetryPolicy, BackoffStrategy
        p = RetryPolicy(base_delay=2.0, backoff=BackoffStrategy.FIXED, jitter=False)
        self.assertAlmostEqual(p.wait_for(1), 2.0)
        self.assertAlmostEqual(p.wait_for(3), 2.0)

    def test_linear_backoff(self):
        from core.retry import RetryPolicy, BackoffStrategy
        p = RetryPolicy(base_delay=1.0, backoff=BackoffStrategy.LINEAR, jitter=False)
        self.assertAlmostEqual(p.wait_for(1), 1.0)
        self.assertAlmostEqual(p.wait_for(3), 3.0)

    def test_exponential_backoff(self):
        from core.retry import RetryPolicy, BackoffStrategy
        p = RetryPolicy(base_delay=1.0, backoff=BackoffStrategy.EXPONENTIAL, jitter=False)
        self.assertAlmostEqual(p.wait_for(1), 1.0)
        self.assertAlmostEqual(p.wait_for(2), 2.0)
        self.assertAlmostEqual(p.wait_for(3), 4.0)

    def test_fibonacci_backoff(self):
        from core.retry import RetryPolicy, BackoffStrategy
        p = RetryPolicy(base_delay=1.0, backoff=BackoffStrategy.FIBONACCI, jitter=False)
        self.assertAlmostEqual(p.wait_for(1), 1.0)
        self.assertAlmostEqual(p.wait_for(2), 1.0)
        self.assertAlmostEqual(p.wait_for(3), 2.0)

    def test_max_delay_cap(self):
        from core.retry import RetryPolicy, BackoffStrategy
        p = RetryPolicy(base_delay=10.0, max_delay=5.0,
                        backoff=BackoffStrategy.EXPONENTIAL, jitter=False)
        self.assertLessEqual(p.wait_for(5), 5.0)

    def test_jitter_adds_variation(self):
        from core.retry import RetryPolicy, BackoffStrategy
        p = RetryPolicy(base_delay=4.0, backoff=BackoffStrategy.FIXED, jitter=True)
        waits = {p.wait_for(1) for _ in range(20)}
        self.assertGreater(len(waits), 1)  # jitter produces different values

    def test_should_retry_empty_means_any(self):
        from core.retry import RetryPolicy
        p = RetryPolicy()
        self.assertTrue(p.should_retry(ValueError("anything")))
        self.assertTrue(p.should_retry(RuntimeError("also retryable")))

    def test_should_retry_specific_types(self):
        from core.retry import RetryPolicy
        p = RetryPolicy(retryable_errors=(ConnectionError, TimeoutError))
        self.assertTrue(p.should_retry(ConnectionError()))
        self.assertFalse(p.should_retry(ValueError("not retryable")))


class TestPrebuiltPolicies(unittest.TestCase):

    def test_agent_step_policy_max_attempts(self):
        from core.retry import AGENT_STEP_POLICY
        self.assertEqual(AGENT_STEP_POLICY.max_attempts, 3)

    def test_llm_call_policy_longer_base_delay(self):
        from core.retry import LLM_CALL_POLICY, AGENT_STEP_POLICY
        self.assertGreater(LLM_CALL_POLICY.base_delay, AGENT_STEP_POLICY.base_delay)

    def test_no_retry_policy_single_attempt(self):
        from core.retry import NO_RETRY_POLICY
        self.assertEqual(NO_RETRY_POLICY.max_attempts, 1)

    def test_tool_call_policy_max_2(self):
        from core.retry import TOOL_CALL_POLICY
        self.assertEqual(TOOL_CALL_POLICY.max_attempts, 2)


class TestRetryExecutor(unittest.TestCase):

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_success_on_first_attempt(self):
        from core.retry import RetryExecutor, NO_RETRY_POLICY

        async def always_ok():
            return {"result": 42}

        result = self._run(RetryExecutor(NO_RETRY_POLICY).run(always_ok))
        self.assertTrue(result.success)
        self.assertEqual(result.value["result"], 42)
        self.assertEqual(result.attempts, 1)

    def test_retry_then_succeed(self):
        from core.retry import RetryExecutor, RetryPolicy, BackoffStrategy

        call_count = [0]
        async def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("not yet")
            return "ok"

        policy = RetryPolicy(max_attempts=3, base_delay=0.01,
                              backoff=BackoffStrategy.FIXED, jitter=False)
        result = self._run(RetryExecutor(policy).run(flaky))
        self.assertTrue(result.success)
        self.assertEqual(result.value, "ok")
        self.assertEqual(result.attempts, 3)

    def test_all_retries_exhausted(self):
        from core.retry import RetryExecutor, RetryPolicy, BackoffStrategy

        async def always_fail():
            raise RuntimeError("always bad")

        policy = RetryPolicy(max_attempts=3, base_delay=0.01,
                              backoff=BackoffStrategy.FIXED, jitter=False)
        result = self._run(RetryExecutor(policy).run(always_fail))
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, RuntimeError)
        self.assertEqual(result.attempts, 3)

    def test_unwrap_success(self):
        from core.retry import RetryExecutor, NO_RETRY_POLICY

        async def ok():
            return 99

        result = self._run(RetryExecutor(NO_RETRY_POLICY).run(ok))
        self.assertEqual(result.unwrap(), 99)

    def test_unwrap_raises_on_failure(self):
        from core.retry import RetryExecutor, RetryPolicy, BackoffStrategy

        async def fail():
            raise ValueError("boom")

        policy = RetryPolicy(max_attempts=1, base_delay=0, jitter=False)
        result = self._run(RetryExecutor(policy).run(fail))
        with self.assertRaises(ValueError):
            result.unwrap()

    def test_non_retryable_error_stops_immediately(self):
        from core.retry import RetryExecutor, RetryPolicy, BackoffStrategy

        call_count = [0]
        async def raises_non_retryable():
            call_count[0] += 1
            raise TypeError("non retryable")

        policy = RetryPolicy(
            max_attempts=3, base_delay=0.01, jitter=False,
            retryable_errors=(ConnectionError,),
        )
        result = self._run(RetryExecutor(policy).run(raises_non_retryable))
        self.assertFalse(result.success)
        self.assertEqual(call_count[0], 1)  # stopped after first attempt

    def test_history_records_attempts(self):
        from core.retry import RetryExecutor, RetryPolicy, BackoffStrategy

        call_count = [0]
        async def fail_twice():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ValueError("fail")
            return "done"

        policy = RetryPolicy(max_attempts=3, base_delay=0.01,
                              backoff=BackoffStrategy.FIXED, jitter=False)
        executor = RetryExecutor(policy)
        self._run(executor.run(fail_twice))
        self.assertEqual(len(executor.history), 3)

    def test_on_final_failure_callback(self):
        from core.retry import RetryExecutor, RetryPolicy

        called_with = []
        async def on_fail(err):
            called_with.append(err)

        async def always_fail():
            raise RuntimeError("done")

        policy = RetryPolicy(max_attempts=2, base_delay=0.01, jitter=False)
        self._run(RetryExecutor(policy).run(
            always_fail, on_final_failure=on_fail
        ))
        self.assertEqual(len(called_with), 1)
        self.assertIsInstance(called_with[0], RuntimeError)


class TestCircuitBreaker(unittest.TestCase):

    def test_starts_closed(self):
        from core.retry import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test_cb_closed")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_opens_after_threshold(self):
        from core.retry import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test_cb_opens", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_open_circuit_blocks_requests(self):
        from core.retry import CircuitBreaker
        cb = CircuitBreaker(name="test_cb_blocks", failure_threshold=1)
        cb.record_failure()
        self.assertFalse(cb.allow_request())

    def test_closed_circuit_allows_requests(self):
        from core.retry import CircuitBreaker
        cb = CircuitBreaker(name="test_cb_allows")
        self.assertTrue(cb.allow_request())

    def test_success_closes_half_open(self):
        from core.retry import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test_cb_recover",
                             failure_threshold=1, recovery_timeout=0.01,
                             success_threshold=2)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        time.sleep(0.02)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.record_success()
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_failure_in_half_open_reopens(self):
        from core.retry import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test_cb_reopen",
                             failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_manual_reset(self):
        from core.retry import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test_cb_reset", failure_threshold=1)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        cb.reset()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_stats(self):
        from core.retry import CircuitBreaker
        cb = CircuitBreaker(name="test_cb_stats", failure_threshold=5)
        cb.allow_request()
        cb.record_failure()
        cb.record_success()
        stats = cb.stats()
        self.assertEqual(stats["name"], "test_cb_stats")
        self.assertIn("state", stats)
        self.assertIn("failure_rate", stats)
        self.assertIn("total_calls", stats)

    def test_get_circuit_breaker_singleton(self):
        from core.retry import get_circuit_breaker
        cb1 = get_circuit_breaker("shared_service")
        cb2 = get_circuit_breaker("shared_service")
        self.assertIs(cb1, cb2)

    def test_all_circuit_stats(self):
        from core.retry import get_circuit_breaker, all_circuit_stats
        get_circuit_breaker("svc_a")
        get_circuit_breaker("svc_b")
        stats = all_circuit_stats()
        names = [s["name"] for s in stats]
        self.assertIn("svc_a", names)
        self.assertIn("svc_b", names)


class TestWithRetryDecorator(unittest.TestCase):

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_decorator_success(self):
        from core.retry import with_retry, NO_RETRY_POLICY

        @with_retry(NO_RETRY_POLICY)
        async def my_func(x):
            return x * 2

        result = self._run(my_func(21))
        self.assertTrue(result.success)
        self.assertEqual(result.unwrap(), 42)

    def test_decorator_attaches_policy(self):
        from core.retry import with_retry, LLM_CALL_POLICY

        @with_retry(LLM_CALL_POLICY)
        async def call_llm():
            return {}

        self.assertEqual(call_llm._retry_policy, LLM_CALL_POLICY)

    def test_decorator_preserves_function_name(self):
        from core.retry import with_retry, NO_RETRY_POLICY

        @with_retry(NO_RETRY_POLICY)
        async def my_named_function():
            return True

        self.assertEqual(my_named_function.__name__, "my_named_function")

    def test_decorator_retries_on_failure(self):
        from core.retry import with_retry, RetryPolicy, BackoffStrategy

        call_count = [0]
        policy = RetryPolicy(max_attempts=3, base_delay=0.01,
                              backoff=BackoffStrategy.FIXED, jitter=False)

        @with_retry(policy)
        async def unstable():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("not ready")
            return "ready"

        result = self._run(unstable())
        self.assertTrue(result.success)
        self.assertEqual(call_count[0], 2)


class TestCorePackageImports(unittest.TestCase):
    """Smoke-test that everything in core/__init__.py is importable."""

    def test_import_message_schema_from_core(self):
        from core import DecisionMessage, TaskMessage, build_message, validate_message
        self.assertTrue(callable(build_message))
        self.assertTrue(callable(validate_message))

    def test_import_retry_from_core(self):
        from core import (
            RetryExecutor, RetryPolicy, CircuitBreaker,
            AGENT_STEP_POLICY, LLM_CALL_POLICY, with_retry,
        )
        self.assertIsNotNone(AGENT_STEP_POLICY)
        self.assertIsNotNone(LLM_CALL_POLICY)

    def test_import_all_six_modules(self):
        from core import (
            # state
            new_state, mark_step_complete,
            # db
            get_session, create_all_tables,
            # llm
            get_llm_client,
            # prompts
            render_prompt, list_prompts,
            # message_schema
            build_message, validate_message, SCHEMA_REGISTRY,
            # retry
            RetryExecutor, AGENT_STEP_POLICY, with_retry,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
