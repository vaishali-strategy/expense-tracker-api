"""Settings, read from environment variables (and an optional .env file)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-only-secret-change-me-before-deploying-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://expense:expense@localhost:5432/expense_dev"
    secret_key: str = DEFAULT_SECRET
    access_token_minutes: int = 60
    bcrypt_rounds: int = 12  # password hashing cost; tests lower it so they run fast
    app_env: str = "development"  # "production" refuses to start with the default secret

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        # Hosting providers hand out "postgres://..." or "postgresql://..." URLs.
        # SQLAlchemy needs to be told which driver to use.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
