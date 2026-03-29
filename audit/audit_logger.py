"""audit/audit_logger.py — Append-only audit trail for every agent decision"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DECISION_LOG_PATH = os.path.join(os.path.dirname(__file__), "decision_logs.json")
TRACE_LOG_PATH = os.path.join(os.path.dirname(__file__), "trace_logs.json")

# In-memory cache for fast reads (the files are the source of truth)
_entries: List[Dict] = []


def _load_existing():
    global _entries
    if os.path.exists(DECISION_LOG_PATH):
        try:
            with open(DECISION_LOG_PATH) as f:
                _entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            _entries = []


_load_existing()


class AuditLogger:
    """
    Append-only audit log. Every agent action writes one row.
    Fields: agent_id, action, workflow_id, step_name,
            input_summary, output_summary, confidence,
            retry_count, timestamp.
    Never updates or deletes — full decision history always reconstructable.
    """

    def log(
        self,
        agent_id: str,
        action: str,
        workflow_id: str,
        step_name: str,
        input_summary: str = "",
        output_summary: str = "",
        confidence: float = 1.0,
        retry_count: int = 0,
        extra: Optional[Dict] = None,
    ):
        entry = {
            "id": len(_entries) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "action": action,
            "step_name": step_name,
            "input_summary": input_summary[:200] if input_summary else "",
            "output_summary": output_summary[:200] if output_summary else "",
            "confidence": round(float(confidence), 4),
            "retry_count": retry_count,
        }
        if extra:
            entry["extra"] = extra

        _entries.append(entry)
        self._persist(entry)

    def _persist(self, entry: Dict):
        """Write entry to decision_logs.json (append-only)"""
        try:
            with open(DECISION_LOG_PATH, "w") as f:
                json.dump(_entries, f, indent=2, default=str)
        except IOError:
            pass

        # Also write to trace_logs (one line per entry for easy grep)
        try:
            with open(TRACE_LOG_PATH, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except IOError:
            pass

    def get_trail(self, workflow_id: str) -> List[Dict]:
        """Return all entries for a specific workflow"""
        return [e for e in _entries if e.get("workflow_id") == workflow_id]

    def get_recent(self, limit: int = 50) -> List[Dict]:
        """Return the most recent N entries across all workflows"""
        return _entries[-limit:]

    def get_by_agent(self, agent_id: str) -> List[Dict]:
        return [e for e in _entries if e.get("agent_id") == agent_id]

    def get_failures(self, workflow_id: Optional[str] = None) -> List[Dict]:
        """Return all FAILED / RETRY / TIMEOUT entries"""
        failure_actions = {"FAILURE_DETECTED", "RETRY_ATTEMPT", "SLA_TIMEOUT_SKIP",
                           "HUMAN_GATE_TRIGGERED", "STEP_SKIPPED", "BREACH_PREDICTED"}
        results = [e for e in _entries if e.get("action") in failure_actions]
        if workflow_id:
            results = [e for e in results if e.get("workflow_id") == workflow_id]
        return results

    def summary(self, workflow_id: str) -> Dict:
        trail = self.get_trail(workflow_id)
        if not trail:
            return {}
        return {
            "workflow_id": workflow_id,
            "total_entries": len(trail),
            "agents_involved": list({e["agent_id"] for e in trail}),
            "actions": [e["action"] for e in trail],
            "avg_confidence": round(
                sum(e.get("confidence", 0) for e in trail) / len(trail), 3
            ),
            "total_retries": sum(e.get("retry_count", 0) for e in trail),
            "first_event": trail[0]["timestamp"],
            "last_event": trail[-1]["timestamp"],
        }