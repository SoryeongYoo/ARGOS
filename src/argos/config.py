from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    claude_model: str = Field("claude-sonnet-4-6", alias="CLAUDE_MODEL")
    claude_haiku_model: str = Field("claude-haiku-4-5-20251001", alias="CLAUDE_HAIKU_MODEL")

    duckdb_path: Path = Field(Path("data/db/argos.duckdb"), alias="DUCKDB_PATH")

    data_start_date: str = Field("2022-01-01", alias="DATA_START_DATE")
    data_end_date: str = Field("2024-12-31", alias="DATA_END_DATE")
    random_seed: int = Field(42, alias="RANDOM_SEED")

    log_level: str = Field("INFO", alias="LOG_LEVEL")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
