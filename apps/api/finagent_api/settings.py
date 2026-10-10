"""Application configuration.

All secrets come from the environment. Provider credentials are read here and never
returned by any endpoint — the API reports provider *availability*, not keys.
"""

from __future__ import annotations

import functools
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ---------------------------------------------------------------- product
    product_name: str = Field(default="FINAGENT LAB")
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    web_origin: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ---------------------------------------------------------------- security
    secret_key: str = Field(
        default="dev-only-insecure-secret-change-me",
        min_length=16,
        description="Signs sessions and derives the secret-encryption key.",
    )
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    password_min_length: int = 12
    bcrypt_rounds: int = 12
    require_mfa_for_admins: bool = False

    # ---------------------------------------------------------------- database
    database_url: str = Field(default="postgresql+psycopg://finagent:finagent@localhost:5432/finagent")
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ------------------------------------------------------------------- jobs
    job_backend: Literal["inline", "celery"] = "inline"
    redis_url: str = "redis://localhost:6379/0"
    celery_task_time_limit: int = 900

    # --------------------------------------------------------------- providers
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    alpha_vantage_api_key: str | None = None
    polygon_api_key: str | None = None
    #: EDGAR requires a contact string; without it the SEC provider is unavailable.
    sec_user_agent: str | None = None
    enable_demo_providers: bool = True
    default_model: str | None = None
    judge_model: str | None = None
    embedding_provider: Literal["auto", "openai", "deterministic"] = "auto"

    # --------------------------------------------------------------- execution
    agent_max_steps: int = 8
    agent_timeout_seconds: int = 300
    sandbox_timeout_seconds: int = 20
    sandbox_memory_mb: int = 512
    sandbox_cpu_seconds: int = 15
    max_upload_bytes: int = 100 * 1024 * 1024

    # ------------------------------------------------------------ rate limits
    rate_limit_enabled: bool = True
    rate_limit_per_user_per_minute: int = 240
    rate_limit_per_workspace_per_minute: int = 600
    rate_limit_per_api_key_per_minute: int = 120
    rate_limit_expensive_per_minute: int = 20

    # ---------------------------------------------------------------- storage
    storage_dir: str = "./storage"

    # ---------------------------------------------------------------- logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    # ---------------------------------------------------------------- billing
    default_plan: str = "trial"
    trial_research_run_limit: int = 100
    trial_evaluation_limit: int = 200

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def provider_status_summary(self) -> dict[str, bool]:
        """Which credentials are configured. Booleans only — never values."""
        return {
            "openai": bool(self.openai_api_key),
            "anthropic": bool(self.anthropic_api_key),
            "google": bool(self.google_api_key),
            "alpha_vantage": bool(self.alpha_vantage_api_key),
            "polygon": bool(self.polygon_api_key),
            "sec_edgar": bool(self.sec_user_agent),
            "demo": self.enable_demo_providers,
        }

    def insecure_defaults(self) -> list[str]:
        """Configuration that must not ship to production."""
        problems: list[str] = []
        if self.secret_key.startswith("dev-only"):
            problems.append("SECRET_KEY is still the development default.")
        if self.debug:
            problems.append("DEBUG is enabled.")
        if "sqlite" in self.database_url:
            problems.append("DATABASE_URL points at SQLite.")
        return problems


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
