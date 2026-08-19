# Public deployment guide

The recommended first deployment is one Docker-based Render web service. The Dockerfile builds the React application,
copies its static output into the Python image, seeds synthetic SQLite data, and starts one FastAPI worker. UI and API
share an origin, so the browser does not need a backend secret and CORS is not involved in normal requests.

## 1. Verify locally

```powershell
Copy-Item .env.example .env
python -m pip install -e ".[dev]"
python scripts\seed_demo_db.py
Set-Location frontend
npm install
npm test
npm run build
Set-Location ..
uvicorn app.main:app --reload
```

Open `http://localhost:8000`, run each example question, and confirm `http://localhost:8000/health/ready` returns an
`ok` status. If Docker is installed, also run `docker compose up --build` and repeat the smoke test.

## 2. Push the repository

Create a private or public GitHub repository and push this project. Do not force-add `.env`, model adapters, database
credentials, or customer data. The checked-in `.gitignore` already excludes local secrets, generated databases, frontend
dependencies, and model artifacts.

## 3. Create the Render service

1. Sign in to Render and connect the GitHub account containing the repository.
2. Select **New → Blueprint**.
3. Choose this repository. Render detects the root `render.yaml` file.
4. Review the `sql-pilot` web service and apply the Blueprint.
5. Wait for the Docker build and `/health/ready` check to succeed.
6. Open the assigned `https://<service-name>.onrender.com` URL.

The included Blueprint intentionally configures:

- synthetic, image-seeded SQLite data;
- one worker, avoiding in-memory limiter and Prometheus multiprocess inconsistencies;
- generated-query execution enabled, with direct SQL execution disabled;
- an explicit four-table allowlist, views disabled, a 100-row hard cap, and five-second query timeout;
- ten generation requests per minute per client on the application instance;
- public metrics disabled;
- the limited heuristic backend, so the initial image remains CPU-friendly.

Render's free web service may sleep when idle, so the first request after inactivity can be slower. Upgrade the instance
if consistent availability is important.

## 4. Production smoke test

Replace the URL below with the assigned hostname:

```powershell
$baseUrl = "https://your-service.onrender.com"

Invoke-RestMethod "$baseUrl/health/ready"
Invoke-RestMethod "$baseUrl/api/v1/schema"

$body = @{
    question = "How many customers are there?"
    execute = $true
    max_rows = 50
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "$baseUrl/api/v1/queries/generate" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

Also verify that `POST /api/v1/queries/execute` returns `403`, `/metrics` returns `404`, unknown table queries are
rejected, and repeated generation eventually produces `429` with `Retry-After`.

## 5. Connect the Hugging Face Space model

The repository contains a reproducible Gradio Space under `deploy/huggingface-space`. It exposes one named endpoint,
`/generate`, that accepts the complete schema-aware prompt and a token limit and returns one SQL string.

1. Open `https://huggingface.co/spaces/omkar1804/sql-pilot-model`.
2. Replace the Space `README.md`, `requirements.txt`, and `app.py` with the files from
   `deploy/huggingface-space` and commit them in the Space UI.
3. In **Settings â†’ Hardware**, select **ZeroGPU** if it is available for the account.
4. Wait for the Space status to become **Running**.
5. From this repository's activated virtual environment, run `python test_space.py`. A successful result is a normal
   statement such as `SELECT COUNT(*) FROM customers;` with no byte-level token markers, Markdown, or trailing noise.
6. Configure the Render web service with the following server-side environment variables and redeploy it:

```dotenv
LLM_BACKEND=huggingface_space
HF_SPACE_ID=omkar1804/sql-pilot-model
HF_SPACE_API_NAME=/generate
HF_SPACE_TOKEN=
MODEL_NAME_OR_PATH=prem-research/prem-1B-SQL
MODEL_REQUEST_TIMEOUT_SECONDS=180
MODEL_MAX_INPUT_TOKENS=3072
MODEL_MAX_NEW_TOKENS=128
MODEL_WARMUP_ON_START=false
```

Use only the `owner/space-name` value for `HF_SPACE_ID`, not the `.hf.space` URL. `HF_SPACE_TOKEN` is optional for a
public Space. When configured, it must be a Render secret and must never be prefixed with `VITE_`. The backend bounds
both HTTP operations and total queue/inference time, rejects malformed or oversized model responses, and still sends
every valid-looking response through SQLGlot and the table allowlist before optional execution.

Free ZeroGPU is intended for low-traffic demonstrations. Cold starts, queues, and per-account GPU quota mean it cannot
support a guaranteed latency or daily-throughput claim. Keep the heuristic backend available for local smoke tests.

## 6. Dedicated model-server alternative

Do not attempt to load CodeLlama-7B inside a small CPU web service. Host the fine-tuned adapter on a GPU inference
service that supports an OpenAI-compatible chat endpoint, then set these server-side Render environment variables:

```dotenv
LLM_BACKEND=openai_compatible
MODEL_API_BASE_URL=https://your-private-model-service
MODEL_NAME_OR_PATH=codellama-text-to-sql
MODEL_API_KEY=<secret configured in the Render dashboard>
MODEL_REQUEST_TIMEOUT_SECONDS=45
```

Never prefix model credentials or API keys with `VITE_`; Vite embeds those values in the public browser bundle.

## 7. Before sharing broadly

The included in-process limiter is appropriate for a small single-instance portfolio demo, not a distributed abuse
boundary. Put the service behind Cloudflare or another gateway and configure endpoint/IP rate limits, body-size limits,
bot protection, and a daily inference-budget circuit breaker. For multiple application replicas, move counters and
concurrency limits to a shared Redis-compatible service.

Keep the public database synthetic. If you later add accounts, feedback, history, or mutable data, migrate those records
to managed PostgreSQL and retain a dedicated read-only role for generated SQL.

## Separate frontend hosting

The frontend can be deployed as a static site by setting `VITE_API_BASE_URL` to the public API origin, adding that exact
HTTPS origin to `CORS_ORIGINS`, and rebuilding. This variable may contain a URL, but never a shared API key. If the backend
must remain API-key protected, place a server-side BFF or edge function between the browser and FastAPI so the secret is
injected outside the browser.

## Custom domain

Add the desired domain in the Render service settings, create the DNS records Render supplies, and wait for managed TLS
to activate. Because the application uses same-origin relative API paths, no frontend rebuild or CORS change is needed.
