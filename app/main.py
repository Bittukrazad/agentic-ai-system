"""
FastAPI Backend - Main application entry point.

Provides:
- FastAPI application setup
- Middleware configuration
- Exception handlers
- CORS support
- Health checks
- Logging integration
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from pathlib import Path

from app.config import Settings
from utils.logger import get_logger, setup_logging
from communication.event_bus import get_event_bus, EventType, Event
from orchestrator.orchestrator import Orchestrator

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Configuration
config = Settings()


class ApplicationState:
    """Global application state."""
    
    def __init__(self):
        """Initialize application state."""
        self.orchestrator: Optional[Orchestrator] = None
        self.is_running: bool = False
        self.start_time: Optional[str] = None


app_state = ApplicationState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting FastAPI application")
    
    try:
        # Initialize orchestrator with config paths
        project_root = Path(config.PROJECT_ROOT)
        workflows_dir = str(project_root / config.WORKFLOWS_DIR)
        state_file = str(project_root / config.STATE_STORE_FILE)
        trace_log_file = str(project_root / config.TRACE_LOG_FILE)
        decision_log_file = str(project_root / config.DECISION_LOG_FILE)
        max_retries = config.DEFAULT_STEP_RETRIES
        
        app_state.orchestrator = Orchestrator(
            workflows_dir=workflows_dir,
            state_file=state_file,
            trace_log_file=trace_log_file,
            decision_log_file=decision_log_file,
            max_retries=max_retries
        )
        app_state.is_running = True
        
        # Initialize event bus
        event_bus = get_event_bus()
        
        logger.info("Application started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down FastAPI application")
        app_state.is_running = False
        logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Agentic AI System",
    description="Production-grade multi-agent AI orchestration platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=config.allowed_hosts or ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle value errors."""
    logger.warning(f"Value error: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": "Invalid request",
            "detail": str(exc)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if config.is_development else None
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns:
        Health status
    """
    return {
        "status": "healthy" if app_state.is_running else "unhealthy",
        "service": "agentic-ai-system",
        "version": "1.0.0",
        "is_running": app_state.is_running
    }


@app.get("/info")
async def info() -> Dict[str, Any]:
    """
    Application info endpoint.
    
    Returns:
        Application information
    """
    return {
        "name": "Agentic AI System",
        "version": "1.0.0",
        "environment": "production" if config.is_production else "development",
        "debug": config.is_development,
        "workflows_dir": str(config.full_workflows_dir),
        "state_store": str(config.full_state_store_file),
        "audit_dir": str(config.full_audit_dir)
    }


# Import routes
from app import routes  # noqa: E402

# Include routers
app.include_router(routes.workflow_router)
app.include_router(routes.audit_router)
app.include_router(routes.agent_router)


if __name__ == "__main__":
    import uvicorn
    
    port = int(config.api_port or 8000)
    host = config.api_host or "0.0.0.0"
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info" if config.is_development else "warning",
        access_log=config.is_development
    )
