"""agents/data_agent.py — Fetches data from external sources"""
from typing import Any, Dict

from agents.base_agent import BaseAgent
from tools.db_tool import DBTool
from tools.api_clients import APIClients
from memory.short_term_memory import ShortTermMemory


class DataAgent(BaseAgent):
    """
    Fetches raw data from databases, APIs, file uploads.
    Never makes decisions — only retrieves and caches.
    """

    def __init__(self):
        super().__init__()
        self.db = DBTool()
        self.api = APIClients()

    async def fetch(self, source: str, params: Dict, state) -> Dict[str, Any]:
        """Fetch data from the specified source and cache in short-term memory"""
        workflow_id = state.workflow_id
        self.logger.info(f"Fetching | source={source} | workflow={workflow_id}")

        result = {}
        if source == "employee_db":
            result = await self._fetch_employee(params)
        elif source == "vendor_db":
            result = await self._fetch_vendor(params)
        elif source == "contract_db":
            result = await self._fetch_contract(params)
        elif source == "approval_rules":
            result = await self._fetch_approval_rules(params)
        elif source == "calendar":
            result = await self._fetch_calendar(params)
        else:
            result = {"source": source, "data": {}, "note": "unknown source"}

        # Cache in short-term memory
        cache_key = f"{workflow_id}:data:{source}"
        ShortTermMemory.set(cache_key, result)

        self.log_action(
            action="DATA_FETCHED",
            workflow_id=workflow_id,
            step_name=f"fetch_{source}",
            input_summary=str(params)[:80],
            output_summary=f"keys={list(result.keys())}",
            confidence=1.0 if result else 0.3,
        )
        return result

    async def _fetch_employee(self, params: Dict) -> Dict:
        return {
            "employee_id": params.get("employee_id", "EMP001"),
            "name": params.get("name", "New Employee"),
            "department": params.get("department", "Engineering"),
            "manager": params.get("manager", "manager@company.com"),
            "start_date": params.get("start_date", "2026-04-01"),
            "role": params.get("role", "Software Engineer"),
        }

    async def _fetch_vendor(self, params: Dict) -> Dict:
        return {
            "vendor_id": params.get("vendor_id", "V001"),
            "vendor_name": params.get("vendor_name", "ACME Corp"),
            "contract_value": params.get("amount", 100000),
            "sla_days": 30,
            "payment_terms": "Net 30",
            "contact_email": "vendor@acme.com",
        }

    async def _fetch_contract(self, params: Dict) -> Dict:
        return {
            "contract_id": params.get("contract_id", "C001"),
            "parties": ["Company A", "Company B"],
            "value": params.get("value", 500000),
            "duration_months": 12,
            "review_required": True,
            "legal_team": "legal@company.com",
        }

    async def _fetch_approval_rules(self, params: Dict) -> Dict:
        return {
            "threshold_auto_approve": 50000,
            "threshold_manager_approve": 200000,
            "threshold_director_approve": 1000000,
            "approvers": {
                "manager": "manager@company.com",
                "director": "director@company.com",
                "cfo": "cfo@company.com",
            },
        }

    async def _fetch_calendar(self, params: Dict) -> Dict:
        return {
            "available_slots": ["2026-04-02T10:00", "2026-04-02T14:00"],
            "blocked": [],
        }

