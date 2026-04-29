from functools import lru_cache
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    api_v1_prefix: str = Field(default="/api/v1")
    secret_key: str = Field(default="change_me")
    access_token_expire_minutes: int = Field(default=60)
    cors_origins: List[AnyHttpUrl] | List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])  # type: ignore[assignment]

    # URLs
    frontend_url: AnyHttpUrl | str = Field(default="http://localhost:5173")
    database_url: str = Field(default="postgresql+psycopg2://fdms:fdms_password@localhost:5432/fdms")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Admin (bootstrap)
    admin_email: str = Field(default="admin@example.com")
    admin_password: str = Field(default="Nitrozox")

    # Email (mock/sandbox)
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = Field(default="no-reply@example.com")

    # External API mock/sandbox endpoints
    pitchbook_base_url: AnyHttpUrl | str = Field(default="https://sandbox.api.pitchbook.com")
    capiq_base_url: AnyHttpUrl | str = Field(default="https://sandbox.api.spglobal.com")
    factset_base_url: AnyHttpUrl | str = Field(default="https://sandbox.api.factset.com")
    axial_base_url: AnyHttpUrl | str = Field(default="https://sandbox.api.axial.net")
    grata_base_url: AnyHttpUrl | str = Field(default="https://sandbox.api.grata.com")
    sec_edgar_base_url: AnyHttpUrl | str = Field(default="https://data.sec.gov")
    scraper_user_agent: str = Field(default="FDMSBot/1.0 (+https://example.com)")

    # Spreadsheet + workflow
    spreadsheet_mode: str = Field(default="excel")  # "google" | "excel"
    google_sheet_id: str | None = None
    excel_path: str = Field(default="data/sample_sheet.csv")
    worksheet_name: str = Field(default="Sheet1")
    freshness_days: int = Field(default=365)
    outreach_cadence_days: int = Field(default=14)
    dry_run: bool = Field(default=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


