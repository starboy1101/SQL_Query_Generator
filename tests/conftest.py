from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                country TEXT NOT NULL
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                total_amount NUMERIC NOT NULL
            );
            INSERT INTO customers VALUES (1, 'Asha', 'India'), (2, 'Daniel', 'Singapore');
            INSERT INTO orders VALUES (1, 1, 125.0), (2, 1, 75.0), (3, 2, 200.0);
            """
        )
    return path


@pytest.fixture
def settings(database_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{database_path.as_posix()}",
        database_dialect="sqlite",
        allowed_tables=("customers", "orders"),
        allow_query_execution=True,
        allow_direct_sql_execution=True,
        llm_backend="heuristic",
        max_repair_attempts=0,
        default_max_rows=25,
        max_rows_cap=50,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
