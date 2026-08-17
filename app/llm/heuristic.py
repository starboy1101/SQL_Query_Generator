from __future__ import annotations

import re
from collections.abc import Callable

from app.core.errors import ModelUnavailableError
from app.db.schema import DatabaseSchema, TableSchema
from app.llm.base import GenerationInput


class HeuristicBackend:
    """Dependency-free development backend; not a replacement for the trained model."""

    def __init__(self, schema_provider: Callable[[], DatabaseSchema]) -> None:
        self._schema_provider = schema_provider

    @property
    def model_id(self) -> str:
        return "heuristic-development-backend"

    def warmup(self) -> None:
        return None

    def generate(self, generation_input: GenerationInput) -> str:
        schema: DatabaseSchema = self._schema_provider()
        if not schema.tables:
            raise ModelUnavailableError("No database tables are available for query generation")

        question = generation_input.question.lower()
        table = self._choose_table(schema, question)
        quote = "`" if generation_input.dialect == "mysql" else '"'
        table_name = _quote_identifier(table.name, quote)

        if any(token in question for token in ("how many", "count", "number of")):
            return f"SELECT COUNT(*) AS count FROM {table_name}"

        aggregate = self._find_aggregate(question, table, quote)
        if aggregate:
            return f"SELECT {aggregate} FROM {table_name}"

        columns = ", ".join(_quote_identifier(column.name, quote) for column in table.columns[:8]) or "*"
        return f"SELECT {columns} FROM {table_name} LIMIT {generation_input.max_rows}"

    @staticmethod
    def _choose_table(schema: DatabaseSchema, question: str) -> TableSchema:
        for table in schema.tables:
            variants = {table.name.lower(), table.name.lower().replace("_", " ")}
            if any(re.search(rf"\b{re.escape(variant)}\b", question) for variant in variants):
                return table
        return schema.tables[0]

    @staticmethod
    def _find_aggregate(question: str, table: TableSchema, quote: str) -> str | None:
        aggregate_names = {
            "average": "AVG",
            "avg": "AVG",
            "maximum": "MAX",
            "highest": "MAX",
            "minimum": "MIN",
            "lowest": "MIN",
            "sum": "SUM",
            "total": "SUM",
        }
        operation = next((sql for word, sql in aggregate_names.items() if word in question), None)
        if not operation:
            return None
        for column in table.columns:
            variants = {column.name.lower(), column.name.lower().replace("_", " ")}
            if any(variant in question for variant in variants):
                identifier = _quote_identifier(column.name, quote)
                return f"{operation}({identifier}) AS value"
        return None


def _quote_identifier(identifier: str, quote: str) -> str:
    escaped = identifier.replace(quote, quote * 2)
    return f"{quote}{escaped}{quote}"
