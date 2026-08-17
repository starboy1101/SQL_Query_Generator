from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

from app.db.gateway import create_database_engine
from app.db.schema import SchemaIntrospector
from app.db.validator import SQLValidator
from app.llm.base import GenerationInput
from app.llm.huggingface import HuggingFaceBackend
from app.llm.prompt import PromptBuilder, extract_sql


def execute_readonly(database_path: Path, sql: str, timeout_seconds: float) -> list[tuple[Any, ...]]:
    started_at = time.monotonic()
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() - started_at > timeout_seconds else 0,
            10_000,
        )
        return connection.execute(sql).fetchall()


def execution_matches(gold_sql: str, predicted_sql: str, database_path: Path, timeout: float) -> bool:
    gold_rows = execute_readonly(database_path, gold_sql, timeout)
    predicted_rows = execute_readonly(database_path, predicted_sql, timeout)
    if "order by" in gold_sql.lower():
        return gold_rows == predicted_rows
    return Counter(map(_stable_row, gold_rows)) == Counter(map(_stable_row, predicted_rows))


def _stable_row(row: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple("<NULL>" if value is None else repr(value) for value in row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure execution accuracy on Spider SQLite databases")
    parser.add_argument("--examples", type=Path, required=True, help="Spider dev JSON")
    parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, help="Optional JSONL with predicted_sql in example order")
    parser.add_argument("--model", default="codellama/CodeLlama-7b-Instruct-hf")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/spider-results.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-rows", type=int, default=10_000)
    parser.add_argument("--no-4bit", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    examples: list[dict[str, Any]] = json.loads(args.examples.read_text(encoding="utf-8"))
    if args.limit:
        examples = examples[: args.limit]

    predictions: list[str] | None = None
    model: HuggingFaceBackend | None = None
    if args.predictions:
        prediction_records = [
            json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines()
        ]
        predictions = [record["predicted_sql"] for record in prediction_records]
        if len(predictions) < len(examples):
            raise ValueError("Predictions file has fewer rows than the evaluation examples")
    else:
        model = HuggingFaceBackend(
            model_name_or_path=args.model,
            adapter_path=str(args.adapter) if args.adapter else None,
            device="auto",
            use_4bit=not args.no_4bit,
            trust_remote_code=False,
            max_input_tokens=3072,
            max_new_tokens=256,
            temperature=0.0,
        )

    prompt_builder = PromptBuilder()
    validator = SQLValidator()
    results: list[dict[str, Any]] = []
    correct = 0

    for index, example in enumerate(examples):
        database_id = str(example["db_id"])
        database_path = args.database_dir / database_id / f"{database_id}.sqlite"
        generated_sql = predictions[index] if predictions is not None else ""
        error: str | None = None
        engine = create_database_engine(f"sqlite:///{database_path.resolve().as_posix()}")
        try:
            schema = SchemaIntrospector(engine, dialect="sqlite", cache_ttl_seconds=0).get_schema()
            if model is not None:
                prompt = prompt_builder.build(
                    question=example["question"],
                    schema=schema,
                    dialect="sqlite",
                    max_rows=args.max_rows,
                )
                generated_sql = extract_sql(
                    model.generate(
                        GenerationInput(
                            prompt=prompt,
                            question=example["question"],
                            dialect="sqlite",
                            max_rows=args.max_rows,
                        )
                    )
                )
            validated = validator.validate(
                generated_sql,
                dialect="sqlite",
                allowed_tables=schema.table_names,
                max_rows=args.max_rows,
            )
            generated_sql = validated.sql
            matched = execution_matches(example["query"], generated_sql, database_path, args.timeout)
        except Exception as exc:
            matched = False
            error = f"{type(exc).__name__}: {exc}"
        finally:
            engine.dispose()

        correct += int(matched)
        results.append(
            {
                "db_id": database_id,
                "question": example["question"],
                "gold_sql": example["query"],
                "predicted_sql": generated_sql,
                "execution_match": matched,
                "error": error,
            }
        )
        print(f"[{index + 1}/{len(examples)}] {'PASS' if matched else 'FAIL'} {database_id}")

    accuracy = correct / len(examples) if examples else 0.0
    report = {
        "metric": "execution_accuracy",
        "correct": correct,
        "total": len(examples),
        "accuracy": accuracy,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Execution accuracy: {accuracy:.2%} ({correct}/{len(examples)})")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
