from __future__ import annotations

import pytest

from app.core.errors import UnsafeQueryError
from app.db.validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator()


def test_adds_limit_to_safe_select(validator: SQLValidator) -> None:
    result = validator.validate(
        "SELECT id, name FROM customers ORDER BY id",
        dialect="sqlite",
        allowed_tables={"customers"},
        max_rows=20,
    )
    assert "LIMIT 20" in result.sql
    assert result.tables == ("customers",)


def test_clamps_excessive_limit(validator: SQLValidator) -> None:
    result = validator.validate(
        "SELECT * FROM customers LIMIT 99999",
        dialect="sqlite",
        allowed_tables={"customers"},
        max_rows=10,
    )
    assert "LIMIT 10" in result.sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "SELECT * FROM customers; DROP TABLE customers",
        "SELECT pg_sleep(10)",
        "SELECT * FROM private_data",
        "SELECT * FROM main.customers",
    ],
)
def test_rejects_unsafe_queries(validator: SQLValidator, sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validator.validate(sql, dialect="sqlite", allowed_tables={"customers"}, max_rows=10)


def test_allows_cte_over_authorized_table(validator: SQLValidator) -> None:
    result = validator.validate(
        "WITH recent AS (SELECT id FROM orders) SELECT id FROM recent",
        dialect="sqlite",
        allowed_tables={"orders"},
        max_rows=10,
    )
    assert result.tables == ("orders",)
