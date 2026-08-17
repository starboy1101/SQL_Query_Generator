from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def serialize_schema(database_path: Path) -> str:
    lines: list[str] = []
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for (table_name,) in table_rows:
            escaped_name = str(table_name).replace('"', '""')
            columns = connection.execute(f'PRAGMA table_info("{escaped_name}")').fetchall()
            column_text = ", ".join(
                f"{column[1]} {column[2] or 'TEXT'}{' PK' if column[5] else ''}" for column in columns
            )
            lines.append(f"TABLE {table_name} ({column_text})")
            foreign_keys = connection.execute(f'PRAGMA foreign_key_list("{escaped_name}")').fetchall()
            for foreign_key in foreign_keys:
                lines.append(f"  FK ({foreign_key[3]}) -> {foreign_key[2]}({foreign_key[4]})")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Spider examples to QLoRA training JSONL")
    parser.add_argument("--input", type=Path, required=True, help="Spider train/dev JSON file")
    parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    examples: list[dict[str, Any]] = json.loads(args.input.read_text(encoding="utf-8"))
    schema_cache: dict[str, str] = {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for example in examples:
            database_id = str(example["db_id"])
            if database_id not in schema_cache:
                database_path = args.database_dir / database_id / f"{database_id}.sqlite"
                schema_cache[database_id] = serialize_schema(database_path)
            record = {
                "question": example["question"],
                "schema": schema_cache[database_id],
                "sql": example["query"],
                "dialect": "sqlite",
                "db_id": database_id,
            }
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(examples)} examples to {args.output}")


if __name__ == "__main__":
    main()
