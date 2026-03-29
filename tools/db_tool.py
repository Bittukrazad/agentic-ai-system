"""tools/db_tool.py — SQLite / PostgreSQL database access"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./agentic_ai.db")

# In-memory fallback store for dev/test (no SQLAlchemy required)
_in_memory_db: Dict[str, List[Dict]] = {}


class DBTool:
    """
    Database interface for reading and writing enterprise records.
    Uses SQLAlchemy in production; falls back to in-memory dict in dev.

    Tables used:
      - workflow_records     — completed workflow run records
      - onboarding_records   — employee onboarding completion
      - payment_obligations  — procurement payment records
      - executed_contracts   — contract execution records
      - audit_log            — mirrors the JSON audit log
    """

    def __init__(self):
        self._engine = None
        self._try_init_sqlalchemy()

    def _try_init_sqlalchemy(self):
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.orm import sessionmaker
            self._engine = create_engine(DB_URL, echo=False)
            self._Session = sessionmaker(bind=self._engine)
            self._create_tables()
            logger.info(f"DB connected: {DB_URL}")
        except ImportError:
            logger.warning("SQLAlchemy not installed — using in-memory DB")
        except Exception as e:
            logger.warning(f"DB connection failed ({e}) — using in-memory DB")

    def _create_tables(self):
        if not self._engine:
            return
        from sqlalchemy import text
        ddl_statements = [
            """CREATE TABLE IF NOT EXISTS workflow_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT, workflow_type TEXT, status TEXT,
                created_at TEXT, completed_at TEXT, data TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS onboarding_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT, employee_name TEXT, status TEXT,
                created_at TEXT, data TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS payment_obligations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT, vendor TEXT, amount REAL,
                status TEXT, payment_terms TEXT, created_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS executed_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT, contract_id TEXT, status TEXT,
                parties TEXT, created_at TEXT
            )""",
        ]
        with self._engine.connect() as conn:
            for ddl in ddl_statements:
                conn.execute(text(ddl))
            conn.commit()

    def write(self, table: str, data: Dict) -> Dict:
        """Insert a record into the specified table"""
        data["created_at"] = datetime.now(timezone.utc).isoformat()

        if self._engine:
            try:
                from sqlalchemy import text
                cols = ", ".join(data.keys())
                placeholders = ", ".join(f":{k}" for k in data.keys())
                sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
                with self._engine.connect() as conn:
                    result = conn.execute(text(sql), data)
                    conn.commit()
                    return {"ok": True, "row_id": result.lastrowid, "table": table}
            except Exception as e:
                logger.warning(f"DB write failed ({e}), using in-memory fallback")

        # In-memory fallback
        if table not in _in_memory_db:
            _in_memory_db[table] = []
        _in_memory_db[table].append(data)
        logger.info(f"[DB IN-MEMORY] INSERT INTO {table} | data={list(data.keys())}")
        return {"ok": True, "mock": True, "table": table, "row_count": len(_in_memory_db[table])}

    def read(self, table: str, filters: Dict = None) -> List[Dict]:
        """Read records from a table with optional filters"""
        if self._engine:
            try:
                from sqlalchemy import text
                sql = f"SELECT * FROM {table}"
                if filters:
                    where_clause = " AND ".join(f"{k} = :{k}" for k in filters)
                    sql += f" WHERE {where_clause}"
                with self._engine.connect() as conn:
                    result = conn.execute(text(sql), filters or {})
                    rows = [dict(r._mapping) for r in result]
                return rows
            except Exception as e:
                logger.warning(f"DB read failed: {e}")

        # In-memory fallback
        rows = _in_memory_db.get(table, [])
        if filters:
            rows = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
        return rows