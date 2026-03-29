"""meeting_intelligence/decision_extractor.py — LLM-powered extraction of decisions and actions"""
import json
import re
from typing import Dict, List

from llm.llm_client import LLMClient
from llm.prompts import PromptLibrary
from utils.logger import get_logger

logger = get_logger(__name__)


class DecisionExtractor:
    """
    Calls LLM with the parsed transcript to extract:
    - Decisions made
    - Action items (who, what, by when)
    - Blockers raised
    - Follow-up questions
    Returns structured JSON output.
    """

    def __init__(self):
        self.llm = LLMClient()

    async def extract(self, parsed: Dict, enriched: bool = False) -> Dict:
        """Extract structured decisions from parsed transcript"""
        full_text = parsed.get("full_text", "")
        speakers = parsed.get("speakers", [])

        if not full_text:
            return {"decisions": [], "action_items": [], "blockers": [], "follow_ups": []}

        prompt = PromptLibrary.get(
            "extract_decisions",
            {"transcript": full_text[:6000], "speakers": speakers, "enriched": enriched},
        )

        try:
            raw_response = await self.llm.complete(prompt)
            extracted = self._parse_response(raw_response)
        except Exception as e:
            logger.warning(f"LLM extraction failed, using rule-based fallback: {e}")
            extracted = self._rule_based_extract(parsed)

        logger.info(
            f"Extracted | decisions={len(extracted.get('decisions', []))} "
            f"action_items={len(extracted.get('action_items', []))}"
        )
        return extracted

    def _parse_response(self, response: Dict) -> Dict:
        """Parse LLM response — handle both dict and raw string"""
        if isinstance(response, dict):
            return {
                "decisions": response.get("decisions", []),
                "action_items": response.get("action_items", []),
                "blockers": response.get("blockers", []),
                "follow_ups": response.get("follow_ups", []),
                "summary": response.get("summary", ""),
            }
        # Try JSON string
        text = str(response)
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"decisions": [], "action_items": [], "blockers": [], "follow_ups": []}

    def _rule_based_extract(self, parsed: Dict) -> Dict:
        """Fallback: keyword-based extraction when LLM is unavailable"""
        action_keywords = ["will", "should", "must", "needs to", "going to", "action:", "todo:", "assigned to"]
        decision_keywords = ["decided", "agreed", "approved", "confirmed", "resolved", "conclusion:"]
        blocker_keywords = ["blocked", "blocker", "issue:", "problem:", "concern:", "risk:"]

        action_items = []
        decisions = []
        blockers = []

        for seg in parsed.get("segments", []):
            text = seg.get("text", "").lower()
            speaker = seg.get("speaker", "Unknown")
            original = seg.get("text", "")

            for kw in action_keywords:
                if kw in text:
                    action_items.append({
                        "id": f"ai_{len(action_items)+1}",
                        "description": original[:120],
                        "speaker": speaker,
                        "owner_hint": speaker,
                        "deadline_hint": "next meeting",
                    })
                    break

            for kw in decision_keywords:
                if kw in text:
                    decisions.append({
                        "id": f"dec_{len(decisions)+1}",
                        "description": original[:120],
                        "made_by": speaker,
                    })
                    break

            for kw in blocker_keywords:
                if kw in text:
                    blockers.append({"description": original[:120], "raised_by": speaker})
                    break

        return {
            "decisions": decisions,
            "action_items": action_items,
            "blockers": blockers,
            "follow_ups": [],
            "summary": f"Extracted {len(decisions)} decisions and {len(action_items)} action items (rule-based).",
        }