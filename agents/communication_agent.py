"""
Communication Agent Module - Responsible for inter-agent communication and coordination.

This agent handles:
- Message routing between agents
- Event publishing
- Message queue management
- Agent discovery
- Communication logs
- Broadcast messaging
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
from collections import defaultdict
from base_agent import BaseAgent, Message, AgentStatus


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class CommunicationAgent(BaseAgent):
    """
    Communication Agent for inter-agent coordination and messaging.
    
    Capabilities:
    - Route messages between agents
    - Manage message queues
    - Publish events
    - Subscribe to events
    - Coordinate agent workflows
    - Maintain communication logs
    """
    
    def __init__(self, agent_name: str = "communication_agent", max_retries: int = 3):
        """
        Initialize Communication Agent.
        
        Args:
            agent_name: Agent identifier
            max_retries: Maximum retry attempts
        """
        super().__init__(agent_name, max_retries)
        self.message_queues = defaultdict(list)
        self.subscriptions = defaultdict(list)
        self.agent_registry = {}
        self.communication_log = []
        self.event_history = []
    
    def process_message(self, message: Message) -> Message:
        """
        Process incoming communication request message.
        
        Supported actions:
        - route_message: Route message to target agent
        - queue_message: Queue message for processing
        - broadcast_message: Broadcast message to multiple agents
        - subscribe_event: Subscribe to event
        - publish_event: Publish event
        - get_queue_status: Get message queue status
        - register_agent: Register agent endpoint
        
        Args:
            message: Incoming message with communication request
            
        Returns:
            Message: Response with communication result
        """
        action = message.action
        payload = message.payload
        
        try:
            if action == "route_message":
                result = self._route_message(payload)
            
            elif action == "queue_message":
                result = self._queue_message(payload)
            
            elif action == "broadcast_message":
                result = self._broadcast_message(payload)
            
            elif action == "subscribe_event":
                result = self._subscribe_event(payload)
            
            elif action == "publish_event":
                result = self._publish_event(payload)
            
            elif action == "get_queue_status":
                result = self._get_queue_status(payload)
            
            elif action == "register_agent":
                result = self._register_agent(payload)
            
            elif action == "deregister_agent":
                result = self._deregister_agent(payload)
            
            elif action == "get_agent_status":
                result = self._get_agent_status(payload)
            
            elif action == "get_communication_log":
                result = self._get_communication_log(payload)
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            response = Message(
                workflow_id=message.workflow_id,
                step_id=message.step_id,
                from_agent=self.agent_name,
                to_agent=message.from_agent,
                action=f"{action}_response",
                payload=result,
                status=AgentStatus.SUCCESS.value
            )
            
            return response
        
        except Exception as e:
            raise Exception(f"Communication error: {str(e)}")
    
    def _route_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route message to target agent.
        
        Args:
            payload: Message to route
            
        Returns:
            Routing confirmation
        """
        target_agent = payload.get("target_agent")
        message_data = payload.get("message")
        priority = payload.get("priority", MessagePriority.NORMAL.value)
        
        if not target_agent:
            raise ValueError("target_agent required")
        
        # Check if agent is registered
        if target_agent not in self.agent_registry:
            return {
                "status": "failed",
                "reason": f"Agent {target_agent} not registered",
                "routed_at": datetime.utcnow().isoformat()
            }
        
        # Route the message
        route_entry = {
            "message_id": (message_data or {}).get("message_id"),
            "from_agent": (message_data or {}).get("from_agent"),
            "to_agent": target_agent,
            "action": (message_data or {}).get("action"),
            "priority": priority,
            "status": "routed",
            "routed_at": datetime.utcnow().isoformat()
        }
        
        self._log_communication(route_entry)
        
        return {
            "status": "success",
            "target_agent": target_agent,
            "message_id": (message_data or {}).get("message_id"),
            "priority": priority,
            "routed_at": datetime.utcnow().isoformat()
        }
    
    def _queue_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queue message for asynchronous processing.
        
        Args:
            payload: Message to queue
            
        Returns:
            Queuing confirmation
        """
        target_agent = payload.get("target_agent")
        message_data = payload.get("message")
        priority = payload.get("priority", MessagePriority.NORMAL.value)
        
        queue_entry = {
            "message_id": (message_data or {}).get("message_id"),
            "message": message_data,
            "priority": priority,
            "queued_at": datetime.utcnow().isoformat(),
            "status": "queued"
        }
        
        # Add to appropriate queue
        self.message_queues[target_agent].append(queue_entry)
        
        # Sort by priority (higher priority first)
        priority_map = {"low": 1, "normal": 2, "high": 3, "critical": 4}
        self.message_queues[target_agent].sort(
            key=lambda x: priority_map.get(x["priority"], 2),
            reverse=True
        )
        
        return {
            "status": "queued",
            "target_agent": target_agent,
            "message_id": (message_data or {}).get("message_id"),
            "queue_depth": len(self.message_queues[target_agent]),
            "queued_at": datetime.utcnow().isoformat()
        }
    
    def _broadcast_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Broadcast message to multiple agents.
        
        Args:
            payload: Message and target agents
            
        Returns:
            Broadcast confirmation
        """
        target_agents = payload.get("target_agents", [])
        message_data = payload.get("message")
        exclude_agent = payload.get("exclude_agent")
        
        success_count = 0
        failed_count = 0
        failed_agents = []
        
        for agent in target_agents:
            if exclude_agent and agent == exclude_agent:
                continue
            
            if agent in self.agent_registry:
                success_count += 1
            else:
                failed_count += 1
                failed_agents.append(agent)
        
        broadcast_entry = {
            "message_id": (message_data or {}).get("message_id"),
            "broadcast_to": target_agents,
            "successful_routes": success_count,
            "failed_routes": failed_count,
            "failed_agents": failed_agents,
            "broadcast_at": datetime.utcnow().isoformat()
        }
        
        self._log_communication(broadcast_entry)
        
        return {
            "status": "broadcast_complete",
            "total_agents": len(target_agents),
            "successful_routes": success_count,
            "failed_routes": failed_count,
            "failed_agents": failed_agents,
            "broadcast_at": datetime.utcnow().isoformat()
        }
    
    def _subscribe_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Subscribe agent to event type.
        
        Args:
            payload: Agent and event type
            
        Returns:
            Subscription confirmation
        """
        agent_name = payload.get("agent_name")
        event_type = payload.get("event_type")
        callback = payload.get("callback")
        
        if not agent_name or not event_type:
            raise ValueError("agent_name and event_type required")
        
        subscription = {
            "agent_name": agent_name,
            "event_type": event_type,
            "callback": callback,
            "subscribed_at": datetime.utcnow().isoformat()
        }
        
        self.subscriptions[event_type].append(subscription)
        
        return {
            "status": "subscribed",
            "agent_name": agent_name,
            "event_type": event_type,
            "subscribers_for_event": len(self.subscriptions[event_type]),
            "subscribed_at": datetime.utcnow().isoformat()
        }
    
    def _publish_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish event to all subscribers.
        
        Args:
            payload: Event data
            
        Returns:
            Publication confirmation
        """
        event_type = payload.get("event_type")
        event_data = payload.get("data", {})
        source_agent = payload.get("source_agent")
        
        subscribers = self.subscriptions.get(event_type, [])
        notified_count = 0
        
        event_entry = {
            "event_type": event_type,
            "source_agent": source_agent,
            "data_keys": list(event_data.keys()),
            "subscribers_notified": len(subscribers),
            "published_at": datetime.utcnow().isoformat()
        }
        
        self.event_history.append(event_entry)
        self._log_communication(event_entry)
        
        # In a real implementation, would notify subscribers asynchronously
        notified_count = len(subscribers)
        
        return {
            "status": "published",
            "event_type": event_type,
            "source_agent": source_agent,
            "subscribers_notified": notified_count,
            "published_at": datetime.utcnow().isoformat()
        }
    
    def _get_queue_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get status of message queues.
        
        Args:
            payload: Optional filter by agent
            
        Returns:
            Queue status
        """
        agent_name = payload.get("agent_name")
        
        queue_status = {}
        total_queued = 0
        
        if agent_name:
            if agent_name in self.message_queues:
                queue_status[agent_name] = {
                    "depth": len(self.message_queues[agent_name]),
                    "messages": self.message_queues[agent_name][-10:]
                }
                total_queued = len(self.message_queues[agent_name])
        else:
            for agent, queue in self.message_queues.items():
                queue_status[agent] = {
                    "depth": len(queue),
                    "oldest_message_age_seconds": self._get_queue_age(queue)
                }
                total_queued += len(queue)
        
        return {
            "total_queued_messages": total_queued,
            "queue_status": queue_status,
            "checked_at": datetime.utcnow().isoformat()
        }
    
    def _register_agent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register agent endpoint.
        
        Args:
            payload: Agent registration details
            
        Returns:
            Registration confirmation
        """
        agent_name = payload.get("agent_name")
        endpoint = payload.get("endpoint")
        capabilities = payload.get("capabilities", [])
        
        if not agent_name:
            raise ValueError("agent_name required")
        
        self.agent_registry[agent_name] = {
            "endpoint": endpoint,
            "capabilities": capabilities,
            "registered_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        return {
            "status": "registered",
            "agent_name": agent_name,
            "endpoint": endpoint,
            "total_agents_registered": len(self.agent_registry),
            "registered_at": datetime.utcnow().isoformat()
        }
    
    def _deregister_agent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deregister agent endpoint.
        
        Args:
            payload: Agent to deregister
            
        Returns:
            Deregistration confirmation
        """
        agent_name = payload.get("agent_name")
        
        if agent_name in self.agent_registry:
            del self.agent_registry[agent_name]
            
            # Clean up queues
            if agent_name in self.message_queues:
                del self.message_queues[agent_name]
        
        return {
            "status": "deregistered",
            "agent_name": agent_name,
            "total_agents_registered": len(self.agent_registry),
            "deregistered_at": datetime.utcnow().isoformat()
        }
    
    def _get_agent_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get status of registered agents.
        
        Args:
            payload: Optional filter
            
        Returns:
            Agent status
        """
        agent_name = payload.get("agent_name")
        
        if agent_name:
            if agent_name in self.agent_registry:
                agent_info = self.agent_registry[agent_name]
                queue_depth = len(self.message_queues.get(agent_name, []))
                
                return {
                    "agent_name": agent_name,
                    "status": agent_info.get("status"),
                    "endpoint": agent_info.get("endpoint"),
                    "capabilities": agent_info.get("capabilities"),
                    "queue_depth": queue_depth,
                    "registered_at": agent_info.get("registered_at"),
                    "checked_at": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "agent_name": agent_name,
                    "status": "not_registered",
                    "checked_at": datetime.utcnow().isoformat()
                }
        else:
            agents_list = []
            for agent_name, info in self.agent_registry.items():
                agents_list.append({
                    "agent_name": agent_name,
                    "status": info.get("status"),
                    "capabilities": info.get("capabilities"),
                    "queue_depth": len(self.message_queues.get(agent_name, []))
                })
            
            return {
                "total_agents": len(self.agent_registry),
                "agents": agents_list,
                "checked_at": datetime.utcnow().isoformat()
            }
    
    def _get_communication_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get communication log.
        
        Args:
            payload: Filter options
            
        Returns:
            Communication log
        """
        limit = payload.get("limit", 20)
        agent_filter = payload.get("agent_name")
        
        filtered_log = self.communication_log
        
        if agent_filter:
            filtered_log = [
                log for log in filtered_log
                if agent_filter in [log.get("from_agent"), log.get("to_agent")]
            ]
        
        return {
            "total_communications": len(self.communication_log),
            "recent_communications": filtered_log[-limit:],
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    def _log_communication(self, communication_entry: Dict[str, Any]) -> None:
        """
        Log communication event.
        
        Args:
            communication_entry: Communication details
        """
        log_entry = {
            **communication_entry,
            "logged_at": datetime.utcnow().isoformat()
        }
        self.communication_log.append(log_entry)
    
    def _get_queue_age(self, queue: List[Dict[str, Any]]) -> Optional[float]:
        """Get age of oldest message in queue."""
        if not queue:
            return None
        
        oldest = queue[0]
        if "queued_at" in oldest:
            queued_time = datetime.fromisoformat(oldest["queued_at"])
            age = (datetime.utcnow() - queued_time).total_seconds()
            return round(age, 2)
        
        return None
    
    def dequeue_message(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve next message from queue (FIFO with priority).
        
        Args:
            agent_name: Agent name
            
        Returns:
            Next message or None
        """
        if agent_name not in self.message_queues:
            return None
        
        if len(self.message_queues[agent_name]) == 0:
            return None
        
        message = self.message_queues[agent_name].pop(0)
        message["dequeued_at"] = datetime.utcnow().isoformat()
        message["status"] = "dequeued"
        
        return message
    
    def clear_queue(self, agent_name: str) -> Dict[str, Any]:
        """
        Clear message queue for agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Confirmation
        """
        count = len(self.message_queues.get(agent_name, []))
        self.message_queues[agent_name] = []
        
        return {
            "agent_name": agent_name,
            "messages_cleared": count,
            "cleared_at": datetime.utcnow().isoformat()
        }
