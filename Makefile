.PHONY: help install dev test lint format migrate clean docker-up docker-down

help:  ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	poetry install

dev:  ## Run development server
	poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:  ## Run all tests
	poetry run pytest

test-unit:  ## Run unit tests only
	poetry run pytest tests/unit -v

test-integration:  ## Run integration tests only
	poetry run pytest tests/integration -v

test-smoke:  ## Run smoke tests only
	poetry run pytest tests/smoke -v

lint:  ## Run linting
	poetry run ruff check src tests
	poetry run mypy src

format:  ## Format code
	poetry run black src tests
	poetry run ruff check --fix src tests

migrate:  ## Run database migrations
	poetry run alembic upgrade head

migrate-create:  ## Create new migration (usage: make migrate-create MESSAGE="description")
	poetry run alembic revision --autogenerate -m "$(MESSAGE)"

clean:  ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov

docker-up:  ## Start Docker Compose stack
	docker compose -f docker/docker-compose.yml up -d

docker-down:  ## Stop Docker Compose stack
	docker compose -f docker/docker-compose.yml down

docker-logs:  ## View Docker Compose logs
	docker compose -f docker/docker-compose.yml logs -f

docker-rebuild:  ## Rebuild and restart Docker Compose
	docker compose -f docker/docker-compose.yml up -d --build
