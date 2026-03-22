"""
Exception Handler Module - Intelligent failure classification and routing.

Provides:
- Transient vs Deterministic error classification
- Smart retry decisions
- Escalation routing
- Fallback strategy selection
"""

from typing import Dict, Any, Optional, Tuple
from enum import Enum
import traceback
from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorClassification(Enum):
    """Classification of error types."""
    TRANSIENT = "transient"  # Temporary, should retry
    DETERMINISTIC = "deterministic"  # Permanent, don't retry
    UNKNOWN = "unknown"  # Unknown classification


class RoutingStrategy(Enum):
    """Strategy for handling the failure."""
    RETRY = "retry"  # Attempt retry with backoff
    FALLBACK = "fallback"  # Use fallback step
    ESCALATE = "escalate"  # Escalate to human/manager
    SKIP = "skip"  # Skip step and continue
    HALT = "halt"  # Stop workflow


class ExceptionHandler:
    """
    Intelligent exception classification and routing.
    
    Determines:
    1. Error type (transient vs deterministic)
    2. Recovery strategy (retry, fallback, escalate, etc.)
    3. Next step in workflow
    """
    
    # Transient error indicators
    TRANSIENT_PATTERNS = [
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "try again",
        "service unavailable",
        "503",
        "502",
        "429",
        "too many requests",
        "reset by peer",
        "broken pipe",
        "connection refused",
        "network unreachable",
        "temporarily",
        "intermittent",
        "transient"
    ]
    
    # Deterministic error indicators
    DETERMINISTIC_PATTERNS = [
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
        "syntax error",
        "assertion",
        "required",
        "does not exist",
        "cannot find",
        "failure is expected",
        "deterministic"
    ]
    
    def __init__(self, max_retries: int = 3):
        """
        Initialize exception handler.
        
        Args:
            max_retries: Default maximum retries
        """
        self.max_retries = max_retries
        self.error_history = []
    
    def classify_exception(self, error: Exception) -> ErrorClassification:
        """
        Classify exception as transient or deterministic.
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorClassification enum value
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check transient patterns
        for pattern in self.TRANSIENT_PATTERNS:
            if pattern in error_str or pattern in error_type:
                return ErrorClassification.TRANSIENT
        
        # Check deterministic patterns
        for pattern in self.DETERMINISTIC_PATTERNS:
            if pattern in error_str or pattern in error_type:
                return ErrorClassification.DETERMINISTIC
        
        # Special case: timeout exceptions are usually transient
        if error_type in ["timeout", "timeouterror", "asyncio.timeouterror"]:
            return ErrorClassification.TRANSIENT
        
        # Default: unknown
        return ErrorClassification.UNKNOWN
    
    def determine_routing_strategy(
        self,
        error: Exception,
        retry_count: int = 0,
        max_retries_allowed: Optional[int] = None,
        has_fallback: bool = False,
        has_escalation_path: bool = False
    ) -> RoutingStrategy:
        """
        Determine routing strategy based on error and context.
        
        Args:
            error: Exception that occurred
            retry_count: Current retry attempt count
            max_retries_allowed: Maximum retries allowed
            has_fallback: Whether fallback step is available
            has_escalation_path: Whether escalation is available
            
        Returns:
            RoutingStrategy enum value
        """
        if max_retries_allowed is None:
            max_retries_allowed = self.max_retries
        
        classification = self.classify_exception(error)
        
        # Transient errors should be retried
        if classification == ErrorClassification.TRANSIENT:
            if retry_count < max_retries_allowed:
                return RoutingStrategy.RETRY
            else:
                # Out of retries
                if has_escalation_path:
                    return RoutingStrategy.ESCALATE
                elif has_fallback:
                    return RoutingStrategy.FALLBACK
                else:
                    return RoutingStrategy.HALT
        
        # Deterministic errors should not be retried
        elif classification == ErrorClassification.DETERMINISTIC:
            if has_fallback:
                return RoutingStrategy.FALLBACK
            elif has_escalation_path:
                return RoutingStrategy.ESCALATE
            else:
                return RoutingStrategy.HALT
        
        # Unknown errors: conservative approach
        else:
            if retry_count < max_retries_allowed and has_escalation_path is False:
                # Try retry once more conservatively
                return RoutingStrategy.RETRY
            elif has_escalation_path:
                return RoutingStrategy.ESCALATE
            elif has_fallback:
                return RoutingStrategy.FALLBACK
            else:
                return RoutingStrategy.HALT
    
    def should_retry(
        self,
        error: Exception,
        retry_count: int,
        max_retries: int
    ) -> bool:
        """
        Quick check if error should be retried.
        
        Args:
            error: Exception
            retry_count: Current retry count
            max_retries: Maximum allowed retries
            
        Returns:
            True if should retry
        """
        if retry_count >= max_retries:
            return False
        
        classification = self.classify_exception(error)
        return classification == ErrorClassification.TRANSIENT
    
    def handle_exception(
        self,
        error: Exception,
        workflow_id: str,
        step_id: str,
        step_name: str,
        retry_count: int = 0,
        max_retries: int = 3,
        has_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Comprehensive exception handling.
        
        Args:
            error: Exception to handle
            workflow_id: Workflow ID
            step_id: Step ID
            step_name: Step name
            retry_count: Current retry count
            max_retries: Maximum retries
            has_fallback: Whether fallback available
            
        Returns:
            Handling decision dictionary
        """
        classification = self.classify_exception(error)
        strategy = self.determine_routing_strategy(
            error,
            retry_count,
            max_retries,
            has_fallback
        )
        
        decision = {
            "error_message": str(error),
            "error_type": type(error).__name__,
            "classification": classification.value,
            "routing_strategy": strategy.value,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "should_retry": strategy == RoutingStrategy.RETRY,
            "should_escalate": strategy == RoutingStrategy.ESCALATE,
            "should_fallback": strategy == RoutingStrategy.FALLBACK,
            "traceback": traceback.format_exc()
        }
        
        # Log handling decision
        logger.error(
            f"Exception handled",
            extra={
                "workflow_id": workflow_id,
                "step_id": step_id,
                "step_name": step_name,
                "classification": classification.value,
                "routing_strategy": strategy.value,
                "retry_count": retry_count
            }
        )
        
        # Track in history
        self.error_history.append({
            "workflow_id": workflow_id,
            "step_id": step_id,
            "decision": decision
        })
        
        return decision
    
    def get_error_history(self, workflow_id: Optional[str] = None) -> list:
        """
        Retrieve error history.
        
        Args:
            workflow_id: Optional filter by workflow
            
        Returns:
            List of error handling decisions
        """
        if workflow_id:
            return [
                entry for entry in self.error_history
                if entry.get("workflow_id") == workflow_id
            ]
        return self.error_history
    
    def clear_history(self) -> None:
        """Clear error history."""
        self.error_history = []


class RetryDecision:
    """Result of retry decision logic."""
    
    def __init__(
        self,
        should_retry: bool,
        delay_seconds: float = 0,
        reason: str = "",
        max_retries: int = 3,
        retry_count: int = 0
    ):
        """Initialize retry decision."""
        self.should_retry = should_retry
        self.delay_seconds = delay_seconds
        self.reason = reason
        self.max_retries = max_retries
        self.retry_count = retry_count
    
    @property
    def retries_remaining(self) -> int:
        """Calculate retries remaining."""
        return max(0, self.max_retries - self.retry_count)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "should_retry": self.should_retry,
            "delay_seconds": self.delay_seconds,
            "reason": self.reason,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "retries_remaining": self.retries_remaining
        }
