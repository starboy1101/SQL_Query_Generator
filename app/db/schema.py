from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import Engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import DatabaseUnavailableError


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool = False


@dataclass(frozen=True, slots=True)
class ForeignKeySchema:
    columns: tuple[str, ...]
    referred_table: str
    referred_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    columns: tuple[ColumnSchema, ...]
    foreign_keys: tuple[ForeignKeySchema, ...] = ()
    kind: str = "table"


@dataclass(frozen=True, slots=True)
class DatabaseSchema:
    dialect: str
    tables: tuple[TableSchema, ...]

    @property
    def table_names(self) -> set[str]:
        return {table.name for table in self.tables}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SchemaIntrospector:
    def __init__(
        self,
        engine: Engine,
        *,
        dialect: str,
        schema_name: str | None = None,
        allowed_tables: tuple[str, ...] = (),
        include_views: bool = True,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._engine = engine
        self._dialect = dialect
        self._schema_name = schema_name
        self._allowed_tables = {name.lower() for name in allowed_tables}
        self._include_views = include_views
        self._cache_ttl = cache_ttl_seconds
        self._cached: DatabaseSchema | None = None
        self._cached_at = 0.0
        self._lock = threading.Lock()

    def get_schema(self, *, force_refresh: bool = False) -> DatabaseSchema:
        now = time.monotonic()
        if not force_refresh and self._cached and now - self._cached_at < self._cache_ttl:
            return self._cached

        with self._lock:
            now = time.monotonic()
            if not force_refresh and self._cached and now - self._cached_at < self._cache_ttl:
                return self._cached
            try:
                inspector = inspect(self._engine)
                table_names = inspector.get_table_names(schema=self._schema_name)
                view_names = inspector.get_view_names(schema=self._schema_name) if self._include_views else []
                schemas = [self._load_table(inspector, name, "table") for name in table_names]
                schemas.extend(self._load_table(inspector, name, "view") for name in view_names)
            except SQLAlchemyError as exc:
                raise DatabaseUnavailableError("Unable to inspect the configured database") from exc

            filtered = tuple(
                sorted(
                    (table for table in schemas if self._is_allowed(table.name)),
                    key=lambda table: table.name.lower(),
                )
            )
            self._cached = DatabaseSchema(dialect=self._dialect, tables=filtered)
            self._cached_at = time.monotonic()
            return self._cached

    def clear_cache(self) -> None:
        with self._lock:
            self._cached = None
            self._cached_at = 0.0

    def _is_allowed(self, table_name: str) -> bool:
        return not self._allowed_tables or table_name.lower() in self._allowed_tables

    def _load_table(self, inspector: Any, name: str, kind: str) -> TableSchema:
        pk_constraint = inspector.get_pk_constraint(name, schema=self._schema_name) or {}
        primary_keys = set(pk_constraint.get("constrained_columns") or [])
        columns = tuple(
            ColumnSchema(
                name=column["name"],
                data_type=str(column["type"]),
                nullable=bool(column.get("nullable", True)),
                primary_key=column["name"] in primary_keys,
            )
            for column in inspector.get_columns(name, schema=self._schema_name)
        )
        foreign_keys = tuple(
            ForeignKeySchema(
                columns=tuple(foreign_key.get("constrained_columns") or ()),
                referred_table=foreign_key.get("referred_table") or "",
                referred_columns=tuple(foreign_key.get("referred_columns") or ()),
            )
            for foreign_key in inspector.get_foreign_keys(name, schema=self._schema_name)
        )
        return TableSchema(name=name, columns=columns, foreign_keys=foreign_keys, kind=kind)
