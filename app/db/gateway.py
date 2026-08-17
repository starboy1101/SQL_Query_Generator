from __future__ import annotations

import datetime as dt
import decimal
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import QueryExecutionError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: float


def create_database_engine(database_url: str) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **kwargs)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def set_sqlite_readonly_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA query_only = ON")
            finally:
                cursor.close()

    return engine


class DatabaseGateway:
    def __init__(self, engine: Engine, *, timeout_seconds: int = 10) -> None:
        self._engine = engine
        self._timeout_seconds = timeout_seconds

    def ping(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            logger.exception("Database health check failed")
            return False

    def execute(self, sql: str) -> QueryResult:
        started_at = time.perf_counter()
        sqlite_connection: Any = None
        try:
            with self._engine.connect() as connection:
                self._apply_transaction_guards(connection)
                if self._engine.dialect.name == "sqlite":
                    sqlite_connection = connection.connection.driver_connection
                    sqlite_connection.set_progress_handler(
                        lambda: 1 if time.perf_counter() - started_at > self._timeout_seconds else 0,
                        10_000,
                    )
                result = connection.execution_options(timeout=self._timeout_seconds).execute(text(sql))
                columns = list(result.keys())
                rows = [
                    {key: _json_safe(value) for key, value in row._mapping.items()}
                    for row in result.fetchall()
                ]
        except SQLAlchemyError as exc:
            logger.warning("Read-only query execution failed", extra={"error_type": type(exc).__name__})
            raise QueryExecutionError("The generated query could not be executed") from exc
        finally:
            if sqlite_connection is not None:
                sqlite_connection.set_progress_handler(None, 0)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )

    def _apply_transaction_guards(self, connection: Any) -> None:
        dialect = self._engine.dialect.name
        if dialect == "postgresql":
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text(f"SET LOCAL statement_timeout = {self._timeout_seconds * 1000}"))
        elif dialect in {"mysql", "mariadb"}:
            connection.execute(text("SET TRANSACTION READ ONLY"))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)
