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
    assert prompt.endswith("# SQL:")


def test_extracts_fenced_sql() -> None:
    assert (
        extract_sql("Here is the query:\n```sql\nSELECT * FROM customers;\n```") == "SELECT * FROM customers;"
    )


def test_extract_sql_uses_a_query_at_the_start_of_a_line() -> None:
    output = "Here is a SELECT query:\nSELECT * FROM customers;"
    assert extract_sql(output) == "SELECT * FROM customers;"


def test_extract_sql_preserves_multiple_statements_for_validation() -> None:
    output = "SELECT * FROM customers; DROP TABLE customers;"
    assert extract_sql(output) == output
