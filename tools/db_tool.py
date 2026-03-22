"""
Database Tool - Abstraction layer for database operations.

Provides:
- Generic CRUD operations
- Support for multiple backends (JSON, SQLite, PostgreSQL)
- Query building
- Transaction support
- Connection pooling
"""

from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod
from datetime import datetime
import json
import sqlite3
from pathlib import Path
import uuid
from utils.logger import get_logger
from utils.helpers import get_iso_now

logger = get_logger(__name__)


class DBResponse:
    """Database operation response."""
    
    def __init__(
        self,
        success: bool,
        data: Union[Dict[str, Any], List[Dict[str, Any]]] = None,
        error: str = "",
        record_count: int = 0
    ):
        """
        Initialize response.
        
        Args:
            success: Whether operation succeeded
            data: Response data
            error: Error message
            record_count: Number of records
        """
        self.success = success
        self.data = data or {}
        self.error = error
        self.record_count = record_count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "record_count": self.record_count
        }


class DBBackend(ABC):
    """Abstract database backend."""
    
    @abstractmethod
    async def insert(
        self,
        table: str,
        record: Dict[str, Any]
    ) -> DBResponse:
        """Insert record."""
        pass
    
    @abstractmethod
    async def find_by_id(
        self,
        table: str,
        record_id: str
    ) -> DBResponse:
        """Find record by ID."""
        pass
    
    @abstractmethod
    async def find(
        self,
        table: str,
        query: Dict[str, Any]
    ) -> DBResponse:
        """Find records by query."""
        pass
    
    @abstractmethod
    async def update(
        self,
        table: str,
        record_id: str,
        updates: Dict[str, Any]
    ) -> DBResponse:
        """Update record."""
        pass
    
    @abstractmethod
    async def delete(
        self,
        table: str,
        record_id: str
    ) -> DBResponse:
        """Delete record."""
        pass
    
    @abstractmethod
    async def list_all(
        self,
        table: str,
        limit: int = 100
    ) -> DBResponse:
        """List all records."""
        pass


class JSONDBBackend(DBBackend):
    """JSON file-based database backend."""
    
    def __init__(self, db_path: str = "data.json"):
        """
        Initialize JSON backend.
        
        Args:
            db_path: Path to JSON database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.db_path.exists():
            self.db_path.write_text(json.dumps({}))
    
    async def insert(
        self,
        table: str,
        record: Dict[str, Any]
    ) -> DBResponse:
        """Insert record."""
        try:
            data = json.loads(self.db_path.read_text())
            
            if table not in data:
                data[table] = []
            
            record_id = record.get("id") or str(uuid.uuid4())
            record["id"] = record_id
            record["created_at"] = get_iso_now()
            
            data[table].append(record)
            self.db_path.write_text(json.dumps(data, indent=2))
            
            return DBResponse(success=True, data=record)
        
        except Exception as e:
            logger.error(f"Insert error: {str(e)}")
            return DBResponse(success=False, error=str(e))
    
    async def find_by_id(
        self,
        table: str,
        record_id: str
    ) -> DBResponse:
        """Find record by ID."""
        try:
            data = json.loads(self.db_path.read_text())
            
            if table not in data:
                return DBResponse(success=True, data={})
            
            for record in data[table]:
                if record.get("id") == record_id:
                    return DBResponse(success=True, data=record)
            
            return DBResponse(success=True, data={})
        
        except Exception as e:
            logger.error(f"Find by ID error: {str(e)}")
            return DBResponse(success=False, error=str(e))
    
    async def find(
        self,
        table: str,
        query: Dict[str, Any]
    ) -> DBResponse:
        """Find records by query."""
        try:
            data = json.loads(self.db_path.read_text())
            
            if table not in data:
                return DBResponse(success=True, data=[])
            
            results = []
            for record in data[table]:
                match = True
                for key, value in query.items():
                    if record.get(key) != value:
                        match = False
                        break
                
                if match:
                    results.append(record)
            
            return DBResponse(
                success=True,
                data=results,
                record_count=len(results)
            )
        
        except Exception as e:
            logger.error(f"Find error: {str(e)}")
            return DBResponse(success=False, error=str(e))
    
    async def update(
        self,
        table: str,
        record_id: str,
        updates: Dict[str, Any]
    ) -> DBResponse:
        """Update record."""
        try:
            data = json.loads(self.db_path.read_text())
            
            if table not in data:
                return DBResponse(
                    success=False,
                    error=f"Table {table} not found"
                )
            
            for record in data[table]:
                if record.get("id") == record_id:
                    record.update(updates)
                    record["updated_at"] = get_iso_now()
                    self.db_path.write_text(json.dumps(data, indent=2))
                    return DBResponse(success=True, data=record)
            
            return DBResponse(
                success=False,
                error=f"Record {record_id} not found"
            )
        
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            return DBResponse(success=False, error=str(e))
    
    async def delete(
        self,
        table: str,
        record_id: str
    ) -> DBResponse:
        """Delete record."""
        try:
            data = json.loads(self.db_path.read_text())
            
            if table not in data:
                return DBResponse(
                    success=False,
                    error=f"Table {table} not found"
                )
            
            for i, record in enumerate(data[table]):
                if record.get("id") == record_id:
                    deleted = data[table].pop(i)
                    self.db_path.write_text(json.dumps(data, indent=2))
                    return DBResponse(success=True, data=deleted)
            
            return DBResponse(
                success=False,
                error=f"Record {record_id} not found"
            )
        
        except Exception as e:
            logger.error(f"Delete error: {str(e)}")
            return DBResponse(success=False, error=str(e))
    
    async def list_all(
        self,
        table: str,
        limit: int = 100
    ) -> DBResponse:
        """List all records."""
        try:
            data = json.loads(self.db_path.read_text())
            
            if table not in data:
                return DBResponse(success=True, data=[])
            
            records = data[table][:limit]
            return DBResponse(
                success=True,
                data=records,
                record_count=len(records)
            )
        
        except Exception as e:
            logger.error(f"List error: {str(e)}")
            return DBResponse(success=False, error=str(e))


class DBTool:
    """
    Database abstraction tool.
    
    Features:
    - Generic CRUD API
    - Multiple backend support
    - ID and timestamp auto-generation
    - Query building
    """
    
    def __init__(self, backend: Optional[DBBackend] = None):
        """
        Initialize DB tool.
        
        Args:
            backend: Database backend instance
        """
        self.backend = backend or JSONDBBackend()
        self.operation_count = 0
    
    async def insert(
        self,
        table: str,
        record: Dict[str, Any]
    ) -> DBResponse:
        """
        Insert record.
        
        Args:
            table: Table/collection name
            record: Record data
            
        Returns:
            DBResponse
        """
        self.operation_count += 1
        return await self.backend.insert(table, record)
    
    async def find_by_id(
        self,
        table: str,
        record_id: str
    ) -> DBResponse:
        """
        Find by ID.
        
        Args:
            table: Table name
            record_id: Record ID
            
        Returns:
            DBResponse
        """
        self.operation_count += 1
        return await self.backend.find_by_id(table, record_id)
    
    async def find(
        self,
        table: str,
        query: Dict[str, Any]
    ) -> DBResponse:
        """
        Find records.
        
        Args:
            table: Table name
            query: Query dict
            
        Returns:
            DBResponse
        """
        self.operation_count += 1
        return await self.backend.find(table, query)
    
    async def update(
        self,
        table: str,
        record_id: str,
        updates: Dict[str, Any]
    ) -> DBResponse:
        """
        Update record.
        
        Args:
            table: Table name
            record_id: Record ID
            updates: Update dict
            
        Returns:
            DBResponse
        """
        self.operation_count += 1
        return await self.backend.update(table, record_id, updates)
    
    async def delete(
        self,
        table: str,
        record_id: str
    ) -> DBResponse:
        """
        Delete record.
        
        Args:
            table: Table name
            record_id: Record ID
            
        Returns:
            DBResponse
        """
        self.operation_count += 1
        return await self.backend.delete(table, record_id)
    
    async def list_all(
        self,
        table: str,
        limit: int = 100
    ) -> DBResponse:
        """
        List records.
        
        Args:
            table: Table name
            limit: Max records
            
        Returns:
            DBResponse
        """
        self.operation_count += 1
        return await self.backend.list_all(table, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "total_operations": self.operation_count,
            "backend_type": self.backend.__class__.__name__
        }


# Global DB tool instance
_db_tool: Optional[DBTool] = None


def get_db_tool(backend: Optional[DBBackend] = None) -> DBTool:
    """Get or create global DB tool."""
    global _db_tool
    
    if _db_tool is None:
        _db_tool = DBTool(backend or JSONDBBackend())
    
    return _db_tool

    def delete(self, record_id):
        self.storage = [r for r in self.storage if r["id"] != record_id]
        return {"status": "deleted"}

    def find_delayed_tasks(self):
        return [r for r in self.storage if r.get("status") == "delayed"]

    def find_by_status(self, status):
        return [r for r in self.storage if r.get("status") == status]

    def get_stats(self):
        total = len(self.storage)
        delayed = len(self.find_delayed_tasks())
        completed = len(self.find_by_status("completed"))

        return {
            "total_tasks": total,
            "delayed_tasks": delayed,
            "completed_tasks": completed,
            "efficiency": (completed / max(1, total))
        }