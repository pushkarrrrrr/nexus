import os
import sys
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_dir() -> Path:
    if "NEXUS_DATA_DIR" in os.environ:
        return Path(os.environ["NEXUS_DATA_DIR"]).expanduser()
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "NEXUS"
        elif sys.platform == "win32":
            return Path(os.environ.get("APPDATA", "~")) / "NEXUS"
        else:
            return Path.home() / ".local" / "share" / "nexus"
    return Path(".nexus")


def get_default_sqlite_url() -> str:
    data_dir = get_default_data_dir()
    db_file = data_dir / "nexus.db"
    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


class NexusSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    nexus_env: str = Field(default="development", alias="NEXUS_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_workers: int = Field(default=1, alias="API_WORKERS")

    cors_origins: list[str] | str = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ],
        alias="CORS_ORIGINS",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/nexus",
        alias="DATABASE_URL",
    )
    sqlite_fallback_url: str = Field(
        default_factory=get_default_sqlite_url,
        alias="SQLITE_FALLBACK_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    default_ai_provider: str = Field(default="openai", alias="DEFAULT_AI_PROVIDER")
    default_fallback_provider: str | None = Field(default=None, alias="DEFAULT_FALLBACK_PROVIDER")
    ai_request_timeout_sec: float = Field(default=60.0, alias="AI_REQUEST_TIMEOUT_SEC")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    embedding_dimension: int = Field(default=1536, alias="EMBEDDING_DIMENSION")

    encryption_key: str = Field(
        default="nexus-development-secret-key-change-in-production",
        alias="ENCRYPTION_KEY",
    )
    integration_encryption_key: str = Field(
        default="nexus-integration-default-aes256-gcm-key-32b!",
        alias="INTEGRATION_ENCRYPTION_KEY",
    )
    session_expiry_hours: int = Field(default=24, alias="SESSION_EXPIRY_HOURS")
    auto_approve_low_risk: bool = Field(default=True, alias="AUTO_APPROVE_LOW_RISK")
    nexus_demo_mode: bool = Field(
        default=False,
        alias="NEXUS_DEMO_MODE",
        description="When True in non-production environments, allows demo session fallback without credentials for live presentation walkthroughs.",
    )

    @field_validator("sqlite_fallback_url", mode="before")
    @classmethod
    def resolve_sqlite_fallback_url(cls, v):
        if os.environ.get("NEXUS_DATA_DIR"):
            data_dir = Path(os.environ["NEXUS_DATA_DIR"]).expanduser()
            return f"sqlite+aiosqlite:///{(data_dir / 'nexus.db').as_posix()}"
        return v or get_default_sqlite_url()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


# Cached singleton
_settings: NexusSettings | None = None


def get_settings() -> NexusSettings:
    global _settings
    if _settings is None:
        _settings = NexusSettings()
    return _settings
