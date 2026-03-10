"""
DatabaseQueue - Wrapper for Database class (PostgreSQL Adaptation)
Original purpose was Single Writer Pattern for SQLite.
For PostgreSQL, we can use the connection pool directly.
This class is kept for backward compatibility with existing code.
"""

import logging
from typing import Tuple, List, Optional, Any
from src.database import Database

logger = logging.getLogger("DatabaseQueue")

class DatabaseQueue:
    """
    Passthrough wrapper for Database class.
    PostgreSQL handles concurrency, so we don't need a queue.
    """

    def __init__(self, db_path=None, batch_size=10, batch_timeout=1.0):
        self._db_path = db_path
        # batch_size/timeout ignored

    @property
    def db(self):
        return Database(self._db_path)

    def start(self):
        """No-op for Postgres"""
        pass

    def stop(self, timeout=10):
        """No-op for Postgres"""
        pass

    def execute_write(self, query: str, params: tuple = (),
                     wait_for_result: bool = False, timeout: float = 30.0) -> Optional[int]:
        """
        Execute a write query (INSERT, UPDATE, DELETE).
        """
        cursor = self.db.execute(query, params)
        if wait_for_result:
            return cursor.lastrowid
        return None

    def execute_read(self, query: str, params: tuple = ()) -> List[Tuple]:
        """
        Execute a read query (SELECT).
        """
        cursor = self.db.query(query, params)
        # query returns list of tuples directly in new Database class implementation
        return cursor

    def query(self, query: str, params: tuple = ()) -> List[Tuple]:
        """Alias for execute_read"""
        return self.execute_read(query, params)

    def execute(self, query: str, params: tuple = ()) -> Optional[int]:
        """Alias for execute_write"""
        return self.execute_write(query, params, wait_for_result=True)

    def get_stats(self) -> dict:
        """Get stats (dummy)"""
        return {'writes_processed': 0, 'batch_count': 0, 'mode': 'direct_postgres'}


# Global instance (singleton pattern)
_db_queue_instance = None

def get_db_queue(db_path=None) -> DatabaseQueue:
    """Get or create global DatabaseQueue instance"""
    global _db_queue_instance

    if _db_queue_instance is None:
        _db_queue_instance = DatabaseQueue(db_path)

    return _db_queue_instance
