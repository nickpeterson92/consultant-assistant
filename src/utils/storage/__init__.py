"""Storage utilities for the multi-agent orchestrator system."""

from .sqlite_store import SQLiteStore
from .async_sqlite import AsyncSQLiteStore
from .async_store_adapter import get_async_store_adapter

# Global SQLite store instance
global_sqlite_store = None

def get_global_sqlite_store():
    """Get or create the global SQLite store instance."""
    global global_sqlite_store
    if global_sqlite_store is None:
        global_sqlite_store = SQLiteStore("memory_store.db")
    return global_sqlite_store

__all__ = [
    "SQLiteStore",
    "AsyncSQLiteStore", 
    "get_async_store_adapter",
    "global_sqlite_store",
    "get_global_sqlite_store"
]