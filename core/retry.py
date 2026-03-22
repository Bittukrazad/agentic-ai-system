"""
Retry Module - Exponential backoff retry logic for fault tolerance.

Provides:
- Exponential backoff decorator
- Jitter support to prevent thundering herd
- Configurable retry strategies
- Classification-aware retry decisions
"""

import asyncio
import time
from typing import Callable, TypeVar, Any, Optional, Type, Awaitable
from functools import wraps
import random

F = TypeVar("F", bound=Callable[..., Any])


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,)
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff calculation
            jitter: Whether to add random jitter to delays
            retryable_exceptions: Tuple of exceptions that should trigger retry
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add jitter: ±25% of the calculated delay
            jitter_amount = delay * 0.25
            delay = delay + random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0)


def retry_with_backoff(config: Optional[RetryConfig] = None) -> Callable[[F], F]:
    """
    Decorator for synchronous functions with exponential backoff retry.
    
    Args:
        config: RetryConfig instance (uses defaults if None)
        
    Returns:
        Decorated function
        
    Usage:
        @retry_with_backoff(RetryConfig(max_attempts=3))
        def risky_operation():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        print(f"Attempt {attempt + 1} failed. Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                    else:
                        print(f"All {config.max_attempts} attempts failed.")
            
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry failed but no exception was captured")
        
        return wrapper  # type: ignore
    
    return decorator


def retry_async(config: Optional[RetryConfig] = None) -> Callable[[Callable], Callable]:
    """
    Decorator for async functions with exponential backoff retry.
    
    Args:
        config: RetryConfig instance (uses defaults if None)
        
    Returns:
        Decorated async function
        
    Usage:
        @retry_async(RetryConfig(max_attempts=3))
        async def risky_async_operation():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        print(f"Attempt {attempt + 1} failed. Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                    else:
                        print(f"All {config.max_attempts} attempts failed.")
            
            if last_exception:
                raise last_exception
            raise RuntimeError("Async retry failed but no exception was captured")
        
        return wrapper
    
    return decorator


class TransientError(Exception):
    """Exception indicating a transient/temporary failure that should be retried."""
    pass


class DeterministicError(Exception):
    """Exception indicating a deterministic failure that should not be retried."""
    pass


def is_transient_error(error: Exception) -> bool:
    """
    Classify error as transient or deterministic.
    
    Args:
        error: Exception to classify
        
    Returns:
        True if transient, False if deterministic
    """
    # Transient errors
    transient_indicators = [
        "timeout",
        "ConnectionError",
        "ConnectionResetError",
        "ConnectionRefusedError",
        "TimeoutError",
        "502",
        "503",
        "504",
        "429",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
    ]
    
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    for indicator in transient_indicators:
        if indicator.lower() in error_str or indicator.lower() in error_type.lower():
            return True
    
    # Check if explicitly marked as transient
    if isinstance(error, TransientError):
        return True
    
    # Deterministic errors (do not retry)
    deterministic_indicators = [
        "validation failed",
        "not found",
        "404",
        "missing",
        "invalid",
        "unauthorized",
        "401",
        "403",
        "forbidden",
        "malformed",
        "type error",
    ]
    
    for indicator in deterministic_indicators:
        if indicator.lower() in error_str or indicator.lower() in error_type.lower():
            return False
    
    if isinstance(error, DeterministicError):
        return False
    
    # Default: treat as transient to be safe
    return True


def classify_error_for_routing(error: Exception) -> tuple[bool, str]:
    """
    Classify error and determine routing strategy.
    
    Args:
        error: Exception to classify
        
    Returns:
        Tuple of (should_retry, routing_strategy)
        - should_retry: Whether the operation should be retried
        - routing_strategy: "retry", "fallback", or "escalate"
    """
    if is_transient_error(error):
        return True, "retry"
    else:
        return False, "fallback"
