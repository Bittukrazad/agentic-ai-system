"""
Logger Module - Custom JSON logging with audit trail compliance.

Features:
- JSON formatted output for structured logging
- Integration with audit system
- Filtering to prevent conflicts with LogRecord attributes
- Hierarchical logger organization
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import sys


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    # Reserved LogRecord attributes that cannot be overridden
    RESERVED_ATTRIBUTES = {
        "name", "msg", "args", "created", "filename", "funcName", "levelname",
        "levelno", "lineno", "module", "msecs", "message", "pathname", "process",
        "processName", "relativeCreated", "thread", "threadName", "exc_info",
        "exc_text", "stack_info", "getMessage", "asctime"
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: LogRecord to format
            
        Returns:
            JSON string representation
        """
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Include extra fields, filtering reserved attributes
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in self.RESERVED_ATTRIBUTES and not key.startswith("_"):
                    log_obj[key] = value
        
        # Handle exceptions
        if record.exc_info and record.exc_info[0]:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_obj, default=str)


def setup_logging(name: str = "agentic-system", level: int = logging.INFO) -> logging.Logger:
    """
    Set up hierarchical logger with JSON formatting.
    
    Args:
        name: Logger name
        level: Logging level
        
    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    
    # Add handler if not already present
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create hierarchical logger.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class StructuredLogger:
    """Wrapper for structured logging with context preservation."""
    
    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = get_logger(name)
        self.context = {}
    
    def set_context(self, **kwargs: Any) -> None:
        """Set logging context."""
        self.context.update(kwargs)
    
    def clear_context(self) -> None:
        """Clear logging context."""
        self.context.clear()
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info with context."""
        extra = {**self.context, **kwargs}
        self.logger.info(message, extra=extra)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error with context."""
        extra = {**self.context, **kwargs}
        self.logger.error(message, extra=extra)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning with context."""
        extra = {**self.context, **kwargs}
        self.logger.warning(message, extra=extra)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug with context."""
        extra = {**self.context, **kwargs}
        self.logger.debug(message, extra=extra)


# Setup root logger on module import
setup_logging()
