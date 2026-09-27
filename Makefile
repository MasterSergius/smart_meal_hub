.DEFAULT_GOAL := help
COMPOSE = docker compose
APP_SERVICE = api
DB_SERVICE = db

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' | sort

# ── Local (uv) ────────────────────────────────────────────────────────────────

.PHONY: lock
lock: ## Generate / refresh uv.lock (commit this file)
	uv lock

.PHONY: install
install: ## Install all dependencies (incl. dev) via uv
	uv sync

.PHONY: install-prod
install-prod: ## Install production dependencies only
	uv sync --no-dev

.PHONY: test
test: ## Run all tests locally
	uv run pytest

.PHONY: test-v
test-v: ## Run all tests locally (verbose)
	uv run pytest -v

.PHONY: test-cov
test-cov: ## Run tests locally with coverage report
	uv run pytest --cov=app --cov-report=term-missing

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

.PHONY: env
env: ## Copy .env.example to .env if .env does not exist
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env from .env.example")

.PHONY: clean
clean: ## Remove __pycache__, .pytest_cache, .mypy_cache, .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

# ── Docker ────────────────────────────────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build Docker images
	$(COMPOSE) build

.PHONY: docker-rebuild
docker-rebuild: ## Force-rebuild Docker images without cache
	$(COMPOSE) build --no-cache

.PHONY: docker-run
docker-run: ## Start all services in the background (db + migrate + api)
	$(COMPOSE) up -d

.PHONY: docker-run-fg
docker-run-fg: ## Start all services in the foreground
	$(COMPOSE) up

.PHONY: docker-stop
docker-stop: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) down

.PHONY: docker-reset
docker-reset: ## Stop containers and DELETE volumes (full reset)
	$(COMPOSE) down -v

.PHONY: docker-logs
docker-logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: docker-logs-api
docker-logs-api: ## Tail logs from the API service only
	$(COMPOSE) logs -f $(APP_SERVICE)

.PHONY: docker-migrate
docker-migrate: ## Run Alembic migrations inside Docker
	$(COMPOSE) run --rm migrate

.PHONY: docker-migrate-down
docker-migrate-down: ## Roll back one Alembic revision inside Docker
	$(COMPOSE) run --rm \
		-e DATABASE_URL=postgresql+asyncpg://smarthub:smarthub@db:5432/smarthub \
		-e JWT_SECRET=dev \
		api uv run alembic downgrade -1

.PHONY: docker-migration
docker-migration: ## Generate a new migration — usage: make docker-migration MSG="add users table"
	$(COMPOSE) run --rm \
		-e DATABASE_URL=postgresql+asyncpg://smarthub:smarthub@db:5432/smarthub \
		-e JWT_SECRET=dev \
		api uv run alembic revision --autogenerate -m "$(MSG)"

.PHONY: docker-test
docker-test: ## Run tests inside Docker (against the Docker DB)
	$(COMPOSE) run --rm test

.PHONY: docker-seed
docker-seed: ## Seed the Docker DB with demo user and sample recipes
	$(COMPOSE) run --rm migrate
	$(COMPOSE) run --rm \
		-e DATABASE_URL=postgresql+asyncpg://smarthub:smarthub@db:5432/smarthub \
		api uv run python scripts/seed.py

.PHONY: docker-shell
docker-shell: ## Open a bash shell in the running API container
	$(COMPOSE) exec $(APP_SERVICE) /bin/bash

.PHONY: docker-shell-db
docker-shell-db: ## Open psql in the running DB container
	$(COMPOSE) exec $(DB_SERVICE) psql -U smarthub -d smarthub
