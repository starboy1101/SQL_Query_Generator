.PHONY: install demo run test lint format docker

install:
	python -m pip install -e ".[dev]"

demo:
	python scripts/seed_demo_db.py

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check .
	mypy app

format:
	ruff format .
	ruff check --fix .

docker:
	docker compose up --build
