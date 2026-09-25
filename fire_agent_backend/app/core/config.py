from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    landscape_data_dir: Path | None = None
    visual_output_dir: Path | None = None
    database_url: str | None = None
    database_echo: bool = False

    cors_origins: list[str] = ["*"]

    llm_provider: str = "zhipu"
    llm_model: str = "glm-4.6"
    llm_api_key: str = ""
    llm_base_url: str = ""
    qwen_vl_api_key: SecretStr = SecretStr("")
    qwen_vl_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_vl_model: str = "qwen3-vl-plus"
    qwen_vl_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    qwen_vl_max_attempts: int = Field(default=2, ge=1, le=3)
    qwen_vl_max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    visual_auto_confirm_screened_candidates: bool = True
    visual_auto_confirm_min_confidence: float = Field(default=0.70, ge=0, le=1)
    professional_detector_api_url: str = "http://visual-detector-api:8300"
    professional_detector_timeout_seconds: float = Field(default=180.0, gt=0, le=300)
    professional_detector_default_confidence: float = Field(default=0.40, ge=0.05, le=0.95)
    forefire_api_url: str = "http://127.0.0.1:5000"
    forefire_timeout_seconds: float = 300.0

    # Realtime candidate hotspot ingestion. Keep the key in .env only.
    firms_map_key: str = ""
    firms_realtime_days: int = 2
    realtime_retention_count: int = 3
    realtime_http_timeout_seconds: float = 45.0
    geocoder_base_url: str = "https://nominatim.openstreetmap.org"
    geocoder_timeout_seconds: float = Field(default=20.0, gt=0, le=60)

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
    def resolved_landscape_data_dir(self) -> Path:
        return self.landscape_data_dir or (self.project_root.parent / "environment")

    @property
    def resolved_visual_output_dir(self) -> Path:
        return self.visual_output_dir or (
            self.resolved_data_dir / "processed" / "visual_verification"
        )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.resolved_data_dir / "fire_agent_backend.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
