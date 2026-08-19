from __future__ import annotations

import re

from app.db.schema import DatabaseSchema


class PromptBuilder:
    SYSTEM_INSTRUCTION = """# Follow these instructions:
You will be given table schemas for a database. Write one correct, read-only SQL query
that answers the question.

1. Return SQL only, on one line, without Markdown or commentary.
2. Use only tables and columns present in the schema; never invent identifiers.
3. Never use INSERT, UPDATE, DELETE, DDL, PRAGMA, stored procedures, or filesystem/network functions.
4. Prefer explicit JOIN conditions and qualify ambiguous columns with table aliases.
5. Respect the requested SQL dialect and maximum row count."""

    def build(self, *, question: str, schema: DatabaseSchema, dialect: str, max_rows: int) -> str:
        schema_text = self._serialize_schema(schema)
        return (
            f"{self.SYSTEM_INSTRUCTION}\n\n"
            f"# SQL dialect: {dialect}\n"
            f"# Maximum rows: {max_rows}\n\n"
            f"# Database and Table Schema:\n{schema_text}\n\n"
            "# Here are some Examples on how to generate SQL statements and use column names:\n\n"
            f"# Question: {question.strip()}\n\n"
            "# SQL:"
        )

    def build_repair(
        self,
        *,
        question: str,
        schema: DatabaseSchema,
        dialect: str,
        max_rows: int,
        invalid_sql: str,
        validation_error: str,
    ) -> str:
        base = self.build(question=question, schema=schema, dialect=dialect, max_rows=max_rows)
        return (
            f"{base}\n\n"
            "The previous attempt was rejected. Correct it using only the schema above.\n"
            f"Rejected SQL: {invalid_sql[:2000]}\n"
            f"Reason: {validation_error[:500]}\n"
            "Corrected SQL"
        )

    @staticmethod
    def _serialize_schema(schema: DatabaseSchema) -> str:
        lines: list[str] = []
        for table in schema.tables:
            column_parts = []
            for column in table.columns:
                markers = []
                if column.primary_key:
                    markers.append("PK")
                if not column.nullable:
                    markers.append("NOT NULL")
                suffix = f" {' '.join(markers)}" if markers else ""
                column_parts.append(f"{column.name} {column.data_type}{suffix}")
            lines.append(f"{table.kind.upper()} {table.name} ({', '.join(column_parts)})")
            for foreign_key in table.foreign_keys:
                lines.append(
                    "  FK "
                    f"({', '.join(foreign_key.columns)}) -> "
                    f"{foreign_key.referred_table}({', '.join(foreign_key.referred_columns)})"
                )
        return "\n".join(lines) if lines else "(no accessible tables)"


_CODE_BLOCK = re.compile(r"```(?:sql)?\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL)
_SQL_START = re.compile(r"^\s*(?:WITH|SELECT)\b", flags=re.IGNORECASE | re.MULTILINE)


def extract_sql(model_output: str) -> str:
    """Strip common chat-model wrappers without altering SQL semantics."""

    text = model_output.strip()
    code_match = _CODE_BLOCK.search(text)
    if code_match:
        text = code_match.group(1).strip()
    start = _SQL_START.search(text)
    if start:
        text = text[start.start() :]
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text.strip()
