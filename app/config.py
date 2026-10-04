from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
