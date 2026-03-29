"""meeting_intelligence/owner_assigner.py — Maps speaker names to employee records"""
from typing import Dict, List
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Employee Directory ────────────────────────────────────────────────────────
# In production: replace with real HRMS API call (Workday, BambooHR etc.)
# Add your actual meeting participants here
EMPLOYEE_DIRECTORY = {
    # ── Your actual meeting people ────────────────────────────────────────────
    "arjun": {
        "name": "Arjun Sharma",
        "email": "arjun@company.com",
        "slack": "@arjun",
        "role": "Backend Developer",
        "department": "Engineering",
    },
    "priya": {
        "name": "Priya Patel",
        "email": "priya@company.com",
        "slack": "@priya",
        "role": "Frontend Developer",
        "department": "Engineering",
    },
    "sneha": {
        "name": "Sneha Reddy",
        "email": "sneha@company.com",
        "slack": "@sneha",
        "role": "QA Lead",
        "department": "QA",
    },
    "rahul": {
        "name": "Rahul Gupta",
        "email": "rahul@company.com",
        "slack": "@rahul",
        "role": "Engineering Manager",
        "department": "Engineering",
    },
    "divya": {
        "name": "Divya Sharma",
        "email": "divya@company.com",
        "slack": "@divya",
        "role": "Product Manager",
        "department": "Product",
    },

    # ── Generic fallbacks ─────────────────────────────────────────────────────
    "alice":   {"name": "Alice Johnson",    "email": "alice@company.com",       "slack": "@alice",      "role": "Developer",  "department": "Engineering"},
    "bob":     {"name": "Bob Smith",        "email": "bob@company.com",         "slack": "@bob",        "role": "Developer",  "department": "Engineering"},
    "charlie": {"name": "Charlie Patel",    "email": "charlie@company.com",     "slack": "@charlie",    "role": "Developer",  "department": "Engineering"},
    "diana":   {"name": "Diana Chen",       "email": "diana@company.com",       "slack": "@diana",      "role": "Designer",   "department": "Design"},

    # ── Team / role references ────────────────────────────────────────────────
    "manager":     {"name": "Manager",          "email": "manager@company.com",     "slack": "@manager",     "role": "Manager", "department": "Management"},
    "team":        {"name": "Team",             "email": "team@company.com",        "slack": "#general",     "role": "Team",    "department": "General"},
    "engineering": {"name": "Engineering Team", "email": "engineering@company.com", "slack": "#engineering", "role": "Team",    "department": "Engineering"},
    "hr":          {"name": "HR Team",          "email": "hr@company.com",          "slack": "#hr",          "role": "HR",      "department": "HR"},
    "legal":       {"name": "Legal Team",       "email": "legal@company.com",       "slack": "#legal",       "role": "Legal",   "department": "Legal"},
    "qa":          {"name": "QA Team",          "email": "qa@company.com",          "slack": "#qa",          "role": "QA",      "department": "QA"},
    "product":     {"name": "Product Team",     "email": "product@company.com",     "slack": "#product",     "role": "Product", "department": "Product"},
    "devops":      {"name": "DevOps Team",      "email": "devops@company.com",      "slack": "#devops",      "role": "DevOps",  "department": "Engineering"},
}


class OwnerAssigner:
    """
    Maps owner_hint (speaker name or vague reference like 'team', 'we')
    to a concrete employee record with email and Slack handle.

    Resolution order:
      1. Exact match on directory key
      2. Fuzzy match on key or full name
      3. Multi-person hint (e.g. 'arjun and priya') — assigns to first found
      4. Fallback: manager
    """

    def assign(self, tasks: List[Dict]) -> List[Dict]:
        """Assign an owner to every task in the list"""
        return [self._resolve_owner(task) for task in tasks]

    def _resolve_owner(self, task: Dict) -> Dict:
        hint = task.get("owner_hint", "").strip().lower()

        # 1. Exact match
        if hint in EMPLOYEE_DIRECTORY:
            return self._apply(task, EMPLOYEE_DIRECTORY[hint])

        # 2. Fuzzy match — key or full name contains hint
        for key, emp in EMPLOYEE_DIRECTORY.items():
            if key in hint or hint in key or hint in emp["name"].lower():
                logger.debug(f"Fuzzy match: '{hint}' → {emp['name']}")
                return self._apply(task, emp)

        # 3. Multi-person hint (e.g. "arjun and priya") — assign to first match
        for key, emp in EMPLOYEE_DIRECTORY.items():
            if key in hint:
                logger.debug(f"Multi-person match: '{hint}' → first match {emp['name']}")
                return self._apply(task, emp)

        # 4. Fallback: assign to manager
        task["assignment_note"] = f"Could not resolve '{hint}' — assigned to manager"
        logger.warning(f"Could not resolve owner '{hint}', assigned to manager")
        return self._apply(task, EMPLOYEE_DIRECTORY["manager"])

    def _apply(self, task: Dict, emp: Dict) -> Dict:
        """Apply employee record to the task"""
        task["owner"]       = emp["name"]
        task["owner_email"] = emp["email"]
        task["owner_slack"] = emp.get("slack", "")
        task["owner_role"]  = emp.get("role", "")
        task["owner_dept"]  = emp.get("department", "")
        logger.debug(f"Assigned '{task.get('title','')[:40]}' → {emp['name']} ({emp['email']})")
        return task