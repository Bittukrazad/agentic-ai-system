"""orchestrator/workflow_engine.py — Executes workflow steps from JSON definition"""
import json
import os
from typing import List, Dict, Any

from orchestrator.state_manager import WorkflowState
from utils.logger import get_logger

logger = get_logger(__name__)

WORKFLOW_DIR = os.path.join(os.path.dirname(__file__), "..", "workflows")


class WorkflowEngine:
    """Loads workflow step definitions and dispatches each step to the right agent"""

    def __init__(self):
        self._workflows: Dict[str, List[Dict]] = {}
        self._load_all()

    def _load_all(self):
        mapping = {
            "meeting": "meeting_workflow.json",
            "onboarding": "employee_onboarding.json",
            "procurement": "procurement_to_payment.json",
            "contract": "contract_lifecycle.json",
        }
        for wf_type, filename in mapping.items():
            path = os.path.join(WORKFLOW_DIR, filename)
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                    self._workflows[wf_type] = data.get("steps", [])
                    logger.info(f"Loaded workflow '{wf_type}' with {len(self._workflows[wf_type])} steps")
            else:
                logger.warning(f"Workflow file not found: {path}")
                self._workflows[wf_type] = []

    def get_steps(self, workflow_type: str) -> List[Dict]:
        return self._workflows.get(workflow_type, [])

    def reroute(self, steps: List[Dict], skip_ids: List[str]) -> List[Dict]:
        """Remove specified steps for dynamic rerouting by health monitor"""
        return [s for s in steps if s.get("id") not in skip_ids]

    def get_step_agent(self, step: Dict) -> str:
        return step.get("agent", "")

    def get_step_id(self, step: Dict) -> str:
        return step.get("id", "")

    def get_step_name(self, step: Dict) -> str:
        return step.get("name", step.get("id", ""))

    def is_critical(self, step: Dict) -> bool:
        return step.get("critical", True)