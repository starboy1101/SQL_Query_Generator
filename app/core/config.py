from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "LLM-Powered SQL Query Generator"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:3000",)
    api_key: str | None = None

    database_url: str = "sqlite:///./data/demo.db"
    database_dialect: Literal["sqlite", "postgres", "mysql", "tsql", "oracle"] = "sqlite"
    database_schema: str | None = None
    allowed_tables: Annotated[tuple[str, ...], NoDecode] = ()
    include_views: bool = True
    schema_cache_ttl_seconds: int = Field(default=300, ge=0, le=86_400)

    llm_backend: Literal["heuristic", "huggingface", "openai_compatible"] = "heuristic"
    model_name_or_path: str = "codellama/CodeLlama-7b-Instruct-hf"
    adapter_path: str | None = None
    model_api_base_url: str = "http://localhost:8001"
    model_api_key: str | None = None
    model_request_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    model_max_input_tokens: int = Field(default=3072, ge=256, le=16_384)
    model_max_new_tokens: int = Field(default=256, ge=32, le=2048)
    model_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    model_device: str = "auto"
    model_use_4bit: bool = True
    model_trust_remote_code: bool = False
    model_warmup_on_start: bool = False
    max_repair_attempts: int = Field(default=1, ge=0, le=2)

    allow_query_execution: bool = False
    default_max_rows: int = Field(default=100, ge=1, le=10_000)
    max_rows_cap: int = Field(default=1000, ge=1, le=100_000)
    query_timeout_seconds: int = Field(default=10, ge=1, le=300)
    max_question_length: int = Field(default=2000, ge=32, le=20_000)

    @field_validator("allowed_tables", "cors_origins", mode="before")
    @classmethod
    def parse_csv_tuple(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("max_rows_cap")
    @classmethod
    def cap_must_cover_default(cls, value: int, info: object) -> int:
        data = getattr(info, "data", {})
        default = data.get("default_max_rows")
        if isinstance(default, int) and value < default:
            raise ValueError("max_rows_cap must be greater than or equal to default_max_rows")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
