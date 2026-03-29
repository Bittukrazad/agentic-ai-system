"""core/prompts.py — Core prompt management layer.

Re-exports PromptLibrary from llm/prompts.py and adds:
  - prompt_exists()     — check if a key is registered
  - list_prompts()      — introspect all available prompt keys
  - validate_context()  — warn if expected context keys are missing
  - register_prompt()   — add a new prompt at runtime (plugins / tests)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from llm.prompts import PromptLibrary, _SafeDict
from utils.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "PromptLibrary",
    "prompt_exists",
    "list_prompts",
    "validate_context",
    "register_prompt",
    "render_prompt",
]

# Expected context keys per prompt key (for validation / early warning)
_REQUIRED_CONTEXT: Dict[str, List[str]] = {
    "extract_decisions":     ["transcript"],
    "verify_output":         ["result", "workflow_type"],
    "decide_access_level":   ["fetched_data"],
    "decide_approval_route": ["fetched_data"],
    "decide_legal_review":   ["fetched_data"],
}


def prompt_exists(key: str) -> bool:
    """Return True if the prompt key is registered in PromptLibrary."""
    return key in PromptLibrary._TEMPLATES


def list_prompts() -> List[str]:
    """Return all registered prompt keys."""
    return sorted(PromptLibrary._TEMPLATES.keys())


def validate_context(key: str, context: Dict[str, Any]) -> List[str]:
    """
    Return a list of missing required context keys.
    Empty list means the context is complete.
    """
    required = _REQUIRED_CONTEXT.get(key, [])
    missing = [k for k in required if not context.get(k)]
    if missing:
        logger.warning(f"Prompt '{key}' missing context keys: {missing}")
    return missing


def register_prompt(key: str, template: str):
    """Register a new prompt template at runtime (useful for tests and plugins)."""
    if key in PromptLibrary._TEMPLATES:
        logger.warning(f"Overwriting existing prompt: {key}")
    PromptLibrary._TEMPLATES[key] = template
    logger.info(f"Prompt registered: {key}")


def render_prompt(key: str, context: Dict[str, Any], enriched: bool = False) -> str:
    """
    Render a prompt template with the given context.
    Validates context first, logs warnings for missing keys.
    """
    missing = validate_context(key, context)
    if missing:
        context = {**context, **{k: f"[MISSING: {k}]" for k in missing}}
    return PromptLibrary.get(key, context, enriched=enriched)
