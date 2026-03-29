"""utils/logger.py — Centralised logging configuration"""
import logging
import os
import sys
from typing import Optional

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a named logger with consistent formatting.
    All loggers write to stdout; production can add file or cloud handlers.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    effective_level = getattr(logging, level or LOG_LEVEL, logging.INFO)
    logger.setLevel(effective_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(effective_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
    logger.propagate = False

    return logger


# Root logger configuration
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt=DATE_FORMAT, stream=sys.stdout)