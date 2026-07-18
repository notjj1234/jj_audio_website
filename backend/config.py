"""Backend configuration."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATT_", env_file=".env", extra="ignore")

    env: str = "development"  # development | production
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: str = "./data"

    # Comma-separated origins. Never use "*" with credentials.
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    secret_key: str = "dev-only-change-me"
    require_auth: bool = False
    bootstrap_admin_email: str = "admin@localhost"
    bootstrap_admin_password: str = "changeme"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    max_upload_mb: int = 50
    allow_youtube: bool = False
    rate_limit_upload: str = "10/minute"
    rate_limit_jobs: str = "20/minute"

    database_url: str = "sqlite:///./data/app.db"
    redis_url: str = "redis://localhost:6379/0"
    use_worker: bool = False  # False = in-process executor (dev); True = arq

    storage_backend: str = "local"  # local | s3
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "audio-tools"
    s3_region: str = "us-east-1"

    artifact_sign_ttl_sec: int = 600
    job_timeout_fast_sec: int = 1800
    job_timeout_balanced_sec: int = 3600
    job_timeout_high_sec: int = 7200
    job_timeout_extreme_sec: int = 14400
    default_isolate_quality: str = "fast"
    max_job_duration_sec: float = 300.0

    @field_validator("cors_origins")
    @classmethod
    def _no_star_with_credentials_hint(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.env == "production":
            if not self.secret_key or self.secret_key == "dev-only-change-me":
                raise ValueError("ATT_SECRET_KEY must be set to a strong value when ATT_ENV=production")
            if self.cors_origins.strip() == "*":
                raise ValueError("ATT_CORS_ORIGINS must not be '*' in production")
            if not self.require_auth:
                raise ValueError("ATT_REQUIRE_AUTH must be true in production")
        return self

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def job_timeout_for_quality(self, quality: str) -> int:
        return {
            "fast": self.job_timeout_fast_sec,
            "balanced": self.job_timeout_balanced_sec,
            "high": self.job_timeout_high_sec,
            "extreme": self.job_timeout_extreme_sec,
        }.get(quality, self.job_timeout_balanced_sec)


settings = Settings()
