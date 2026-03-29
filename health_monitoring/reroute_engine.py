"""health_monitoring/reroute_engine.py — Dynamically rewrites active workflow step list"""
from datetime import datetime, timezone
from typing import Dict, List

from memory.short_term_memory import ShortTermMemory
from audit.audit_logger import AuditLogger
from utils.logger import get_logger

logger = get_logger(__name__)
audit = AuditLogger()

# Active workflow step registries {workflow_id: [steps]}
_active_steps: Dict[str, List[Dict]] = {}


class RerouteEngine:
    """
    Dynamically modifies the active step list of a running workflow.
    Strategies:
      - skip_non_critical: remove steps where critical=False
      - expedite: move high-priority steps earlier
      - escalate: notify senior stakeholder and continue
    """

    @staticmethod
    def register_workflow(workflow_id: str, steps: List[Dict]):
        _active_steps[workflow_id] = list(steps)

    def reroute(self, workflow_id: str, reason: str, strategy: str = "skip_non_critical"):
        """Apply rerouting strategy to a running workflow"""
        steps = _active_steps.get(workflow_id, [])
        if not steps:
            logger.warning(f"No steps registered for rerouting | workflow={workflow_id}")
            return

        original_count = len(steps)
        if strategy == "skip_non_critical":
            new_steps = [s for s in steps if s.get("critical", True)]
        elif strategy == "expedite":
            critical = [s for s in steps if s.get("critical", True)]
            optional = [s for s in steps if not s.get("critical", True)]
            new_steps = critical + optional
        else:
            new_steps = steps

        _active_steps[workflow_id] = new_steps
        skipped = original_count - len(new_steps)

        logger.warning(
            f"REROUTED | workflow={workflow_id} strategy={strategy} "
            f"skipped={skipped} steps_remaining={len(new_steps)} reason={reason}"
        )
        audit.log(
            agent_id="reroute_engine",
            action="WORKFLOW_REROUTED",
            workflow_id=workflow_id,
            step_name="reroute",
            input_summary=f"reason={reason} strategy={strategy}",
            output_summary=f"skipped={skipped} steps remaining={len(new_steps)}",
            confidence=0.0,
        )

    @staticmethod
    def get_active_steps(workflow_id: str) -> List[Dict]:
        return _active_steps.get(workflow_id, [])