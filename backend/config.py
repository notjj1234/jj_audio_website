"""Backend configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATT_", env_file=".env")

    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: str = "./data"
    cors_origins: str = "*"


settings = Settings()
