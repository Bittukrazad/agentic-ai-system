"""app/main.py — FastAPI application entry point"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes import router
from app.config import config
from health_monitoring.drift_detector import DriftDetector
from health_monitoring.bottleneck_predictor import BottleneckPredictor
from communication.event_bus import EventBus
from memory.short_term_memory import ShortTermMemory
from llm.llm_client import LLMClient
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle"""
    logger.info("=== Agentic AI System starting up ===")
    ShortTermMemory.init()
    LLMClient.init()
    EventBus.init()
    DriftDetector.start_scheduler()
    BottleneckPredictor.start_scheduler()
    logger.info("All subsystems initialised. Ready.")
    yield
    logger.info("=== Agentic AI System shutting down ===")
    DriftDetector.stop_scheduler()
    BottleneckPredictor.stop_scheduler()
    EventBus.shutdown()


app = FastAPI(
    title="Agentic AI — Autonomous Enterprise Workflows",
    description="Multi-agent system for autonomous enterprise workflow execution with full audit trail",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Agentic AI — Autonomous Enterprise Workflows",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=config.APP_HOST, port=config.APP_PORT, reload=config.DEBUG)