"""
API Routes - FastAPI routes for workflow, audit, and agent management.

Provides:
- POST /workflow/trigger - Start workflow
- GET /workflow/{workflow_id} - Get workflow status
- GET /workflow/{workflow_id}/state - Get detailed state
- GET /audit/logs - Query audit logs
- GET /audit/trace/{workflow_id} - Get workflow trace
- POST /agent/health - Agent health check
- GET /agents - List registered agents
"""

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from pathlib import Path

from app.config import Settings
from app.main import app_state
from utils.logger import get_logger
from audit.audit_logger import AuditLogger
from utils.helpers import load_json_file, load_jsonl_file

logger = get_logger(__name__)
config = Settings()


# Request/Response models
class WorkflowTriggerRequest(BaseModel):
    """Workflow trigger request."""
    workflow_name: str
    input_data: Dict[str, Any] = {}
    priority: str = "medium"
    metadata: Dict[str, Any] = {}


class WorkflowResponse(BaseModel):
    """Workflow execution response."""
    success: bool
    workflow_id: str
    workflow_name: str
    status: str
    message: str = ""


class WorkflowStateResponse(BaseModel):
    """Workflow state response."""
    workflow_id: str
    workflow_name: str
    status: str
    started_at: str
    current_step: Optional[str]
    completed_steps: int
    total_steps: int
    progress_percentage: float
    sla_status: str
    steps_detail: List[Dict[str, Any]] = []


class AuditLogQuery(BaseModel):
    """Audit log query."""
    workflow_id: Optional[str] = None
    agent_name: Optional[str] = None
    action_type: Optional[str] = None
    limit: int = 100


class AgentHealthRequest(BaseModel):
    """Agent health check request."""
    agent_name: str
    status: str = "healthy"
    metrics: Dict[str, Any] = {}


# Routers
workflow_router = APIRouter(prefix="/workflow", tags=["workflow"])
audit_router = APIRouter(prefix="/audit", tags=["audit"])
agent_router = APIRouter(prefix="/agent", tags=["agent"])


# Workflow Routes
@workflow_router.post("/trigger", response_model=WorkflowResponse)
async def trigger_workflow(
    request: WorkflowTriggerRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Trigger workflow execution.
    
    Args:
        request: Workflow trigger request
        background_tasks: FastAPI background tasks
        
    Returns:
        WorkflowResponse
    """
    try:
        if not app_state.is_running:
            raise HTTPException(
                status_code=503,
                detail="Orchestrator not initialized"
            )
        
        if app_state.orchestrator is None:
            raise HTTPException(
                status_code=500,
                detail="Orchestrator failed to initialize"
            )
        
        logger.info(
            f"Workflow trigger requested",
            extra={
                "workflow_name": request.workflow_name,
                "priority": request.priority
            }
        )
        
        # Load workflow
        workflow = app_state.orchestrator.load_workflow(request.workflow_name)
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{request.workflow_name}' not found"
            )
        
        # Initialize workflow
        root_trace_id = app_state.orchestrator.initialize_workflow(
            request.workflow_name,
            request.input_data
        )
        if not root_trace_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize workflow"
            )
        
        # Generate workflow ID (using trace ID as unique identifier)
        workflow_id = f"{request.workflow_name}_{root_trace_id}"
        
        # Execute asynchronously
        background_tasks.add_task(
            app_state.orchestrator.execute_workflow,
            request.workflow_name,
            request.input_data
        )
        
        logger.info(
            f"Workflow execution started",
            extra={"workflow_id": workflow_id, "workflow_name": request.workflow_name}
        )
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "workflow_name": request.workflow_name,
            "status": "executing",
            "message": f"Workflow '{request.workflow_name}' started"
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Workflow trigger error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    Get workflow execution status.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Workflow status
    """
    try:
        if not app_state.is_running or app_state.orchestrator is None:
            raise HTTPException(
                status_code=503,
                detail="Orchestrator not initialized"
            )
        
        state = app_state.orchestrator.state_manager.get_workflow_state(workflow_id)
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{workflow_id}' not found"
            )
        
        return {
            "workflow_id": workflow_id,
            "status": state.get("status"),
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
            "metadata": state.get("metadata", {})
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Get status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.get("/{workflow_id}/state")
async def get_workflow_state(workflow_id: str) -> Dict[str, Any]:
    """
    Get detailed workflow execution state.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Detailed workflow state
    """
    try:
        if not app_state.is_running or app_state.orchestrator is None:
            raise HTTPException(
                status_code=503,
                detail="Orchestrator not initialized"
            )
        
        state = app_state.orchestrator.state_manager.get_workflow_state(workflow_id)
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{workflow_id}' not found"
            )
        
        # Calculate progress
        steps = state.get("steps", {})
        completed = len([s for s in steps.values() if s.get("status") == "completed"])
        total = len(steps)
        
        return {
            "workflow_id": workflow_id,
            "workflow_name": state.get("workflow_name"),
            "status": state.get("status"),
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
            "current_step": state.get("current_step"),
            "completed_steps": completed,
            "total_steps": total,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "steps_detail": [
                {
                    "step_id": step_id,
                    "status": step.get("status"),
                    "started_at": step.get("started_at"),
                    "completed_at": step.get("completed_at"),
                    "retry_count": step.get("retry_count", 0)
                }
                for step_id, step in steps.items()
            ]
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Get state error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.get("")
async def list_workflows(
    status: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    List all workflows.
    
    Args:
        status: Optional filter by status
        
    Returns:
        List of workflows
    """
    try:
        # Load all workflow files
        workflows_dir = Path(config.full_workflows_dir)
        workflows = []
        
        for wf_file in workflows_dir.glob("*.json"):
            try:
                wf_data = load_json_file(str(wf_file))
                workflows.append({
                    "name": wf_data.get("name"),
                    "description": wf_data.get("description", ""),
                    "steps": len(wf_data.get("steps", []))
                })
            except Exception as e:
                logger.warning(f"Failed to load {wf_file}: {str(e)}")
        
        return {
            "success": True,
            "total_workflows": len(workflows),
            "workflows": workflows
        }
    
    except Exception as e:
        logger.error(f"List workflows error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Audit Routes
@audit_router.get("/logs")
async def get_audit_logs(
    workflow_id: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
) -> Dict[str, Any]:
    """
    Query audit logs.
    
    Args:
        workflow_id: Optional filter by workflow
        agent_name: Optional filter by agent
        action_type: Optional filter by action type
        limit: Max results
        
    Returns:
        Audit logs
    """
    try:
        trace_logs = load_jsonl_file(str(config.full_trace_log_file))
        
        # Filter logs
        filtered = trace_logs
        
        if workflow_id:
            filtered = [l for l in filtered if l.get("workflow_id") == workflow_id]
        
        if agent_name:
            filtered = [l for l in filtered if l.get("from_agent") == agent_name]
        
        if action_type:
            filtered = [l for l in filtered if l.get("log_type") == action_type]
        
        # Limit results
        filtered = filtered[-limit:]
        
        return {
            "success": True,
            "total_logs": len(trace_logs),
            "filtered_count": len(filtered),
            "logs": filtered
        }
    
    except Exception as e:
        logger.error(f"Get audit logs error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@audit_router.get("/trace/{workflow_id}")
async def get_workflow_trace(workflow_id: str) -> Dict[str, Any]:
    """
    Get complete trace for workflow.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Workflow execution trace
    """
    try:
        project_root = Path(config.PROJECT_ROOT)
        trace_log_file = str(project_root / config.TRACE_LOG_FILE)
        decision_log_file = str(project_root / config.DECISION_LOG_FILE)
        audit_logger = AuditLogger(trace_log_file, decision_log_file)
        trace = audit_logger.get_trace_for_workflow(workflow_id)
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "trace_count": len(trace),
            "trace": trace
        }
    
    except Exception as e:
        logger.error(f"Get trace error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@audit_router.get("/decisions/{workflow_id}")
async def get_workflow_decisions(workflow_id: str) -> Dict[str, Any]:
    """
    Get all decisions made for workflow.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Decision logs
    """
    try:
        project_root = Path(config.PROJECT_ROOT)
        trace_log_file = str(project_root / config.TRACE_LOG_FILE)
        decision_log_file = str(project_root / config.DECISION_LOG_FILE)
        audit_logger = AuditLogger(trace_log_file, decision_log_file)
        decisions = audit_logger.get_decisions_for_workflow(workflow_id)
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "decision_count": len(decisions),
            "decisions": decisions
        }
    
    except Exception as e:
        logger.error(f"Get decisions error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent Routes
@agent_router.post("/health")
async def agent_health_check(request: AgentHealthRequest) -> Dict[str, Any]:
    """
    Record agent health check.
    
    Args:
        request: Agent health info
        
    Returns:
        Health check response
    """
    try:
        logger.info(
            f"Agent health check received",
            extra={
                "agent_name": request.agent_name,
                "status": request.status,
                "metrics": request.metrics
            }
        )
        
        return {
            "success": True,
            "agent_name": request.agent_name,
            "acknowledged": True,
            "timestamp": None  # Will be set by JSON encoder
        }
    
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@agent_router.get("")
async def list_agents() -> Dict[str, Any]:
    """
    List registered agents.
    
    Returns:
        List of agents
    """
    try:
        # Get agent registry from communication router
        from communication.router import get_router
        
        router = get_router()
        agents = router.registry.list_agents()
        
        return {
            "success": True,
            "total_agents": len(agents),
            "agents": agents
        }
    
    except Exception as e:
        logger.error(f"List agents error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@agent_router.get("/{agent_name}")
async def get_agent_info(agent_name: str) -> Dict[str, Any]:
    """
    Get agent information.
    
    Args:
        agent_name: Agent name
        
    Returns:
        Agent info
    """
    try:
        from communication.router import get_router
        
        router = get_router()
        agent = router.registry.get_agent(agent_name)
        
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' not found"
            )
        
        return {
            "success": True,
            "agent_name": agent_name,
            "registered": True,
            "has_handler": router.registry.has_agent(agent_name)
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Get agent info error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
