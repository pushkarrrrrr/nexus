from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default=["http://localhost:3000", "http://localhost:5173", "tauri://localhost"],
        alias="CORS_ORIGINS",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/nexus",
        alias="DATABASE_URL",
    )
    sqlite_fallback_url: str = Field(
        default="sqlite+aiosqlite:///./.nexus/nexus.db",
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

    encryption_key: str = Field(
        default="nexus-development-secret-key-change-in-production",
        alias="ENCRYPTION_KEY",
    )
    session_expiry_hours: int = Field(default=24, alias="SESSION_EXPIRY_HOURS")
    auto_approve_low_risk: bool = Field(default=True, alias="AUTO_APPROVE_LOW_RISK")

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
