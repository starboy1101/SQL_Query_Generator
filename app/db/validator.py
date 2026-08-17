from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.core.errors import InvalidQueryError, UnsafeQueryError


@dataclass(frozen=True, slots=True)
class ValidatedQuery:
    sql: str
    tables: tuple[str, ...]
    limit: int


class SQLValidator:
    """Parse, authorize, and normalize model-generated SQL."""

    _prohibited_node_names = (
        "Alter",
        "Analyze",
        "Attach",
        "Command",
        "Copy",
        "Create",
        "Delete",
        "Detach",
        "Drop",
        "Grant",
        "Insert",
        "Into",
        "LoadData",
        "Lock",
        "Merge",
        "Pragma",
        "Revoke",
        "Set",
        "Transaction",
        "TruncateTable",
        "Update",
        "Use",
    )
    _dangerous_functions: ClassVar[set[str]] = {
        "benchmark",
        "dblink",
        "dblink_connect",
        "load_extension",
        "load_file",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_sleep",
        "sleep",
        "sys_eval",
        "sys_exec",
    }

    def validate(
        self,
        sql: str,
        *,
        dialect: str,
        allowed_tables: set[str],
        max_rows: int,
    ) -> ValidatedQuery:
        candidate = sql.strip()
        if not candidate:
            raise InvalidQueryError("The model returned an empty query")

        try:
            statements = sqlglot.parse(candidate, read=dialect)
        except (ParseError, ValueError) as exc:
            raise InvalidQueryError("The generated SQL could not be parsed") from exc

        parsed_statements = [statement for statement in statements if statement is not None]
        if len(parsed_statements) != 1:
            raise UnsafeQueryError("Exactly one SQL statement is allowed")

        statement = parsed_statements[0]
        if not isinstance(statement, exp.Query):
            raise UnsafeQueryError("Only read-only query expressions are allowed")
        if not statement.find(exp.Select):
            raise UnsafeQueryError("Only read-only SELECT queries are allowed")

        prohibited_types = tuple(
            node_type
            for name in self._prohibited_node_names
            if isinstance((node_type := getattr(exp, name, None)), type)
        )
        prohibited = next(statement.find_all(*prohibited_types), None) if prohibited_types else None
        if prohibited is not None:
            raise UnsafeQueryError(
                "The query contains a prohibited operation",
                details={"operation": type(prohibited).__name__},
            )

        self._validate_functions(statement)
        tables = self._validate_tables(statement, allowed_tables)
        normalized = self._enforce_limit(statement, max_rows=max_rows)

        return ValidatedQuery(
            sql=normalized.sql(dialect=dialect, pretty=True),
            tables=tuple(sorted(tables)),
            limit=max_rows,
        )

    def _validate_tables(self, statement: exp.Expression, allowed_tables: set[str]) -> set[str]:
        normalized_allowed = {name.lower() for name in allowed_tables}
        cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
        referenced: set[str] = set()

        for table in statement.find_all(exp.Table):
            name = table.name
            if not name or name.lower() in cte_names:
                continue
            if table.catalog or table.db:
                raise UnsafeQueryError("Cross-schema and cross-database references are not allowed")
            if name.lower() not in normalized_allowed:
                raise UnsafeQueryError(
                    f"Table '{name}' is not available to this service",
                    details={"table": name},
                )
            referenced.add(name)

        return referenced

    def _validate_functions(self, statement: exp.Expression) -> None:
        for function in statement.find_all(exp.Func):
            name = str(function.sql_name()).lower()  # type: ignore[no-untyped-call]
            if isinstance(function, exp.Anonymous):
                name = function.name.lower()
            if name in self._dangerous_functions:
                raise UnsafeQueryError(
                    f"Function '{name}' is not permitted",
                    details={"function": name},
                )

    @staticmethod
    def _enforce_limit(statement: exp.Query, *, max_rows: int) -> exp.Query:
        current_limit = statement.args.get("limit")
        if current_limit is None:
            return statement.limit(max_rows)

        limit_expression = current_limit.expression
        if not isinstance(limit_expression, exp.Literal) or not limit_expression.is_int:
            return statement.limit(max_rows)
        if int(limit_expression.this) > max_rows:
            return statement.limit(max_rows)
        return statement
