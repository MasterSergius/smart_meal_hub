# Changelog

All notable changes to SmartMeal Hub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-09-27

### Added

#### Auth
- `POST /api/v1/auth/register` — user registration with bcrypt password hashing
- `POST /api/v1/auth/login` — JWT authentication (HS256, 24h expiry)
- `GET /api/v1/auth/me` — authenticated user profile

#### Recipes
- `POST /api/v1/recipes` — create a recipe (authenticated users only)
- `GET /api/v1/recipes/{id}` — fetch a single recipe (public)
- `DELETE /api/v1/recipes/{id}` — delete a recipe (author only)
- `GET /api/v1/recipes/search` — search and filter recipes (public)
  - Full-text search on title and description (`q`)
  - Filter by diet tags with AND logic (`diet_tags`)
  - Filter by cuisine (`cuisine`)
  - Filter by max total time (`max_total_time`)
  - Filter by minimum rating (`min_rating`)
  - Pagination (`page`, `limit`)

#### Ratings
- `POST /api/v1/recipes/{id}/ratings` — rate a recipe 1–5 stars (upsert semantics)
  - Authors cannot rate their own recipes
  - `avg_rating` and `rating_count` recalculated atomically on every write

#### Infrastructure
- FastAPI + SQLAlchemy 2.x async + asyncpg + PostgreSQL 16
- Alembic migrations (async-aware)
- Docker Compose stack: `db → migrate → api` with health checks
- `uv` for dependency management (`pyproject.toml`)
- Makefile with targets for local dev, Docker, testing, linting, seeding
- Seed script with 5 sample recipes and a demo user
- 21 automated tests covering all endpoints (happy path + error cases)
