"""core/retry.py — Retry engine with exponential backoff, jitter, and circuit breaker.

Used by:
  - orchestrator/exception_handler.py  (agent-step retries)
  - core/llm_client.py                 (LLM API call retries)
  - tools/*.py                         (external tool call retries)

Three public surfaces:
  1. RetryPolicy         — configuration dataclass (immutable, composable)
  2. RetryExecutor       — async engine that runs a callable with the policy
  3. CircuitBreaker      — per-agent open/half-open/closed state machine
  4. @with_retry         — decorator for quick one-line usage

Example — agent step retry:
    from core.retry import RetryExecutor, AGENT_STEP_POLICY

    async def my_step(enriched=False):
        return await decision_agent.decide("key", state, enriched=enriched)

    result = await RetryExecutor(AGENT_STEP_POLICY).run(
        my_step,
        workflow_id=state.workflow_id,
        step_name="decide_access",
    )

Example — LLM call retry:
    from core.retry import RetryExecutor, LLM_CALL_POLICY

    result = await RetryExecutor(LLM_CALL_POLICY).run(llm.complete, prompt)

Example — decorator:
    from core.retry import with_retry, LLM_CALL_POLICY

    @with_retry(LLM_CALL_POLICY)
    async def call_api(url: str) -> dict: ...
"""
from __future__ import annotations

import asyncio
import functools
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# RetryPolicy — immutable configuration object
# ---------------------------------------------------------------------------

class BackoffStrategy(str, Enum):
    FIXED       = "fixed"          # wait = base_delay every time
    LINEAR      = "linear"         # wait = base_delay * attempt
    EXPONENTIAL = "exponential"    # wait = base_delay * 2^(attempt-1)
    FIBONACCI   = "fibonacci"      # wait = fib(attempt) * base_delay


@dataclass(frozen=True)
class RetryPolicy:
    """
    Immutable retry configuration.
    Create once, share across agents. Use the pre-built policies below
    or construct a custom one.

    Fields:
        max_attempts      Total number of attempts (1 = no retry).
        base_delay        Base wait time in seconds between attempts.
        max_delay         Cap on total wait time per attempt.
        backoff           Backoff strategy enum.
        jitter            If True, add random ±25% jitter to each wait.
        retryable_errors  Exception types that trigger a retry.
                          Empty tuple = retry on ANY exception.
        on_retry          Optional callback(attempt, error, wait) for logging.
        name              Human-readable name for audit logs.
    """
    max_attempts:     int   = 3
    base_delay:       float = 1.0
    max_delay:        float = 30.0
    backoff:          BackoffStrategy = BackoffStrategy.EXPONENTIAL
    jitter:           bool  = True
    retryable_errors: Tuple[Type[Exception], ...] = ()  # () = retry on any
    name:             str   = "default"

    def wait_for(self, attempt: int) -> float:
        """Compute the wait time (in seconds) before attempt N (1-indexed)."""
        if self.backoff == BackoffStrategy.FIXED:
            wait = self.base_delay
        elif self.backoff == BackoffStrategy.LINEAR:
            wait = self.base_delay * attempt
        elif self.backoff == BackoffStrategy.EXPONENTIAL:
            wait = self.base_delay * (2 ** (attempt - 1))
        elif self.backoff == BackoffStrategy.FIBONACCI:
            wait = self.base_delay * _fib(attempt)
        else:
            wait = self.base_delay

        if self.jitter:
            wait *= random.uniform(0.75, 1.25)

        return min(wait, self.max_delay)

    def should_retry(self, exc: Exception) -> bool:
        """Return True if this exception type is retryable under this policy."""
        if not self.retryable_errors:
            return True   # retry on anything
        return isinstance(exc, self.retryable_errors)


def _fib(n: int) -> int:
    a, b = 1, 1
    for _ in range(max(0, n - 1)):
        a, b = b, a + b
    return a


# ---------------------------------------------------------------------------
# Pre-built policies — import and use directly
# ---------------------------------------------------------------------------

AGENT_STEP_POLICY = RetryPolicy(
    name="agent_step",
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    jitter=True,
)
"""Standard policy for orchestrator agent steps."""

LLM_CALL_POLICY = RetryPolicy(
    name="llm_call",
    max_attempts=3,
    base_delay=2.0,
    max_delay=20.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    jitter=True,
    retryable_errors=(ConnectionError, TimeoutError, OSError),
)
"""LLM API call — retries on network errors with longer backoff."""

TOOL_CALL_POLICY = RetryPolicy(
    name="tool_call",
    max_attempts=2,
    base_delay=0.5,
    max_delay=5.0,
    backoff=BackoffStrategy.LINEAR,
    jitter=False,
)
"""Slack, email, calendar, DB tool calls — fast, short backoff."""

HEALTH_CHECK_POLICY = RetryPolicy(
    name="health_check",
    max_attempts=2,
    base_delay=0.2,
    max_delay=2.0,
    backoff=BackoffStrategy.FIXED,
    jitter=False,
)
"""Internal health check reads — minimal delay."""

NO_RETRY_POLICY = RetryPolicy(
    name="no_retry",
    max_attempts=1,
    base_delay=0.0,
    max_delay=0.0,
)
"""Use when you want zero retries (e.g. human gate, one-shot actions)."""


# ---------------------------------------------------------------------------
# RetryResult — returned by RetryExecutor.run()
# ---------------------------------------------------------------------------

@dataclass
class RetryResult:
    success:      bool
    value:        Any = None
    error:        Optional[Exception] = None
    attempts:     int = 0
    total_wait:   float = 0.0
    policy_name:  str = ""

    def unwrap(self) -> Any:
        """Return the value on success, raise the last exception on failure."""
        if self.success:
            return self.value
        raise self.error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Attempt history — used by audit_logger integration
# ---------------------------------------------------------------------------

@dataclass
class AttemptRecord:
    attempt:    int
    started_at: str
    elapsed_ms: int
    success:    bool
    error:      Optional[str] = None
    wait_ms:    int = 0


# ---------------------------------------------------------------------------
# RetryExecutor — the async engine
# ---------------------------------------------------------------------------

class RetryExecutor:
    """
    Async retry engine. Call .run(fn, *args, **kwargs) to execute
    the callable with the configured RetryPolicy.

    Integrates with the audit system: pass workflow_id + step_name
    as kwargs and RetryExecutor will emit retry log entries.
    """

    def __init__(self, policy: RetryPolicy = AGENT_STEP_POLICY):
        self.policy = policy
        self._history: List[AttemptRecord] = []

    async def run(
        self,
        fn: Callable,
        *args: Any,
        workflow_id: str = "",
        step_name: str = "",
        on_final_failure: Optional[Callable] = None,
        **kwargs: Any,
    ) -> RetryResult:
        """
        Execute fn(*args, **kwargs) with the retry policy.
        Returns a RetryResult — never raises.
        """
        self._history.clear()
        total_wait = 0.0
        last_error: Optional[Exception] = None

        for attempt in range(1, self.policy.max_attempts + 1):
            started = time.monotonic()
            start_iso = datetime.now(timezone.utc).isoformat()

            try:
                value = fn(*args, **kwargs)
                if asyncio.iscoroutine(value):
                    value = await value

                elapsed_ms = int((time.monotonic() - started) * 1000)
                self._history.append(AttemptRecord(
                    attempt=attempt, started_at=start_iso,
                    elapsed_ms=elapsed_ms, success=True,
                ))
                self._audit_success(workflow_id, step_name, attempt, elapsed_ms)
                return RetryResult(
                    success=True, value=value,
                    attempts=attempt, total_wait=total_wait,
                    policy_name=self.policy.name,
                )

            except Exception as exc:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                last_error = exc

                if not self.policy.should_retry(exc):
                    # Non-retryable error — fail immediately
                    self._history.append(AttemptRecord(
                        attempt=attempt, started_at=start_iso,
                        elapsed_ms=elapsed_ms, success=False,
                        error=str(exc),
                    ))
                    logger.warning(
                        f"[{self.policy.name}] Non-retryable error on attempt {attempt}: {exc}"
                    )
                    break

                wait = self.policy.wait_for(attempt) if attempt < self.policy.max_attempts else 0
                total_wait += wait

                self._history.append(AttemptRecord(
                    attempt=attempt, started_at=start_iso, elapsed_ms=elapsed_ms,
                    success=False, error=str(exc), wait_ms=int(wait * 1000),
                ))
                self._audit_retry(workflow_id, step_name, attempt, exc, wait)

                if attempt < self.policy.max_attempts:
                    logger.warning(
                        f"[{self.policy.name}] Attempt {attempt}/{self.policy.max_attempts} "
                        f"failed: {exc!r} — retrying in {wait:.2f}s"
                    )
                    await asyncio.sleep(wait)

        # All attempts exhausted
        logger.error(
            f"[{self.policy.name}] All {self.policy.max_attempts} attempts failed "
            f"for step '{step_name}'. Last error: {last_error!r}"
        )
        if on_final_failure:
            try:
                await _maybe_await(on_final_failure(last_error))
            except Exception:
                pass

        self._audit_exhausted(workflow_id, step_name, self.policy.max_attempts)
        return RetryResult(
            success=False, error=last_error,
            attempts=self.policy.max_attempts,
            total_wait=total_wait,
            policy_name=self.policy.name,
        )

    @property
    def history(self) -> List[AttemptRecord]:
        return list(self._history)

    def _audit_retry(self, workflow_id: str, step_name: str, attempt: int, exc: Exception, wait: float):
        if not workflow_id:
            return
        try:
            from audit.audit_logger import AuditLogger
            AuditLogger().log(
                agent_id=f"retry_executor[{self.policy.name}]",
                action="RETRY_ATTEMPT",
                workflow_id=workflow_id,
                step_name=step_name,
                input_summary=f"attempt={attempt}/{self.policy.max_attempts}",
                output_summary=f"error={str(exc)[:80]} wait={wait:.2f}s",
                confidence=0.0,
                retry_count=attempt,
            )
        except Exception:
            pass

    def _audit_success(self, workflow_id: str, step_name: str, attempt: int, elapsed_ms: int):
        if not workflow_id or attempt == 1:
            return   # First-attempt success needs no special audit entry
        try:
            from audit.audit_logger import AuditLogger
            AuditLogger().log(
                agent_id=f"retry_executor[{self.policy.name}]",
                action="RETRY_SUCCESS",
                workflow_id=workflow_id,
                step_name=step_name,
                output_summary=f"succeeded on attempt {attempt} in {elapsed_ms}ms",
                confidence=1.0,
                retry_count=attempt - 1,
            )
        except Exception:
            pass

    def _audit_exhausted(self, workflow_id: str, step_name: str, max_attempts: int):
        if not workflow_id:
            return
        try:
            from audit.audit_logger import AuditLogger
            AuditLogger().log(
                agent_id=f"retry_executor[{self.policy.name}]",
                action="RETRY_EXHAUSTED",
                workflow_id=workflow_id,
                step_name=step_name,
                output_summary=f"all {max_attempts} attempts failed",
                confidence=0.0,
                retry_count=max_attempts,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CircuitBreaker — per-agent open/half-open/closed state machine
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED      = "closed"       # Normal operation — requests pass through
    OPEN        = "open"         # Failing — requests are blocked immediately
    HALF_OPEN   = "half_open"    # Probing — one trial request allowed


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a named service (e.g. an external API or agent).

    States:
        CLOSED    → failures accumulate; stays CLOSED until failure_threshold hit
        OPEN      → all calls fail fast for recovery_timeout seconds
        HALF_OPEN → one trial call allowed; success → CLOSED, failure → OPEN

    Usage:
        cb = CircuitBreaker("openai_api", failure_threshold=5, recovery_timeout=60)

        if cb.allow_request():
            try:
                result = await llm.complete(prompt)
                cb.record_success()
            except Exception as e:
                cb.record_failure()
                raise
        else:
            raise CircuitOpenError("openai_api circuit is OPEN")
    """
    name:              str
    failure_threshold: int   = 5     # failures before OPEN
    recovery_timeout:  float = 60.0  # seconds in OPEN before HALF_OPEN
    success_threshold: int   = 2     # successes in HALF_OPEN before CLOSED

    # Runtime state (not frozen — mutable)
    _state:             CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count:     int          = field(default=0, init=False)
    _success_count:     int          = field(default=0, init=False)
    _last_failure_time: float        = field(default=0.0, init=False)
    _total_calls:       int          = field(default=0, init=False)
    _total_failures:    int          = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        self._maybe_transition_to_half_open()
        return self._state

    def allow_request(self) -> bool:
        """Return True if the circuit allows this request through."""
        self._total_calls += 1
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            logger.warning(f"Circuit OPEN: {self.name} — blocking request")
            return False
        # HALF_OPEN: allow one probe
        return True

    def record_success(self):
        """Call after a successful request."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Call after a failed request."""
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._transition_to_open()

    def reset(self):
        """Manually reset to CLOSED (e.g. after ops intervention)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        logger.info(f"Circuit RESET: {self.name}")

    def stats(self) -> Dict[str, Any]:
        return {
            "name":           self.name,
            "state":          self._state,
            "failure_count":  self._failure_count,
            "total_calls":    self._total_calls,
            "total_failures": self._total_failures,
            "failure_rate":   round(self._total_failures / max(self._total_calls, 1), 3),
        }

    def _maybe_transition_to_half_open(self):
        if (self._state == CircuitState.OPEN and
                time.monotonic() - self._last_failure_time >= self.recovery_timeout):
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
            logger.info(f"Circuit HALF_OPEN: {self.name} — probe allowed")

    def _transition_to_open(self):
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()
        logger.error(f"Circuit OPEN: {self.name} — blocked for {self.recovery_timeout}s")

    def _transition_to_closed(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        logger.info(f"Circuit CLOSED: {self.name} — fully recovered")


class CircuitOpenError(Exception):
    """Raised when a request is rejected by an OPEN circuit breaker."""
    pass


# ---------------------------------------------------------------------------
# Circuit breaker registry — one breaker per named service
# ---------------------------------------------------------------------------

_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """Get or create a named CircuitBreaker (singleton per name)."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _breakers[name]


def all_circuit_stats() -> List[Dict[str, Any]]:
    """Return stats for every registered circuit breaker."""
    return [cb.stats() for cb in _breakers.values()]


# ---------------------------------------------------------------------------
# @with_retry decorator
# ---------------------------------------------------------------------------

def with_retry(policy: RetryPolicy = AGENT_STEP_POLICY):
    """
    Decorator that wraps an async function with the given RetryPolicy.

    Usage:
        @with_retry(LLM_CALL_POLICY)
        async def call_openai(prompt: str) -> dict:
            ...

    The decorated function returns a RetryResult.
    Call .unwrap() to get the raw value or re-raise the last error.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> RetryResult:
            executor = RetryExecutor(policy)
            return await executor.run(fn, *args, **kwargs)
        wrapper._retry_policy = policy   # attach for introspection
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _maybe_await(result: Any) -> Any:
    if asyncio.iscoroutine(result):
        return await result
    return result