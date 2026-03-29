"""agents/decision_agent.py — LLM-powered decision making"""
from typing import Any, Dict

from agents.base_agent import BaseAgent
from llm.llm_client import LLMClient
from llm.prompts import PromptLibrary
from memory.short_term_memory import ShortTermMemory
from memory.long_term_memory import LongTermMemory


class DecisionAgent(BaseAgent):
    """
    The only agent that directly calls the LLM.
    Returns structured decisions with confidence scores.
    """

    def __init__(self):
        super().__init__()
        self.llm = LLMClient()
        self.ltm = LongTermMemory()

    async def decide(self, prompt_key: str, state, enriched: bool = False) -> Dict[str, Any]:
        """Make an LLM-backed decision for the current workflow step"""
        workflow_id = state.workflow_id

        # Build context from short-term memory
        context = {
            "workflow_type": state.workflow_type,
            "fetched_data": state.fetched_data,
            "completed_steps": state.completed_steps,
            "payload": state.payload,
            "error_context": state.last_error if enriched else None,
            "historical_patterns": self.ltm.get_patterns(state.workflow_type),
        }

        prompt = PromptLibrary.get(prompt_key, context, enriched=enriched)
        self.logger.info(f"LLM decision | prompt={prompt_key} | workflow={workflow_id}")

        response = await self.llm.complete(prompt)
        confidence = self._score(response)

        result = {
            "decision": response.get("decision", ""),
            "rationale": response.get("rationale", ""),
            "action": response.get("action", ""),
            "params": response.get("params", {}),
            "confidence": confidence,
            "prompt_key": prompt_key,
        }

        self.log_action(
            action="DECISION_MADE",
            workflow_id=workflow_id,
            step_name=prompt_key,
            input_summary=f"prompt={prompt_key} enriched={enriched}",
            output_summary=f"decision={result['decision'][:60]} confidence={confidence:.2f}",
            confidence=confidence,
            retry_count=state.retry_count,
        )

        # Store in long-term memory for pattern learning
        self.ltm.store_decision(state.workflow_type, prompt_key, result)

        return result

    def _score(self, response: Dict) -> float:
        """Score response quality 0.0–1.0"""
        if not response:
            return 0.0
        score = 0.0
        if response.get("decision"):
            score += 0.4
        if response.get("rationale") and len(response["rationale"]) > 20:
            score += 0.3
        if response.get("action"):
            score += 0.2
        if response.get("confidence"):
            score = score * 0.5 + float(response["confidence"]) * 0.5
        return min(1.0, score + 0.1)   # base 0.1 for returning at all