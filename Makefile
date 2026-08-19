.PHONY: install demo run frontend frontend-build test lint format docker

install:
	python -m pip install -e ".[dev]"

demo:
	python scripts/seed_demo_db.py

run:
	uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

test:
	pytest --cov=app --cov-report=term-missing
	cd frontend && npm test

lint:
	ruff check .
	mypy app
	cd frontend && npm run build

format:
	ruff format .
	ruff check --fix .

docker:
	docker compose up --build
