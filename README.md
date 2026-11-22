# smart_meal_hub
Smart Meal Planning &amp; Grocery Hub ("SmartMeal Hub")

A FastAPI service for a recipe catalog and weekly meal planning: users save their
diets and ingredients to avoid, generate a 7-day menu, swap single dishes and rescale
portions for the number of people.

- Requirements: [`docs/project_requirements.md`](docs/project_requirements.md)
- Specs: [v0.1.0](docs/spec_v0.1.0.md) (recipe catalog), [v0.2.0](docs/spec_v0.2.0.md) (menu generation)
- Changes: [`CHANGELOG.md`](CHANGELOG.md)

## Quick start (Docker)

```bash
make docker-run      # db + migrations + API on http://localhost:8000
make docker-seed     # demo user chef@example.com / password123 and 39 recipes
make docker-test     # test suite against the Docker database
```

API docs: http://localhost:8000/docs

## Local development (uv)

```bash
make env             # creates .env from .env.example (APP_ENV=dev)
make install
make test            # needs PostgreSQL with a smarthub_test database
make lint
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | | `postgresql+asyncpg://user:pass@host:5432/db` |
| `JWT_SECRET` | yes | | Token signing key; in `prod` at least 32 characters and not a placeholder |
| `JWT_EXPIRE_HOURS` | no | `24` | Token lifetime |
| `APP_ENV` | no | `prod` | `dev` allows placeholder secrets |
| `CORS_ORIGINS` | no | empty | Comma-separated allowed origins; empty disables CORS |
| `LOG_FORMAT` | no | `text` (`json` in the prod image) | `json` writes one JSON object per line |

## Production image

```bash
make docker-build-prod                 # smart-meal-hub:<version>, target "prod"
docker run --rm -e DATABASE_URL=... -e JWT_SECRET=... smart-meal-hub:0.2.0 \
    alembic upgrade head               # run migrations as a one-off task
```

The image runs as a non-root user and listens on port 8000. Probes: `GET /healthz`
(liveness, no database) and `GET /readyz` (readiness, checks the database).
