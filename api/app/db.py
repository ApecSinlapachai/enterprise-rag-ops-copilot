"""PostgreSQL connection pool and database health helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages the psycopg3 connection pool lifecycle."""

    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 5) -> None:
        self._dsn = dsn
        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        self._opened = False

    def open(self) -> None:
        """Open the connection pool without failing app boot if DB is offline."""
        if self._opened:
            return
        try:
            self._pool.open(wait=True, timeout=3.0)
            self._opened = True
        except Exception as exc:
            logger.warning("Database pool did not open at startup: %s", exc)

    def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._opened:
            self._pool.close()
            self._opened = False

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Yield a pooled PostgreSQL connection."""
        if not self._opened:
            self._pool.open(wait=True, timeout=3.0)
            self._opened = True
        with self._pool.connection() as conn:
            yield conn

    def check_health(self) -> bool:
        """Verify database connectivity and pgvector availability."""
        try:
            with self.connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                row = cur.fetchone()
                return bool(row and row.get("ok") == 1)
        except Exception as exc:
            logger.debug("Database health probe failed: %s", exc)
            return False
