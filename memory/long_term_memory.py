"""memory/long_term_memory.py — Persistent store for patterns, baselines, and history"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

STORE_PATH = os.path.join(os.path.dirname(__file__), "workflow_state_store.json")

# In-memory cache loaded from disk on init
_cache: Dict[str, Any] = {}


def _load():
    global _cache
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH) as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            _cache = {}


def _save():
    try:
        with open(STORE_PATH, "w") as f:
            json.dump(_cache, f, indent=2, default=str)
    except IOError:
        pass


_load()


class LongTermMemory:
    """
    Persistent store backed by a JSON file (swap for PostgreSQL / vector DB in production).
    Stores:
      - Decision history per workflow type
      - Step duration baselines per step
      - Workflow outcome statistics
      - Agent performance patterns
    """

    # ── Decisions ────────────────────────────────────────────────────────
    def store_decision(self, workflow_type: str, prompt_key: str, decision: Dict):
        key = f"decisions:{workflow_type}:{prompt_key}"
        history = _cache.get(key, [])
        history.append({
            "decision": decision.get("decision", ""),
            "confidence": decision.get("confidence", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 50
        _cache[key] = history[-50:]
        _save()

    def get_patterns(self, workflow_type: str) -> Dict:
        """Return decision patterns for context injection"""
        patterns = {}
        prefix = f"decisions:{workflow_type}:"
        for key in _cache:
            if key.startswith(prefix):
                prompt_key = key[len(prefix):]
                history = _cache[key]
                if history:
                    patterns[prompt_key] = {
                        "recent_decisions": [h["decision"] for h in history[-3:]],
                        "avg_confidence": sum(h["confidence"] for h in history) / len(history),
                    }
        return patterns

    # ── Step Baselines ───────────────────────────────────────────────────
    def update_step_baseline(self, workflow_type: str, step_id: str, duration_seconds: float):
        key = f"baseline:{workflow_type}:{step_id}"
        history = _cache.get(key, [])
        history.append(duration_seconds)
        history = history[-20:]   # rolling window of 20 runs
        _cache[key] = history
        _save()

    def get_step_baseline(self, workflow_type: str, step_id: str) -> Optional[float]:
        key = f"baseline:{workflow_type}:{step_id}"
        history = _cache.get(key, [])
        if not history:
            return None
        return sum(history) / len(history)

    # ── Outcome Stats ────────────────────────────────────────────────────
    def record_outcome(self, workflow_id: str, workflow_type: str, outcome: Dict):
        key = f"outcomes:{workflow_type}"
        records = _cache.get(key, [])
        records.append({
            "workflow_id": workflow_id,
            "completed_steps": outcome.get("completed_steps", 0),
            "total_retries": outcome.get("total_retries", 0),
            "sla_breached": outcome.get("sla_breached", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _cache[key] = records[-100:]
        _save()

    def get_outcome_stats(self, workflow_type: str) -> Dict:
        key = f"outcomes:{workflow_type}"
        records = _cache.get(key, [])
        if not records:
            return {}
        total = len(records)
        sla_breaches = sum(1 for r in records if r.get("sla_breached"))
        avg_retries = sum(r.get("total_retries", 0) for r in records) / total
        return {
            "total_runs": total,
            "sla_breach_rate": sla_breaches / total,
            "avg_retries_per_run": avg_retries,
        }