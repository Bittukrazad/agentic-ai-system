"""core/llm_client.py — Core LLM client facade.

Agents import from here rather than directly from llm/llm_client.py.
This keeps the import path stable if the LLM implementation changes,
and adds a thin retry/backoff layer on top of the raw client.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from llm.llm_client import LLMClient as _LLMClient
from utils.logger import get_logger

logger = get_logger(__name__)

# Re-export so agents can do: from core.llm_client import get_llm_client
__all__ = ["get_llm_client", "CoreLLMClient"]

_MAX_BACKOFF_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


class CoreLLMClient:
    """
    Thin facade over LLMClient that adds:
      - Automatic exponential backoff on transient errors
      - Per-call timeout
      - Simple token-budget guard (refuse calls over MAX_TOKENS)

    Used by decision_agent, decision_extractor, and verification_agent.
    """

    MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1500"))

    def __init__(self):
        self._inner = _LLMClient()

    async def complete(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        timeout_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Call the LLM with automatic retry on failure.
        Returns parsed dict — never raises.
        """
        tokens = min(max_tokens or self.MAX_TOKENS, self.MAX_TOKENS)

        for attempt in range(1, _MAX_BACKOFF_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    self._inner.complete(prompt, max_tokens=tokens),
                    timeout=timeout_seconds,
                )
                return result
            except asyncio.TimeoutError:
                logger.warning(f"LLM timeout on attempt {attempt}/{_MAX_BACKOFF_RETRIES}")
            except Exception as e:
                logger.warning(f"LLM error attempt {attempt}/{_MAX_BACKOFF_RETRIES}: {e}")

            if attempt < _MAX_BACKOFF_RETRIES:
                wait = _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                await asyncio.sleep(wait)

        # All retries exhausted — return safe fallback
        logger.error("LLM all retries exhausted — returning fallback response")
        return {
            "decision": "fallback",
            "rationale": "LLM unavailable after retries",
            "action": "escalate",
            "params": {},
            "confidence": 0.0,
        }

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token"""
        return len(text) // 4


def get_llm_client() -> CoreLLMClient:
    """Factory — always returns the same singleton instance."""
    return _singleton


_singleton = CoreLLMClient()
