from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Xinghuo Fire Agent Backend"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"

    host: str = "0.0.0.0"
    port: int = 8200

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    data_dir: Path | None = None
    database_url: str | None = None
    database_echo: bool = False

    cors_origins: list[str] = ["*"]

    llm_provider: str = "zhipu"
    llm_model: str = "glm-4.6"
    llm_api_key: str = ""
    llm_base_url: str = ""
    forefire_api_url: str = "http://127.0.0.1:5000"
    forefire_timeout_seconds: float = 300.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "*":
                return ["*"]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir or (self.project_root / "data")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.resolved_data_dir / "fire_agent_backend.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
