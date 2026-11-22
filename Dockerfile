# Targets:
#   dev  — all dependencies incl. pytest/ruff; used by docker-compose with the source bind-mounted
#   prod — runtime dependencies only, non-root, no build tools (default; this is what goes to AWS)
#
# The virtualenv lives in /opt/venv rather than /app/.venv, so bind-mounting the
# source over /app in development does not hide it.
#
# Works with both BuildKit and the legacy builder (no RUN --mount).

ARG PYTHON_IMAGE=python:3.12-slim

# ── Shared base ───────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS base
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ── Development image ─────────────────────────────────────────────────────────
FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Production build stage ────────────────────────────────────────────────────
FROM base AS builder
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Production image ──────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS prod
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=prod \
    LOG_FORMAT=json
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]
# Request logging comes from the app (OPS-4), so uvicorn's own access log is off.
# --proxy-headers: the app runs behind a load balancer that sets X-Forwarded-*.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
