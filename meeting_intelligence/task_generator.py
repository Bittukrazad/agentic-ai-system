"""meeting_intelligence/task_generator.py — Creates Task objects from extracted action items"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List


class TaskGenerator:
    """
    Converts raw action_items from DecisionExtractor into
    structured Task objects with IDs, deadlines, and priorities.
    """

    # Keyword→priority mapping
    PRIORITY_KEYWORDS = {
        "urgent": "high", "asap": "high", "immediately": "high", "critical": "high",
        "soon": "medium", "next week": "medium", "this week": "medium",
        "eventually": "low", "when possible": "low", "low priority": "low",
    }

    def generate(self, extracted: Dict) -> List[Dict]:
        """Convert extracted action items into Task objects"""
        action_items = extracted.get("action_items", [])
        tasks = []

        for item in action_items:
            task = self._build_task(item)
            tasks.append(task)

        return tasks

    def _build_task(self, item: Dict) -> Dict:
        task_id = str(uuid.uuid4())[:8]
        description = item.get("description", "")
        deadline_hint = item.get("deadline_hint", "next meeting")
        priority = self._detect_priority(description + " " + deadline_hint)
        deadline = self._parse_deadline(deadline_hint)

        return {
            "id": f"task_{task_id}",
            "title": self._extract_title(description),
            "description": description,
            "owner_hint": item.get("owner_hint", item.get("speaker", "")),
            "owner": "",            # Filled by OwnerAssigner
            "owner_email": "",      # Filled by OwnerAssigner
            "priority": priority,
            "deadline": deadline.isoformat(),
            "deadline_hint": deadline_hint,
            "status": "pending",
            "source": "meeting_intelligence",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_title(self, description: str) -> str:
        """First sentence, capped at 60 chars"""
        first = description.split(".")[0].split("\n")[0].strip()
        return first[:60] + ("..." if len(first) > 60 else "")

    def _detect_priority(self, text: str) -> str:
        text_lower = text.lower()
        for keyword, priority in self.PRIORITY_KEYWORDS.items():
            if keyword in text_lower:
                return priority
        return "medium"

    def _parse_deadline(self, hint: str) -> datetime:
        now = datetime.now(timezone.utc)
        hint_lower = hint.lower()
        if any(w in hint_lower for w in ["today", "eod", "end of day"]):
            return now + timedelta(hours=8)
        if any(w in hint_lower for w in ["tomorrow"]):
            return now + timedelta(days=1)
        if any(w in hint_lower for w in ["this week", "end of week", "friday"]):
            return now + timedelta(days=5)
        if any(w in hint_lower for w in ["next week", "next meeting"]):
            return now + timedelta(days=7)
        if any(w in hint_lower for w in ["this month", "end of month"]):
            return now + timedelta(days=30)
        # Default: 7 days
        return now + timedelta(days=7)