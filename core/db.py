"""core/db.py — Database connection, session management, and ORM models.

Provides:
  - get_engine()        — SQLAlchemy engine singleton
  - get_session()       — context-managed session
  - Base                — declarative base for all ORM models
  - AuditLog            — ORM model mirroring audit/decision_logs.json
  - WorkflowRecord      — persists completed workflow run metadata
  - TaskRecord          — persists meeting-intelligence tasks
  - create_all_tables() — idempotent table creation on startup
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agentic_ai.db")

# ---------------------------------------------------------------------------
# Engine & Session (SQLAlchemy optional)
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None
Base = None


def _try_init():
    global _engine, _SessionLocal, Base
    if _engine is not None:
        return True
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, declarative_base

        _engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
            echo=False,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
        Base = declarative_base()
        logger.info(f"DB engine ready: {DATABASE_URL}")
        return True
    except ImportError:
        logger.warning("SQLAlchemy not installed — ORM models unavailable, using in-memory fallback")
        return False
    except Exception as e:
        logger.warning(f"DB init failed: {e} — using in-memory fallback")
        return False


def get_engine():
    _try_init()
    return _engine


@contextmanager
def get_session():
    """Context-managed database session. Auto-commits on success, rolls back on error."""
    if not _try_init() or _SessionLocal is None:
        yield None
        return
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

def _define_models():
    """Define models only if SQLAlchemy is available."""
    if not _try_init() or Base is None:
        return

    from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime

    class AuditLog(Base):
        """Mirror of audit/decision_logs.json — queryable via SQL."""
        __tablename__ = "audit_log"
        id            = Column(Integer, primary_key=True, autoincrement=True)
        timestamp     = Column(String(50), nullable=False)
        workflow_id   = Column(String(100), nullable=False, index=True)
        agent_id      = Column(String(100), nullable=False)
        action        = Column(String(100), nullable=False)
        step_name     = Column(String(200))
        input_summary = Column(Text)
        output_summary= Column(Text)
        confidence    = Column(Float, default=1.0)
        retry_count   = Column(Integer, default=0)

        def __repr__(self):
            return f"<AuditLog {self.id} {self.agent_id}:{self.action}>"

    class WorkflowRecord(Base):
        """One row per completed workflow run."""
        __tablename__ = "workflow_records"
        id            = Column(Integer, primary_key=True, autoincrement=True)
        workflow_id   = Column(String(100), nullable=False, unique=True, index=True)
        workflow_type = Column(String(50), nullable=False)
        status        = Column(String(50), default="running")
        priority      = Column(String(20), default="normal")
        sla_breached  = Column(Boolean, default=False)
        total_retries = Column(Integer, default=0)
        tasks_count   = Column(Integer, default=0)
        created_at    = Column(String(50))
        completed_at  = Column(String(50))

    class TaskRecord(Base):
        """Meeting-intelligence tasks persisted for cross-session tracking."""
        __tablename__ = "task_records"
        id            = Column(Integer, primary_key=True, autoincrement=True)
        task_id       = Column(String(50), nullable=False, index=True)
        workflow_id   = Column(String(100), nullable=False, index=True)
        title         = Column(String(300))
        description   = Column(Text)
        owner         = Column(String(200))
        owner_email   = Column(String(200))
        priority      = Column(String(20))
        status        = Column(String(50), default="pending")
        deadline      = Column(String(50))
        escalation_count = Column(Integer, default=0)
        created_at    = Column(String(50))
        updated_at    = Column(String(50))

    return AuditLog, WorkflowRecord, TaskRecord


# Attempt model definition at import time
try:
    _models = _define_models()
    if _models:
        AuditLog, WorkflowRecord, TaskRecord = _models
    else:
        AuditLog = WorkflowRecord = TaskRecord = None
except Exception:
    AuditLog = WorkflowRecord = TaskRecord = None


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def create_all_tables():
    """Idempotent — safe to call on every app startup."""
    engine = get_engine()
    if engine is None or Base is None:
        return
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("All DB tables created / verified")
    except Exception as e:
        logger.warning(f"Table creation failed: {e}")
