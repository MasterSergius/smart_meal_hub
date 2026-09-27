.DEFAULT_GOAL := help
COMPOSE = docker compose
APP_SERVICE = api
DB_SERVICE = db

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' | sort

# ── Local dev (uv) ────────────────────────────────────────────────────────────

.PHONY: lock
lock: ## Generate / refresh uv.lock (commit this file)
	uv lock

.PHONY: install
install: ## Install all dependencies (incl. dev) via uv
	uv sync

.PHONY: install-prod
install-prod: ## Install production dependencies only
	uv sync --no-dev

.PHONY: run
run: ## Run the API locally (requires .env)
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: migrate
migrate: ## Run Alembic migrations (local DB via .env)
	uv run alembic upgrade head

.PHONY: migrate-down
migrate-down: ## Roll back one Alembic revision
	uv run alembic downgrade -1

.PHONY: migration
migration: ## Generate a new migration — usage: make migration MSG="add users table"
	uv run alembic revision --autogenerate -m "$(MSG)"

# ── Testing ───────────────────────────────────────────────────────────────────

.PHONY: test
test: ## Run all tests
	uv run pytest

.PHONY: test-v
test-v: ## Run all tests (verbose)
	uv run pytest -v

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	uv run pytest --cov=app --cov-report=term-missing

# ── Docker ────────────────────────────────────────────────────────────────────

.PHONY: build
build: ## Build Docker images
	$(COMPOSE) build

.PHONY: rebuild
rebuild: ## Force-rebuild images without cache
	$(COMPOSE) build --no-cache

.PHONY: up
up: ## Start all services (db + migrate + api)
	$(COMPOSE) up

.PHONY: up-d
up-d: ## Start all services in the background
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) down

.PHONY: down-v
down-v: ## Stop containers and DELETE volumes (full reset)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: logs-api
logs-api: ## Tail logs from the API service only
	$(COMPOSE) logs -f $(APP_SERVICE)

.PHONY: docker-migrate
docker-migrate: ## Run migrations inside Docker
	$(COMPOSE) run --rm migrate

.PHONY: docker-shell
docker-shell: ## Open a shell in the running API container
	$(COMPOSE) exec $(APP_SERVICE) /bin/bash

.PHONY: docker-shell-db
docker-shell-db: ## Open psql in the running DB container
	$(COMPOSE) exec $(DB_SERVICE) psql -U smarthub -d smarthub

.PHONY: docker-test
docker-test: ## Build and run tests inside Docker (against the Docker DB)
	$(COMPOSE) run --rm test

# ── Code quality ──────────────────────────────────────────────────────────────

.PHONY: lint
lint: ## Run ruff linter
	uv run ruff check app tests

.PHONY: fmt
fmt: ## Auto-format code with ruff
	uv run ruff format app tests

.PHONY: typecheck
typecheck: ## Run mypy type checker
	uv run mypy app

.PHONY: check
check: lint typecheck ## Run lint + type checks

# ── Utilities ─────────────────────────────────────────────────────────────────

.PHONY: env
env: ## Copy .env.example to .env if .env does not exist
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env from .env.example")

.PHONY: clean
clean: ## Remove __pycache__, .pytest_cache, .mypy_cache, .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
