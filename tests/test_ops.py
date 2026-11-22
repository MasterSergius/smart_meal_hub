"""Deployment readiness — spec v0.2.0 §9 (OPS-1 … OPS-4)."""

import json
import logging
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import Settings
from app.database import get_db
from app.logging_setup import JsonFormatter
from app.main import app

STRONG_SECRET = "x" * 32


async def test_healthz(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_ops1_readyz_ok(client: AsyncClient) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_ops1_readyz_unavailable_when_db_fails() -> None:
    class BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise ConnectionRefusedError("database is down")

    async def broken_db() -> AsyncGenerator[BrokenSession, None]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/readyz")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json() == {"status": "unavailable"}


def _settings(**kwargs: str) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, database_url="postgresql+asyncpg://x/y", **kwargs
    )


@pytest.mark.parametrize("secret", ["change-me-in-production", "seed-secret", "short"])
def test_ops2_prod_rejects_weak_secret(secret: str) -> None:
    with pytest.raises(ValidationError):
        _settings(app_env="prod", jwt_secret=secret)


def test_ops2_prod_accepts_strong_secret_and_dev_accepts_any() -> None:
    assert _settings(app_env="prod", jwt_secret=STRONG_SECRET).app_env == "prod"
    assert _settings(app_env="dev", jwt_secret="change-me-in-production").app_env == "dev"


def test_ops2_app_env_defaults_to_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    assert _settings(jwt_secret=STRONG_SECRET).app_env == "prod"


def test_ops3_cors_origin_list() -> None:
    origins = " https://a.example, ,https://b.example"
    s = _settings(app_env="dev", jwt_secret="dev", cors_origins=origins)
    assert s.cors_origin_list == ["https://a.example", "https://b.example"]
    assert _settings(app_env="dev", jwt_secret="dev").cors_origin_list == []


def test_ops4_json_log_line_has_request_fields() -> None:
    record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "GET /x 200", None, None)
    record.method, record.path, record.status, record.duration_ms = "GET", "/x", 200, 1.5
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "INFO" and entry["logger"] == "app.request"
    assert entry["message"] == "GET /x 200"
    assert (entry["method"], entry["path"], entry["status"], entry["duration_ms"]) == (
        "GET",
        "/x",
        200,
        1.5,
    )
