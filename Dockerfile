# syntax=docker/dockerfile:1
FROM node:24-alpine AS frontend-builder

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts/seed_demo_db.py ./scripts/seed_demo_db.py
RUN python -m pip install \
    --disable-pip-version-check \
    --retries 10 \
    --timeout 60 \
    .

COPY --from=frontend-builder /web/dist ./frontend/dist
RUN mkdir -p /app/data \
    && python scripts/seed_demo_db.py --path /app/data/demo.db \
    && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health/ready', timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers"]
