# sqlite_store.py


import sqlite3
import json
import asyncio
from langgraph.store.base import BaseStore  # Adjust this import as needed

class SQLiteStore(BaseStore):
    def __init__(self, db_path: str = "memory_store.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def get_connection(self, db_path: str = None):
        path = db_path or self.db_path
        # create and return a new instance (and connection) for the calling thread
        return SQLiteStore(path)

    def _create_table(self):
        # Create a table to store key-value pairs.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS store (
                namespace TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (namespace, key)
            )
            """
        )
        self.conn.commit()

    def get(self, namespace, key):
        cursor = self.conn.execute(
            "SELECT value FROM store WHERE namespace = ? AND key = ?",
            (json.dumps(namespace), key)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    def put(self, namespace, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO store (namespace, key, value) VALUES (?, ?, ?)",
            (json.dumps(namespace), key, json.dumps(value))
        )
        self.conn.commit()

    def delete(self, namespace, key):
        self.conn.execute(
            "DELETE FROM store WHERE namespace = ? AND key = ?",
            (json.dumps(namespace), key)
        )
        self.conn.commit()

    def batch(self, items: list[tuple]) -> None:
        """
        Synchronously store multiple key-value pairs.
        Each item in 'items' should be a tuple: (namespace, key, value).
        """
        for ns, key, value in items:
            self.put(ns, key, value)

    async def abatch(self, items: list[tuple]) -> None:
        """
        Asynchronously store multiple key-value pairs.
        Each item in 'items' should be a tuple: (namespace, key, value).
        """
        for ns, key, value in items:
            self.put(ns, key, value)
            await asyncio.sleep(0)  # Yield control to the event loop

    def __del__(self):
        self.conn.close()
