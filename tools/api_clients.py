"""tools/api_clients.py — Generic HTTP client for external CRM, HRMS, ERP APIs"""
import json
import os
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class APIClients:
    """
    Generic async HTTP client for external integrations.
    In production, replace mock responses with real API calls using httpx.

    Supported integrations:
      - CRM (Salesforce)
      - HRMS (Workday, BambooHR)
      - ERP (SAP, Oracle)
      - Custom REST APIs
    """

    def __init__(self):
        self._client = None
        self._try_init_httpx()

    def _try_init_httpx(self):
        try:
            import httpx
            self._client = httpx.AsyncClient(timeout=30.0)
            logger.info("APIClients: httpx client initialised")
        except ImportError:
            logger.warning("httpx not installed — API calls will use mock responses")

    async def get(self, url: str, headers: Dict = None, params: Dict = None) -> Dict:
        """Make a GET request to an external API"""
        if self._client:
            try:
                response = await self._client.get(url, headers=headers or {}, params=params or {})
                return response.json()
            except Exception as e:
                logger.warning(f"API GET failed: {url} | {e}")
                return {"error": str(e)}
        logger.info(f"[API MOCK] GET {url} | params={params}")
        return {"mock": True, "url": url, "data": {}}

    async def post(self, url: str, payload: Dict, headers: Dict = None) -> Dict:
        """Make a POST request to an external API"""
        if self._client:
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", **(headers or {})},
                )
                return response.json()
            except Exception as e:
                logger.warning(f"API POST failed: {url} | {e}")
                return {"error": str(e)}
        logger.info(f"[API MOCK] POST {url} | payload_keys={list(payload.keys())}")
        return {"mock": True, "url": url, "status": "ok"}

    async def fetch_employee_by_id(self, employee_id: str) -> Dict:
        """Fetch employee from HRMS"""
        hrms_url = os.getenv("HRMS_API_URL", "")
        if hrms_url:
            return await self.get(f"{hrms_url}/employees/{employee_id}")
        return {
            "employee_id": employee_id,
            "name": "Demo Employee",
            "department": "Engineering",
            "manager_email": "manager@company.com",
            "mock": True,
        }

    async def fetch_vendor_by_id(self, vendor_id: str) -> Dict:
        """Fetch vendor from procurement system"""
        erp_url = os.getenv("ERP_API_URL", "")
        if erp_url:
            return await self.get(f"{erp_url}/vendors/{vendor_id}")
        return {
            "vendor_id": vendor_id,
            "name": "Demo Vendor",
            "contact": "vendor@demo.com",
            "sla_days": 30,
            "mock": True,
        }

    async def close(self):
        if self._client:
            await self._client.aclose()