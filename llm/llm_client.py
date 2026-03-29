"""llm/llm_client.py — Unified LLM API wrapper (OpenAI / Anthropic / mock)"""
import json
import os
import re
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Singleton wrapper around the configured LLM provider.
    Handles: API calls, JSON extraction, retry-safe error handling.

    Providers supported:
      - openai   → GPT-4o (default)
      - anthropic → Claude claude-sonnet-4-6
      - mock     → deterministic local responses (for testing / no API key)

    Set LLM_PROVIDER and the appropriate API key in .env.
    """

    _instance: Optional["LLMClient"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    @classmethod
    def init(cls):
        inst = cls()
        if not inst._initialised:
            inst._setup()
            inst._initialised = True

    def _setup(self):
        self.provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self.model = os.getenv("LLM_MODEL", "gpt-4o")
        self._openai_client = None
        self._anthropic_client = None

        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                try:
                    from openai import AsyncOpenAI
                    self._openai_client = AsyncOpenAI(api_key=api_key)
                    logger.info(f"LLM: OpenAI {self.model}")
                except ImportError:
                    logger.warning("openai package not installed — falling back to mock")
                    self.provider = "mock"
            else:
                logger.warning("OPENAI_API_KEY not set — using mock LLM")
                self.provider = "mock"

        elif self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if api_key:
                try:
                    import anthropic
                    self._anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
                    logger.info(f"LLM: Anthropic {self.model}")
                except ImportError:
                    logger.warning("anthropic package not installed — falling back to mock")
                    self.provider = "mock"
            else:
                logger.warning("ANTHROPIC_API_KEY not set — using mock LLM")
                self.provider = "mock"

        if self.provider == "mock":
            logger.info("LLM: mock mode (set LLM_PROVIDER + API key for real calls)")

    async def complete(self, prompt: str, max_tokens: int = 1500) -> Dict[str, Any]:
        """
        Send prompt to LLM, extract and return parsed JSON response.
        Always returns a dict — never raises on parse failure.
        """
        if not hasattr(self, "_initialised") or not self._initialised:
            self._setup()
            self._initialised = True

        if self.provider == "openai" and self._openai_client:
            return await self._call_openai(prompt, max_tokens)
        elif self.provider == "anthropic" and self._anthropic_client:
            return await self._call_anthropic(prompt, max_tokens)
        else:
            return self._mock_response(prompt)

    async def _call_openai(self, prompt: str, max_tokens: int) -> Dict:
        try:
            response = await self._openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an enterprise workflow AI. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
            return self._parse_json(text)
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            return self._mock_response(prompt)

    async def _call_anthropic(self, prompt: str, max_tokens: int) -> Dict:
        try:
            response = await self._anthropic_client.messages.create(
                model=self.model or "claude-sonnet-4-6",
                max_tokens=max_tokens,
                system="You are an enterprise workflow AI. Always respond with valid JSON only.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else "{}"
            return self._parse_json(text)
        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            return self._mock_response(prompt)

    def _parse_json(self, text: str) -> Dict:
        """Extract JSON from response, handle markdown code blocks"""
        text = text.strip()
        # Strip ```json ... ``` wrappers
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object within the text
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        logger.warning("LLM response was not valid JSON — returning structured fallback")
        return {"decision": "unknown", "rationale": text[:200], "confidence": 0.5}

    def _mock_response(self, prompt: str) -> Dict:
        """Deterministic mock responses keyed by prompt content"""
        prompt_lower = prompt.lower()

        if "extract" in prompt_lower and "decision" in prompt_lower:
            return {
                "decisions": [
                    {"id": "dec_1", "description": "Move to new deployment strategy", "made_by": "Team"}
                ],
                "action_items": [
                    {
                        "id": "ai_1",
                        "description": "Alice will update the deployment docs by Friday",
                        "owner_hint": "Alice",
                        "deadline_hint": "Friday",
                        "priority": "high",
                    },
                    {
                        "id": "ai_2",
                        "description": "Bob will set up the staging environment this week",
                        "owner_hint": "Bob",
                        "deadline_hint": "this week",
                        "priority": "medium",
                    },
                ],
                "blockers": [],
                "follow_ups": ["Confirm budget approval"],
                "summary": "Team agreed on new deployment strategy. Two action items assigned.",
            }

        if "access" in prompt_lower:
            return {
                "decision": "DEVELOPER",
                "rationale": "Employee is in Engineering department — standard developer access applies.",
                "action": "provision_access",
                "params": {"systems": ["email", "slack", "github", "jira"]},
                "confidence": 0.92,
            }

        if "approval" in prompt_lower and "route" in prompt_lower:
            return {
                "decision": "manager",
                "rationale": "Amount within manager approval threshold.",
                "action": "route_approval",
                "params": {"approver": "manager@company.com", "sla_hours": 24},
                "confidence": 0.95,
            }

        if "legal" in prompt_lower:
            return {
                "decision": "required",
                "rationale": "Contract value exceeds threshold — legal review required.",
                "action": "route_to_legal",
                "params": {"urgency": "standard"},
                "confidence": 0.88,
            }

        if "verify" in prompt_lower or "score" in prompt_lower:
            return {"score": 0.85, "issues": [], "passed": True}

        return {
            "decision": "proceed",
            "rationale": "Standard workflow step — proceeding as planned.",
            "action": "continue",
            "params": {},
            "confidence": 0.80,
        }