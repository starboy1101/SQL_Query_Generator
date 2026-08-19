from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError

from gradio_client import Client
from gradio_client.exceptions import AppError
from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.core.config import Settings

DEFAULT_SPACE_ID = "omkar1804/sql-pilot-model"
REQUEST_TIMEOUT_SECONDS = 180
INVALID_DECODE_MARKERS = ("\u010a", "\u0120")

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
    settings = Settings()
    space_id = settings.hf_space_id.strip() or DEFAULT_SPACE_ID
    client = Client(
        space_id,
        token=settings.hf_space_token,
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
    except AppError as exc:
        message = str(exc)
        if "ZeroGPU runs limit" in message:
            if settings.hf_space_token:
                hint = (
                    "The authenticated Hugging Face account has exhausted its daily ZeroGPU quota. "
                    "Wait for the quota reset or use an account with additional quota."
                )
            else:
                hint = (
                    "The unauthenticated ZeroGPU quota is exhausted. Add a Hugging Face read token "
                    "to .env as HF_SPACE_TOKEN, then run this test again."
                )
            raise SystemExit(hint) from exc
        raise SystemExit(f"Space request failed: {message}") from exc

    if not isinstance(result, str) or not result.strip():
        raise SystemExit("Space returned an empty or non-text response")

    sql = result.strip()
    if "\x00" in sql or any(marker in sql for marker in INVALID_DECODE_MARKERS):
        raise SystemExit(f"Space returned malformed tokenizer text: {sql!r}")

    try:
        statements = parse(sql, read="sqlite")
    except ParseError as exc:
        raise SystemExit(f"Space returned invalid SQL: {sql!r}\nParser error: {exc}") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise SystemExit(f"Space did not return exactly one read-only query: {sql!r}")

    print(sql)


if __name__ == "__main__":
    main()
