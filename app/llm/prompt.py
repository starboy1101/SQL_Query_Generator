from __future__ import annotations

import re

from app.db.schema import DatabaseSchema


class PromptBuilder:
    SYSTEM_INSTRUCTION = """You are an expert data analyst who writes precise, read-only SQL.
Return exactly one SQL SELECT statement and no commentary.
Use only the tables and columns in the provided schema.
Never use INSERT, UPDATE, DELETE, DDL, PRAGMA, stored procedures, or filesystem/network functions.
Prefer explicit JOIN conditions and qualify ambiguous columns with table aliases.
Never invent identifiers. Respect the requested SQL dialect and row limit."""

    def build(self, *, question: str, schema: DatabaseSchema, dialect: str, max_rows: int) -> str:
        schema_text = self._serialize_schema(schema)
        return (
            f"{self.SYSTEM_INSTRUCTION}\n\n"
            f"SQL dialect: {dialect}\n"
            f"Maximum rows: {max_rows}\n\n"
            f"DATABASE SCHEMA\n{schema_text}\n\n"
            f"USER QUESTION\n{question.strip()}\n\n"
            "SQL"
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
_SQL_START = re.compile(r"\b(?:WITH|SELECT)\b", flags=re.IGNORECASE)


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
