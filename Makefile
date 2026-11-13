.PHONY: install lint format test run run-web coverage

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests
	ruff format --check src tests

format:
	ruff format src tests

test:
	pytest

coverage:
	pytest --cov=src/jobpilot --cov-report=term-missing

run:
	uvicorn jobpilot.chat.webhook:create_app --factory --reload --port 8000

run-web:
	uvicorn jobpilot.web.app:create_web_app --factory --reload --port 8001
