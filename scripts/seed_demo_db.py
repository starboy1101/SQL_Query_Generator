from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_price NUMERIC NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL,
    order_date TEXT NOT NULL,
    total_amount NUMERIC NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL
);
"""

CUSTOMERS = [
    (1, "Asha Rao", "asha@example.com", "India", "2025-01-05"),
    (2, "Daniel Kim", "daniel@example.com", "Singapore", "2025-01-17"),
    (3, "Maya Patel", "maya@example.com", "India", "2025-02-03"),
    (4, "Sofia Martin", "sofia@example.com", "France", "2025-02-20"),
]
PRODUCTS = [
    (1, "Mechanical Keyboard", "Accessories", 89.00, 1),
    (2, "4K Monitor", "Displays", 429.00, 1),
    (3, "USB-C Dock", "Accessories", 149.00, 1),
    (4, "Legacy Webcam", "Cameras", 39.00, 0),
]
ORDERS = [
    (1, 1, "completed", "2025-03-01", 518.00),
    (2, 2, "shipped", "2025-03-03", 298.00),
    (3, 1, "pending", "2025-03-07", 89.00),
    (4, 3, "completed", "2025-03-09", 858.00),
]
ORDER_ITEMS = [
    (1, 1, 1, 1, 89.00),
    (2, 1, 2, 1, 429.00),
    (3, 2, 3, 2, 149.00),
    (4, 3, 1, 1, 89.00),
    (5, 4, 2, 2, 429.00),
]


def seed(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?)", CUSTOMERS)
        connection.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", PRODUCTS)
        connection.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?)", ORDERS)
        connection.executemany("INSERT OR IGNORE INTO order_items VALUES (?, ?, ?, ?, ?)", ORDER_ITEMS)
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the local demonstration SQLite database")
    parser.add_argument("--path", type=Path, default=Path("data/demo.db"))
    args = parser.parse_args()
    seed(args.path.resolve())
    print(f"Seeded demo database at {args.path.resolve()}")


if __name__ == "__main__":
    main()
