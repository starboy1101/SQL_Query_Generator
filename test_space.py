from __future__ import annotations

import os
from concurrent.futures import TimeoutError as FutureTimeoutError

from gradio_client import Client
from sqlglot import exp, parse

SPACE_ID = os.getenv("HF_SPACE_ID", "omkar1804/sql-pilot-model")
REQUEST_TIMEOUT_SECONDS = 180

PROMPT = """# Follow these instructions:
You will be given table schemas for a database. Write one correct, read-only SQL query
that answers the question.

1. Return SQL only, on one line, without Markdown or commentary.
2. Use only tables and columns present in the schema; never invent identifiers.
3. Never use INSERT, UPDATE, DELETE, DDL, or PRAGMA.

# SQL dialect: sqlite
# Maximum rows: 100

# Database and Table Schema:
TABLE customers (id INTEGER PK NOT NULL, name TEXT NOT NULL)

# Here are some Examples on how to generate SQL statements and use column names:

# Question: How many customers are there?

# SQL:"""


def main() -> None:
    client = Client(
        SPACE_ID,
        verbose=False,
        analytics_enabled=False,
        download_files=False,
    )
    job = client.submit(
        prompt=PROMPT,
        max_new_tokens=128,
        api_name="/generate",
    )

    try:
        result = job.result(timeout=REQUEST_TIMEOUT_SECONDS)
    except FutureTimeoutError as exc:
        job.cancel()
        raise SystemExit(f"Space request timed out after {REQUEST_TIMEOUT_SECONDS} seconds") from exc

    if not isinstance(result, str) or not result.strip():
        raise SystemExit("Space returned an empty or non-text response")

    sql = result.strip()
    if "\x00" in sql or "Ċ" in sql or "Ġ" in sql:
        raise SystemExit(f"Space returned malformed tokenizer text: {sql!r}")

    statements = parse(sql, read="sqlite")
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise SystemExit(f"Space did not return exactly one read-only query: {sql!r}")

    print(sql)


if __name__ == "__main__":
    main()
