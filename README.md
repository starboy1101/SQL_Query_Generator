# LLM-Powered SQL Query Generator

A production-oriented, schema-aware text-to-SQL service built with FastAPI, SQLAlchemy, SQLGlot, CodeLlama-7B, and
QLoRA. It converts natural-language questions into SQL, treats all model output as untrusted, validates it against the
live database schema, and can optionally execute the resulting read-only query.

The repository includes the serving API, a dependency-free development backend, local and remote CodeLlama inference,
QLoRA training, Spider conversion and execution evaluation, metrics, containers, and automated tests. Model weights and
licensed datasets are intentionally not committed.

## Architecture

```text
Natural language request
         |
         v
Schema introspection -> prompt builder -> CodeLlama / vLLM
                                            |
                                            v
                              SQL extraction and repair
                                            |
                                            v
                              SQLGlot safety validator
                              - one SELECT statement
                              - table allowlist
                              - dangerous-op denial
                              - server row cap
                                            |
                              +-------------+-------------+
                              |                           |
                         SQL response             read-only execution
                                                        |
                                                        v
                                               rows + latency metrics
```

The model never receives database credentials or row data. It sees only allowlisted table/column metadata. The database
layer is a second safety boundary and should always connect with a read-only database role in production.

## What is included

- Versioned FastAPI endpoints with OpenAPI documentation in non-production environments.
- SQLite, PostgreSQL, MySQL, SQL Server, and Oracle SQL generation dialects.
- Schema discovery with primary/foreign-key context and an expiring cache.
- Local CodeLlama inference with a PEFT/QLoRA adapter, plus an OpenAI-compatible vLLM/TGI backend.
- AST-based SQL validation, single-statement enforcement, allowlisted tables, function denial, row caps, and timeouts.
- Optional API-key authentication, CORS policy, request correlation IDs, JSON logs, health probes, and Prometheus metrics.
- Reproducible QLoRA training and Spider execution-accuracy evaluation scripts.
- Pytest safety/API coverage, Ruff checks, CI, Docker, and Docker Compose.

## Quick start

Python 3.10-3.13 is supported.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env
python scripts/seed_demo_db.py
uvicorn app.main:app --reload
```

On Windows, replace `cp` with `Copy-Item .env.example .env`. Then open `http://localhost:8000/docs` or run:

```bash
curl -X POST http://localhost:8000/api/v1/queries/generate \
  -H "Content-Type: application/json" \
  -d '{"question":"How many customers are there?","execute":true}'
```

The default `heuristic` backend is deliberately small and supports smoke tests such as listing, counting, and basic
aggregates. Use one of the CodeLlama backends for real text-to-SQL behavior.

You can also start the complete demo with `docker compose up --build`.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/queries/generate` | Generate, parse, and validate SQL; optionally execute it |
| `POST` | `/api/v1/queries/execute` | Validate and execute supplied read-only SQL |
| `GET` | `/api/v1/schema` | Inspect the exact schema visible to the model |
| `GET` | `/health/live` | Process liveness probe |
| `GET` | `/health/ready` | Database readiness probe |
| `GET` | `/metrics` | Prometheus metrics |

When `API_KEY` is configured, send it in the `X-API-Key` header for all `/api/v1` routes. Query execution is independently
controlled by `ALLOW_QUERY_EXECUTION` and defaults to `false` unless overridden in `.env`.

Example response:

```json
{
  "request_id": "3cb77d13-1334-42cf-91f8-13b86dafb893",
  "question": "How many customers are there?",
  "sql": "SELECT\n  COUNT(*) AS count\nFROM \"customers\"\nLIMIT 100",
  "dialect": "sqlite",
  "model": "heuristic-development-backend",
  "validation": {"read_only": true, "tables": ["customers"], "applied_row_limit": 100},
  "execution": {"columns": ["count"], "rows": [{"count": 4}], "row_count": 1, "elapsed_ms": 0.39},
  "generation_ms": 3.18
}
```

## Model serving modes

### Local Hugging Face + QLoRA

Install the ML dependencies and point the app at the adapter produced by the training script:

```bash
python -m pip install -e ".[ml]"
export LLM_BACKEND=huggingface
export MODEL_NAME_OR_PATH=codellama/CodeLlama-7b-Instruct-hf
export ADAPTER_PATH=artifacts/codellama-text-to-sql-qlora
export MODEL_USE_4BIT=true
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Four-bit loading requires a supported CUDA environment. Keep `MODEL_WARMUP_ON_START=false` for lazy loading or enable it
when readiness should wait for model loading.

### Optimized remote inference

For higher throughput and sub-second latency targets, serve the base model and adapter using an OpenAI-compatible vLLM
deployment, then configure:

```dotenv
LLM_BACKEND=openai_compatible
MODEL_API_BASE_URL=http://model-server:8001
MODEL_NAME_OR_PATH=codellama-text-to-sql
MODEL_API_KEY=replace-me
```

Latency and throughput depend on GPU, prompt size, batching, quantization, network placement, and generated token count.
The API exposes measured request latency; production SLOs should be established from load tests on the actual hardware.

## QLoRA fine-tuning

Training data is JSONL with one record per pair:

```json
{"question":"List completed orders","schema":"TABLE orders (id INTEGER PK, status TEXT)","sql":"SELECT id FROM orders WHERE status = 'completed'","dialect":"sqlite"}
```

Convert the official Spider files into that format:

```bash
python scripts/prepare_spider_dataset.py \
  --input datasets/spider/train_spider.json \
  --database-dir datasets/spider/database \
  --output data/train_spider.jsonl
```

After assembling and deduplicating the intended 80K examples, run QLoRA on a CUDA host:

```bash
python scripts/train_qlora.py \
  --train-file data/train_80k.jsonl \
  --validation-file data/validation.jsonl \
  --output-dir artifacts/codellama-text-to-sql-qlora \
  --epochs 3 --batch-size 2 --gradient-accumulation-steps 16
```

The trainer uses NF4 four-bit quantization, double quantization, completion-only loss masking, gradient checkpointing,
LoRA attention adapters, deterministic seeding, validation loss, and best-checkpoint retention.

## Spider evaluation

Generate predictions with the adapter and calculate execution accuracy against read-only Spider databases:

```bash
python scripts/evaluate_spider.py \
  --examples datasets/spider/dev.json \
  --database-dir datasets/spider/database \
  --adapter artifacts/codellama-text-to-sql-qlora \
  --output artifacts/spider-results.json
```

For reproducible offline scoring, supply JSONL records containing `predicted_sql` with `--predictions`. The evaluator
records every prediction, validation/execution failure, numerator, denominator, and final execution accuracy.

The “79% Spider execution accuracy,” “500+ daily queries,” and “<900 ms latency” figures in the project brief are not
hard-coded or claimed as results of this source checkout. They must be backed by the generated evaluation report and
production telemetry for the exact checkpoint, dataset split, database, and hardware being presented.

## Production checklist

1. Create a dedicated database principal with `SELECT` access only to the required tables/views.
2. Set `ALLOWED_TABLES`, `API_KEY`, a specific CORS origin, and `APP_ENV=production` in a secrets manager.
3. Leave `ALLOW_QUERY_EXECUTION=false` unless returning data is an explicit product requirement.
4. Run the model in a separate GPU service and place both services on a private network.
5. Terminate TLS and apply distributed rate limits/body limits at the API gateway.
6. Scrape `/metrics`, centralize JSON logs, and alert on readiness, error rate, and latency percentiles.
7. Load-test with representative schemas and questions; canary every adapter/model change.
8. Retain evaluation artifacts and dataset/model versions for auditability.

## Validation

```bash
ruff check .
pytest --cov=app --cov-report=term-missing
mypy app
```

The most important negative tests cover write operations, multiple statements, unknown tables, cross-schema references,
dangerous functions, server-side limit clamping, execution policy, and stable error responses.

## Repository layout

```text
app/api/       HTTP routes and schemas
app/core/      settings, errors, logging, and metrics
app/db/        connection, schema introspection, SQL validation, execution
app/llm/       prompt, output extraction, local/remote/development backends
app/services/  generation, repair, validation, and execution workflow
scripts/       demo data, QLoRA training, Spider preparation/evaluation
tests/         API, prompt, and SQL safety tests
```
