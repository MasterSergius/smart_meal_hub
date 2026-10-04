# Changelog

All notable changes to SmartMeal Hub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.1] - 2026-10-04

### Added
- `make clean-pyc`: removes `*.pyc`, `*.pyo`, `*.pyd`, `*~` and `__pycache__/` (skips `.venv`);
  `make clean` now runs it too
- Docstrings for all functions, methods and models

### Fixed
- Ratings: concurrent ratings of the same recipe could store a wrong `avg_rating` / `rating_count`
  (the recipe row is now locked with `SELECT ... FOR UPDATE` while the aggregate is recomputed)
- Ratings: a double-submitted first rating could hit the unique constraint and return 500
  (the write is now an atomic `INSERT ... ON CONFLICT DO UPDATE`)
- Recipes: over-long titles, cuisines or diet tags and out-of-range servings or times returned 500
  from Postgres; they are now rejected with 422
- Search: `%` and `_` in `q` were treated as wildcards; they are now matched literally
- Search: negative `max_total_time` and `min_rating` outside 0–5 now return 422
- Auth: over-long `display_name` returned 500; it now returns 422

### Changed
- Services raise domain exceptions (`app/exceptions.py`) that are mapped to HTTP responses in
  `app/main.py`; unexpected database errors are logged and return a generic 500
- Password length is validated in the `UserRegister` schema (422 with pydantic's error format)
- `avg_rating` in rating responses is rounded to 2 decimals, matching the stored value

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
