"""llm/prompts.py — All LLM prompt templates centralised in one place"""
from typing import Any, Dict


class PromptLibrary:
    """
    Single source of truth for every LLM prompt used in the system.
    Changing a prompt here updates it system-wide.
    Templates support variable injection via context dict.
    """

    _TEMPLATES: Dict[str, str] = {

        # ── Meeting Intelligence ─────────────────────────────────────────
        "extract_decisions": """
You are an expert meeting analyst. Extract ALL decisions and action items from the transcript below.

Speakers identified: {speakers}

Transcript:
{transcript}

{enriched_note}

Return ONLY valid JSON with this exact structure:
{{
  "decisions": [
    {{"id": "dec_1", "description": "...", "made_by": "speaker name"}}
  ],
  "action_items": [
    {{
      "id": "ai_1",
      "description": "...",
      "owner_hint": "person responsible",
      "deadline_hint": "by when (e.g. next Friday, EOD, next week)",
      "priority": "high|medium|low"
    }}
  ],
  "blockers": [
    {{"description": "...", "raised_by": "speaker name"}}
  ],
  "follow_ups": ["question or topic needing clarification"],
  "summary": "2-sentence summary of the meeting"
}}

Be thorough. Every commitment mentioned ("I will", "we need to", "let's do", "assigned to") is an action item.
""",

        # ── Verification ─────────────────────────────────────────────────
        "verify_output": """
You are a quality reviewer. Score the following agent output for quality and completeness.

Workflow type: {workflow_type}
Output to review:
{result}

Rate the output from 0.0 to 1.0 where:
  1.0 = complete, accurate, all required fields present
  0.7 = mostly complete, minor gaps
  0.5 = partially complete, significant gaps
  0.3 = incomplete, major issues
  0.0 = empty or incorrect

Return ONLY valid JSON:
{{"score": 0.85, "issues": ["list any specific issues"], "passed": true}}
""",

        # ── Enterprise Workflow Decisions ────────────────────────────────
        "decide_access_level": """
You are an IT security manager. Determine the appropriate system access level for a new employee.

Employee data:
{fetched_data}

Access levels:
- STANDARD: email, Slack, basic tools
- DEVELOPER: email, Slack, GitHub, Jira, AWS dev
- MANAGER: all above + admin panels, reporting
- ADMIN: full access

Consider their role and department. Return ONLY valid JSON:
{{
  "decision": "STANDARD|DEVELOPER|MANAGER|ADMIN",
  "rationale": "brief justification",
  "action": "provision_access",
  "params": {{"systems": ["email", "slack"]}},
  "confidence": 0.9
}}
""",

        "decide_approval_route": """
You are a procurement compliance officer. Determine the approval route for a purchase order.

Vendor and PO data:
{fetched_data}

Approval rules:
{fetched_data}

Rules:
- Below ₹50,000: auto-approve
- ₹50,000–₹2,00,000: manager approval
- ₹2,00,001–₹10,00,000: director approval
- Above ₹10,00,000: CFO approval

Return ONLY valid JSON:
{{
  "decision": "auto_approve|manager|director|cfo",
  "rationale": "brief justification",
  "action": "route_approval",
  "params": {{"approver": "approver@company.com", "sla_hours": 24}},
  "confidence": 0.95
}}
""",

        "verify_approval_received": """
You are a procurement workflow manager. Check if an approval has been received.

Workflow context:
{fetched_data}

Return ONLY valid JSON:
{{
  "decision": "approved|pending|rejected|timeout",
  "rationale": "what you found",
  "action": "proceed|wait|escalate",
  "params": {{}},
  "confidence": 0.85
}}
""",

        "decide_legal_review": """
You are a legal operations manager. Determine if a contract requires legal team review.

Contract data:
{fetched_data}

Legal review required if:
- Contract value > ₹5,00,000
- Duration > 12 months
- International parties involved
- Custom IP or liability clauses present

Return ONLY valid JSON:
{{
  "decision": "required|not_required",
  "rationale": "brief justification",
  "action": "route_to_legal|skip_legal",
  "params": {{"urgency": "standard|urgent"}},
  "confidence": 0.9
}}
""",

        "track_contract_signature": """
You are a contract manager. Check the status of a contract awaiting signature.

Contract context:
{fetched_data}

Return ONLY valid JSON:
{{
  "decision": "signed|pending|expired|rejected",
  "rationale": "current status assessment",
  "action": "execute|follow_up|escalate|void",
  "params": {{}},
  "confidence": 0.8
}}
""",
    }

    @classmethod
    def get(cls, key: str, context: Dict[str, Any], enriched: bool = False) -> str:
        """Retrieve and render a prompt template with context variables"""
        template = cls._TEMPLATES.get(key, cls._FALLBACK_TEMPLATE)

        # Add enrichment note if this is a retry
        context["enriched_note"] = (
            "NOTE: This is a retry attempt. The previous extraction was incomplete. "
            "Please be extra thorough and look for any missed action items."
            if enriched else ""
        )

        # Safely render — missing keys become empty string
        try:
            return template.format_map(_SafeDict(context))
        except Exception:
            return template

    _FALLBACK_TEMPLATE = """
You are a helpful AI assistant processing an enterprise workflow step.

Context: {fetched_data}
Task: {workflow_type}

Analyse the context and return a structured JSON decision with keys:
decision, rationale, action, params, confidence (0.0-1.0).
"""


class _SafeDict(dict):
    """dict subclass that returns empty string for missing keys instead of raising KeyError"""
    def __missing__(self, key):
        return ""