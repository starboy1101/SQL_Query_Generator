from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Dialect = Literal["sqlite", "postgres", "mysql", "tsql", "oracle"]


class GenerateQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=20_000, examples=["Show the five highest-value orders"])
    dialect: Dialect | None = Field(default=None, description="Defaults to the configured database dialect")
    max_rows: int | None = Field(default=None, ge=1, le=100_000)
    execute: bool = Field(default=False, description="Execute after validation when server policy permits")

    @field_validator("question")
    @classmethod
    def question_must_have_text(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("question must contain letters or numbers")
        return value


class ExecuteQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sql: str = Field(min_length=6, max_length=100_000)
    max_rows: int | None = Field(default=None, ge=1, le=100_000)


class ValidationInfo(BaseModel):
    read_only: bool = True
    tables: list[str]
    applied_row_limit: int


class QueryExecution(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: float


class QueryResponse(BaseModel):
    request_id: str
    question: str | None = None
    sql: str
    dialect: str
    model: str
    validation: ValidationInfo
    execution: QueryExecution | None = None
    generation_ms: float


class ColumnResponse(BaseModel):
    name: str
    data_type: str
    nullable: bool
    primary_key: bool


class ForeignKeyResponse(BaseModel):
    columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableResponse(BaseModel):
    name: str
    kind: str
    columns: list[ColumnResponse]
    foreign_keys: list[ForeignKeyResponse]


class DatabaseSchemaResponse(BaseModel):
    dialect: str
    tables: list[TableResponse]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict[str, bool] = Field(default_factory=dict)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
