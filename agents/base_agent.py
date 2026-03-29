"""agents/base_agent.py — Abstract base for all specialist agents"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from audit.audit_logger import AuditLogger
from utils.logger import get_logger


class BaseAgent(ABC):
    """
    Every specialist agent inherits from this.
    Provides: logging, audit writing, confidence scoring helpers.
    """

    def __init__(self):
        self.audit = AuditLogger()
        self.logger = get_logger(self.__class__.__name__)

    @property
    def agent_id(self) -> str:
        return self.__class__.__name__.lower().replace("agent", "_agent")

    def log_action(self, action: str, workflow_id: str, step_name: str,
                   input_summary: str = "", output_summary: str = "",
                   confidence: float = 1.0, retry_count: int = 0):
        self.audit.log(
            agent_id=self.agent_id,
            action=action,
            workflow_id=workflow_id,
            step_name=step_name,
            input_summary=input_summary,
            output_summary=output_summary,
            confidence=confidence,
            retry_count=retry_count,
        )

    def score_confidence(self, result: dict) -> float:
        """Default confidence scorer — subclasses can override"""
        if not result:
            return 0.0
        if "confidence" in result:
            return float(result["confidence"])
        # Heuristic: more non-empty fields = higher confidence
        filled = sum(1 for v in result.values() if v)
        total = max(len(result), 1)
        return min(1.0, filled / total)