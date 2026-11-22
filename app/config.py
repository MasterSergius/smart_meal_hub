from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# OPS-2: secrets that ship in this repo (compose, tests, seed) and must never reach prod.
PLACEHOLDER_SECRETS = frozenset(
    {"change-me-in-production", "seed-secret", "test-secret-key-not-for-production", "dev"}
)
MIN_PROD_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application settings, read from environment variables (or ``.env``) at import time.

    Field names map to env vars case-insensitively, so ``DATABASE_URL`` sets
    ``database_url``. Fields without defaults are required: the app will not start
    without them.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_hours: int = 24

    app_env: Literal["dev", "prod"] = "prod"
    cors_origins: str = ""  # comma-separated; empty disables CORS (OPS-3)
    log_format: Literal["text", "json"] = "text"  # OPS-4

    @model_validator(mode="after")
    def reject_weak_secret_in_prod(self) -> "Settings":
        """OPS-2: refuse to start in prod with a placeholder or short ``JWT_SECRET``."""
        if self.app_env == "prod" and (
            self.jwt_secret in PLACEHOLDER_SECRETS
            or len(self.jwt_secret) < MIN_PROD_SECRET_LENGTH
        ):
            raise ValueError(
                f"JWT_SECRET must be a non-placeholder secret of at least "
                f"{MIN_PROD_SECRET_LENGTH} characters when APP_ENV=prod"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """``CORS_ORIGINS`` split on commas, blanks removed."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
