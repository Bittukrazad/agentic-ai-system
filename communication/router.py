"""
Communication Router Module - Agent discovery and message routing.

Provides:
- Agent registry
- Async message dispatch
- Request/response correlation
"""

from typing import Dict, Any, Callable, Optional, Awaitable
import asyncio
from utils.logger import get_logger
from core.message_schema import AgentMessage, MessageStatus

logger = get_logger(__name__)


class AgentRegistry:
    """Registry of available agents and their capabilities."""
    
    def __init__(self):
        """Initialize agent registry."""
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.handlers: Dict[str, Callable] = {}
    
    def register_agent(
        self,
        agent_name: str,
        capabilities: list,
        handler: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register agent in system.
        
        Args:
            agent_name: Agent identifier
            capabilities: List of actions agent can perform
            handler: Async function to handle messages
            metadata: Additional metadata
        """
        self.agents[agent_name] = {
            "name": agent_name,
            "capabilities": capabilities,
            "metadata": metadata or {},
            "registered_at": __import__("utils.helpers", fromlist=["get_iso_now"]).get_iso_now(),
            "status": "active"
        }
        self.handlers[agent_name] = handler
        
        logger.info(
            f"Agent registered",
            extra={"agent_name": agent_name, "capabilities": capabilities}
        )
    
    def deregister_agent(self, agent_name: str) -> bool:
        """Deregister agent."""
        if agent_name in self.agents:
            del self.agents[agent_name]
            if agent_name in self.handlers:
                del self.handlers[agent_name]
            return True
        return False
    
    def get_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get agent information."""
        return self.agents.get(agent_name)
    
    def list_agents(self) -> list:
        """List all registered agents."""
        return list(self.agents.values())
    
    def has_agent(self, agent_name: str) -> bool:
        """Check if agent is registered."""
        return agent_name in self.agents
    
    def get_handler(self, agent_name: str) -> Optional[Callable]:
        """Get message handler for agent."""
        return self.handlers.get(agent_name)


class CommunicationRouter:
    """
    Routes messages between agents asynchronously.
    
    Handles:
    - Message dispatch to target agents
    - Response correlation
    - Timeout handling
    - Error propagation
    """
    
    def __init__(self):
        """Initialize communication router."""
        self.registry = AgentRegistry()
        self.pending_requests: Dict[str, asyncio.Future] = {}
    
    def register_agent(
        self,
        agent_name: str,
        capabilities: list,
        handler: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register agent with router."""
        self.registry.register_agent(agent_name, capabilities, handler, metadata)
    
    async def dispatch_message(
        self,
        message: AgentMessage,
        timeout_seconds: int = 60
    ) -> AgentMessage:
        """
        Dispatch message to target agent asynchronously.
        
        Args:
            message: Message to dispatch
            timeout_seconds: Response timeout
            
        Returns:
            Response message from agent
        """
        to_agent = message.to_agent
        
        # Verify agent exists
        if not self.registry.has_agent(to_agent):
            response = message
            response.mark_failed(f"Agent {to_agent} not found")
            return response
        
        try:
            # Mark as processing
            message.mark_processing()
            
            # Get handler
            handler = self.registry.get_handler(to_agent)
            if not handler:
                response = message
                response.mark_failed(f"No handler for {to_agent}")
                return response
            
            # Dispatch with timeout
            try:
                response = await asyncio.wait_for(
                    handler(message),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                response = message
                response.mark_failed(f"Agent response timeout after {timeout_seconds}s")
            
            logger.info(
                f"Message dispatched",
                extra={
                    "message_id": message.message_id,
                    "from_agent": message.from_agent,
                    "to_agent": to_agent
                }
            )
            
            return response
        
        except Exception as e:
            logger.error(
                f"Message dispatch error",
                extra={
                    "message_id": message.message_id,
                    "to_agent": to_agent,
                    "error": str(e)
                }
            )
            
            response = message
            response.mark_failed(str(e))
            return response
    
    async def dispatch_broadcast(
        self,
        message: AgentMessage,
        target_agents: list,
        timeout_seconds: int = 60
    ) -> Dict[str, AgentMessage]:
        """
        Broadcast message to multiple agents.
        
        Args:
            message: Message to broadcast
            target_agents: List of agent names
            timeout_seconds: Response timeout per agent
            
        Returns:
            Dictionary of responses by agent name
        """
        tasks = []
        agent_names = []
        
        for agent_name in target_agents:
            if self.registry.has_agent(agent_name):
                # Clone message for each agent
                agent_message = AgentMessage(
                    workflow_id=message.workflow_id,
                    step_id=message.step_id,
                    from_agent=message.from_agent,
                    to_agent=agent_name,
                    action=message.action,
                    payload=message.payload,
                    parent_message_id=message.message_id
                )
                
                tasks.append(self.dispatch_message(agent_message, timeout_seconds))
                agent_names.append(agent_name)
        
        # Wait for all responses
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        result = {}
        for agent_name, response in zip(agent_names, responses):
            if isinstance(response, Exception):
                error_msg = AgentMessage(
                    workflow_id=message.workflow_id,
                    step_id=message.step_id,
                    from_agent=agent_name,
                    to_agent=message.from_agent,
                    action=message.action,
                    status=MessageStatus.FAILED
                )
                error_msg.mark_failed(str(response))
                result[agent_name] = error_msg
            else:
                result[agent_name] = response
        
        logger.info(
            f"Broadcast complete",
            extra={
                "message_id": message.message_id,
                "target_count": len(target_agents),
                "success_count": sum(1 for r in result.values() if r.status == MessageStatus.SUCCESS)
            }
        )
        
        return result
    
    def get_registry(self) -> AgentRegistry:
        """Get agent registry."""
        return self.registry


# Global router instance
_router: Optional[CommunicationRouter] = None


def get_router() -> CommunicationRouter:
    """Get or create global communication router."""
    global _router
    if _router is None:
        _router = CommunicationRouter()
    return _router
