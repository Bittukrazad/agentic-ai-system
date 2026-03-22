"""
Data Agent Module - Responsible for fetching and retrieving data from various sources.

This agent handles:
- Database queries
- API calls
- Calendar data retrieval
- Email data fetching
- Data validation and caching
- Error handling for data sources
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
import asyncio
from base_agent import BaseAgent, Message, AgentStatus


class DataAgent(BaseAgent):
    """
    Data Agent for autonomous data retrieval and management.
    
    Capabilities:
    - Query databases for workflow data
    - Fetch from external APIs
    - Retrieve calendar events
    - Fetch email information
    - Cache frequently accessed data
    - Validate data integrity
    """
    
    def __init__(self, agent_name: str = "data_agent", max_retries: int = 3):
        """
        Initialize Data Agent.
        
        Args:
            agent_name: Agent identifier
            max_retries: Maximum retry attempts
        """
        super().__init__(agent_name, max_retries)
        self.data_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update = {}
    
    def process_message(self, message: Message) -> Message:
        """
        Process incoming data request message.
        
        Supported actions:
        - fetch_user_data: Get user information
        - fetch_workflow_data: Get workflow details
        - fetch_calendar_events: Get calendar data
        - fetch_emails: Get email information
        - query_database: Execute database query
        - fetch_from_api: Call external API
        
        Args:
            message: Incoming message with data request
            
        Returns:
            Message: Response with fetched data
        """
        action = message.action
        payload = message.payload
        
        try:
            if action == "fetch_user_data":
                data = self._fetch_user_data(payload)
            
            elif action == "fetch_workflow_data":
                data = self._fetch_workflow_data(payload)
            
            elif action == "fetch_calendar_events":
                data = self._fetch_calendar_events(payload)
            
            elif action == "fetch_emails":
                data = self._fetch_emails(payload)
            
            elif action == "query_database":
                data = self._query_database(payload)
            
            elif action == "fetch_from_api":
                data = self._fetch_from_api(payload)
            
            elif action == "cache_data":
                self._cache_data(payload)
                data = {"cached": True, "keys": list(payload.keys())}
            
            elif action == "get_cached_data":
                data = self._get_cached_data(payload)
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            response = Message(
                workflow_id=message.workflow_id,
                step_id=message.step_id,
                from_agent=self.agent_name,
                to_agent=message.from_agent,
                action=f"{action}_response",
                payload={"data": data, "source": action},
                status=AgentStatus.SUCCESS.value
            )
            
            self.update_state(f"last_{action}_success", datetime.utcnow().isoformat())
            return response
        
        except Exception as e:
            raise Exception(f"Data retrieval error: {str(e)}")
    
    def _fetch_user_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch user information from database.
        
        Args:
            payload: Request payload with user_id
            
        Returns:
            User data dictionary
        """
        user_id = payload.get("user_id")
        
        # Check cache first
        cache_key = f"user_{user_id}"
        cached = self._get_cached_data({"key": cache_key})
        if cached:
            return cached
        
        # Simulated database fetch
        user_data = {
            "user_id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
            "department": "Engineering",
            "manager_id": "mgr_001",
            "role": "Engineer"
        }
        
        # Cache the result
        self._cache_data({cache_key: user_data})
        return user_data
    
    def _fetch_workflow_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch workflow information.
        
        Args:
            payload: Request payload with workflow_id
            
        Returns:
            Workflow data dictionary
        """
        workflow_id = payload.get("workflow_id")
        
        # Check cache first
        cache_key = f"workflow_{workflow_id}"
        cached = self._get_cached_data({"key": cache_key})
        if cached:
            return cached
        
        # Simulated workflow fetch
        workflow_data = {
            "workflow_id": workflow_id,
            "name": "Employee Onboarding",
            "status": "in_progress",
            "created_at": datetime.utcnow().isoformat(),
            "due_date": "2026-04-15",
            "owner": "hr_team",
            "steps": [
                {
                    "step_id": "step_1",
                    "name": "Initial Setup",
                    "status": "completed",
                    "assigned_to": "onboarding_agent"
                },
                {
                    "step_id": "step_2",
                    "name": "Document Collection",
                    "status": "in_progress",
                    "assigned_to": "data_agent"
                }
            ]
        }
        
        # Cache the result
        self._cache_data({cache_key: workflow_data})
        return workflow_data
    
    def _fetch_calendar_events(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch calendar events for a user.
        
        Args:
            payload: Request with user_id and date_range
            
        Returns:
            List of calendar events
        """
        user_id = payload.get("user_id")
        date_range = payload.get("date_range", {"start": "2026-03-22", "end": "2026-03-29"})
        
        # Simulated calendar events
        events = [
            {
                "event_id": "evt_001",
                "title": "Team Standup",
                "start": "2026-03-22T09:00:00",
                "end": "2026-03-22T09:30:00",
                "attendees": [user_id, "user_002", "user_003"],
                "location": "Conference Room A"
            },
            {
                "event_id": "evt_002",
                "title": "Project Planning",
                "start": "2026-03-24T14:00:00",
                "end": "2026-03-24T15:30:00",
                "attendees": [user_id, "user_004"],
                "location": "Virtual"
            }
        ]
        
        return events
    
    def _fetch_emails(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch email information.
        
        Args:
            payload: Request with user_id and filters
            
        Returns:
            List of email messages
        """
        user_id = payload.get("user_id")
        limit = payload.get("limit", 10)
        
        # Simulated emails
        emails = [
            {
                "email_id": "email_001",
                "from": "manager@example.com",
                "to": f"user{user_id}@example.com",
                "subject": "Onboarding Checklist",
                "received_at": "2026-03-22T08:30:00",
                "body": "Please complete the following tasks...",
                "priority": "high"
            },
            {
                "email_id": "email_002",
                "from": "hr@example.com",
                "to": f"user{user_id}@example.com",
                "subject": "Welcome to the Team",
                "received_at": "2026-03-21T10:00:00",
                "body": "Welcome aboard! We're excited to have you.",
                "priority": "normal"
            }
        ]
        
        return emails[:limit]
    
    def _query_database(self, payload: Dict[str, Any]) -> Any:
        """
        Execute a database query.
        
        Args:
            payload: Query specification
            
        Returns:
            Query result
        """
        query_type = payload.get("query_type")
        filters = payload.get("filters", {})
        
        # Simulated database query for different entity types
        if query_type == "procurement_orders":
            return self._query_procurement_orders(filters)
        elif query_type == "contracts":
            return self._query_contracts(filters)
        elif query_type == "employee_records":
            return self._query_employee_records(filters)
        else:
            raise ValueError(f"Unknown query type: {query_type}")
    
    def _query_procurement_orders(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query procurement orders from database."""
        return [
            {
                "order_id": "PO_001",
                "vendor": "Tech Supplies Inc",
                "amount": 5000.00,
                "status": "pending_approval",
                "created_at": "2026-03-20"
            }
        ]
    
    def _query_contracts(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query contracts from database."""
        return [
            {
                "contract_id": "CTR_001",
                "vendor": "Service Provider LLC",
                "value": 100000.00,
                "start_date": "2026-04-01",
                "end_date": "2027-03-31",
                "status": "draft"
            }
        ]
    
    def _query_employee_records(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query employee records from database."""
        return [
            {
                "employee_id": "EMP_001",
                "name": "John Doe",
                "department": "Engineering",
                "start_date": "2026-03-15",
                "status": "active"
            }
        ]
    
    def _fetch_from_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch data from external API.
        
        Args:
            payload: API request specification
            
        Returns:
            API response data
        """
        endpoint = payload.get("endpoint")
        method = payload.get("method", "GET")
        params = payload.get("params", {})
        
        # Simulated API call - in production would use requests library
        api_response = {
            "endpoint": endpoint,
            "method": method,
            "status_code": 200,
            "data": params,
            "fetched_at": datetime.utcnow().isoformat()
        }
        
        return api_response
    
    def _cache_data(self, data: Dict[str, Any]) -> None:
        """
        Cache data for quick retrieval.
        
        Args:
            data: Dictionary of key-value pairs to cache
        """
        for key, value in data.items():
            self.data_cache[key] = {
                "value": value,
                "cached_at": datetime.utcnow().isoformat(),
                "ttl": self.cache_ttl
            }
            self.last_cache_update[key] = datetime.utcnow().timestamp()
    
    def _get_cached_data(self, payload: Dict[str, Any]) -> Optional[Any]:
        """
        Retrieve cached data if still valid.
        
        Args:
            payload: Request with cache key
            
        Returns:
            Cached data or None if expired
        """
        key = payload.get("key")
        
        if key not in self.data_cache:
            return None
        
        cache_entry = self.data_cache[key]
        last_update = self.last_cache_update.get(key, 0)
        age = datetime.utcnow().timestamp() - last_update
        
        if age > cache_entry["ttl"]:
            # Cache expired
            del self.data_cache[key]
            del self.last_cache_update[key]
            return None
        
        return cache_entry["value"]
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.data_cache = {}
        self.last_cache_update = {}
