"""agents/verification_agent.py — Validates agent outputs via LLM cross-check"""
from typing import Any, Dict

from agents.base_agent import BaseAgent
from app.config import config
from llm.llm_client import LLMClient
from llm.prompts import PromptLibrary


class VerificationAgent(BaseAgent):
    """
    Runs a second LLM pass to validate decision_agent output.
    If score < CONFIDENCE_THRESHOLD, flags for exception_handler.
    """

    def __init__(self):
        super().__init__()
        self.llm = LLMClient()

    async def verify(self, result: Dict, state) -> Dict[str, Any]:
        """Verify the quality of an agent's output"""
        workflow_id = state.workflow_id

        # Score heuristically first
        score = self._heuristic_score(result)

        # If borderline, run LLM verification
        if 0.4 < score < 0.85:
            try:
                prompt = PromptLibrary.get("verify_output", {"result": result, "workflow_type": state.workflow_type})
                llm_check = await self.llm.complete(prompt)
                llm_score = float(llm_check.get("score", score))
                score = (score + llm_score) / 2
            except Exception:
                pass  # Fall back to heuristic score

        passed = score >= config.CONFIDENCE_THRESHOLD
        self.log_action(
            action="VERIFICATION_COMPLETE",
            workflow_id=workflow_id,
            step_name="verify",
            input_summary=f"result_keys={list(result.keys())}",
            output_summary=f"score={score:.2f} passed={passed}",
            confidence=score,
        )
        return {"passed": passed, "score": score}

    def _heuristic_score(self, result: Dict) -> float:
        if not result:
            return 0.0
        score = 0.0
        if result.get("decision"):
            score += 0.35
        if result.get("rationale") and len(str(result.get("rationale", ""))) > 15:
            score += 0.25
        if result.get("action"):
            score += 0.2
        if result.get("confidence"):
            score = max(score, float(result["confidence"]))
        return min(1.0, score + 0.2)