"""Configuration module for Gemini Telegram Bot.

Uses pydantic-settings to load and validate environment variables.
"""

from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    bot_token: str = Field(
        ...,
        alias="BOT_TOKEN",
        description="Telegram bot token obtained from @BotFather",
    )
    gemini_api_key: str = Field(
        ...,
        alias="GEMINI_API_KEY",
        description="Google Gemini API key",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        alias="GEMINI_MODEL",
        description="Google Gemini model identifier",
    )
    max_history_messages: int = Field(
        default=20,
        gt=0,
        alias="MAX_HISTORY_MESSAGES",
        description="Maximum number of historical conversation turns to retain",
    )
    max_file_size_mb: int = Field(
        default=20,
        gt=0,
        alias="MAX_FILE_SIZE_MB",
        description="Maximum allowed input file size in megabytes",
    )

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env.example", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("bot_token", "gemini_api_key")
    @classmethod
    def validate_non_empty(cls, value: str, info) -> str:
        """Validate that critical credential tokens are not empty strings."""
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"Field '{info.field_name}' must not be empty.")
        return stripped

    @property
    def max_file_size_bytes(self) -> int:
        """Return maximum file size converted to bytes."""
        return self.max_file_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()


# Convenient global configuration instance
config: Settings = get_settings()
