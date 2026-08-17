from __future__ import annotations

from app.db.schema import ColumnSchema, DatabaseSchema, TableSchema
from app.llm.prompt import PromptBuilder, extract_sql


def test_prompt_contains_schema_and_constraints() -> None:
    schema = DatabaseSchema(
        dialect="sqlite",
        tables=(TableSchema("customers", (ColumnSchema("id", "INTEGER", False, True),)),),
    )
    prompt = PromptBuilder().build(question="Count customers", schema=schema, dialect="sqlite", max_rows=10)
    assert "TABLE customers" in prompt
    assert "id INTEGER PK NOT NULL" in prompt
    assert "Count customers" in prompt
    assert "read-only" in prompt


def test_extracts_fenced_sql() -> None:
    assert (
        extract_sql("Here is the query:\n```sql\nSELECT * FROM customers;\n```") == "SELECT * FROM customers;"
    )
