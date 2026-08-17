from __future__ import annotations

import logging
import time

from app.api.schemas import (
    ExecuteQueryRequest,
    GenerateQueryRequest,
    QueryExecution,
    QueryResponse,
    ValidationInfo,
)
from app.core.config import Settings
from app.core.errors import InvalidQueryError, QueryExecutionDisabledError, UnsafeQueryError
from app.db.gateway import DatabaseGateway
from app.db.schema import DatabaseSchema, SchemaIntrospector
from app.db.validator import SQLValidator, ValidatedQuery
from app.llm.base import GenerationInput, LLMBackend
from app.llm.prompt import PromptBuilder, extract_sql

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(
        self,
        *,
        settings: Settings,
        introspector: SchemaIntrospector,
        gateway: DatabaseGateway,
        llm: LLMBackend,
        validator: SQLValidator,
        prompt_builder: PromptBuilder,
    ) -> None:
        self._settings = settings
        self._introspector = introspector
        self._gateway = gateway
        self._llm = llm
        self._validator = validator
        self._prompt_builder = prompt_builder

    @property
    def model_id(self) -> str:
        return self._llm.model_id

    def warmup(self) -> None:
        self._llm.warmup()

    def generate(self, request: GenerateQueryRequest, *, request_id: str) -> QueryResponse:
        started_at = time.perf_counter()
        if len(request.question) > self._settings.max_question_length:
            raise InvalidQueryError(
                f"Question exceeds the configured limit of {self._settings.max_question_length} characters"
            )

        dialect = request.dialect or self._settings.database_dialect
        max_rows = self._resolve_max_rows(request.max_rows)
        schema = self._introspector.get_schema()
        if not schema.tables:
            raise InvalidQueryError("The configured database has no accessible tables")

        prompt = self._prompt_builder.build(
            question=request.question,
            schema=schema,
            dialect=dialect,
            max_rows=max_rows,
        )
        generation_input = GenerationInput(
            prompt=prompt,
            question=request.question,
            dialect=dialect,
            max_rows=max_rows,
        )
        raw_output = self._llm.generate(generation_input)
        sql = extract_sql(raw_output)
        validated = self._validate_with_repair(
            sql=sql,
            generation_input=generation_input,
            schema=schema,
        )

        execution = None
        if request.execute:
            self._ensure_execution_allowed(dialect)
            execution = self._execute(validated.sql)

        elapsed = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Text-to-SQL request completed",
            extra={
                "dialect": dialect,
                "model_id": self._llm.model_id,
                "tables": list(validated.tables),
                "executed": request.execute,
                "generation_ms": elapsed,
            },
        )
        return self._response(
            request_id=request_id,
            question=request.question,
            dialect=dialect,
            validated=validated,
            execution=execution,
            elapsed_ms=elapsed,
        )

    def execute(self, request: ExecuteQueryRequest, *, request_id: str) -> QueryResponse:
        started_at = time.perf_counter()
        dialect = self._settings.database_dialect
        self._ensure_execution_allowed(dialect)
        schema = self._introspector.get_schema()
        max_rows = self._resolve_max_rows(request.max_rows)
        validated = self._validator.validate(
            request.sql,
            dialect=dialect,
            allowed_tables=schema.table_names,
            max_rows=max_rows,
        )
        execution = self._execute(validated.sql)
        elapsed = round((time.perf_counter() - started_at) * 1000, 2)
        return self._response(
            request_id=request_id,
            question=None,
            dialect=dialect,
            validated=validated,
            execution=execution,
            elapsed_ms=elapsed,
        )

    def _validate_with_repair(
        self,
        *,
        sql: str,
        generation_input: GenerationInput,
        schema: DatabaseSchema,
    ) -> ValidatedQuery:
        candidate = sql
        for attempt in range(self._settings.max_repair_attempts + 1):
            try:
                return self._validator.validate(
                    candidate,
                    dialect=generation_input.dialect,
                    allowed_tables=schema.table_names,
                    max_rows=generation_input.max_rows,
                )
            except (InvalidQueryError, UnsafeQueryError) as exc:
                if attempt >= self._settings.max_repair_attempts:
                    raise
                logger.info(
                    "Repairing rejected model output",
                    extra={"attempt": attempt + 1, "validation_code": exc.code},
                )
                repair_prompt = self._prompt_builder.build_repair(
                    question=generation_input.question,
                    schema=schema,
                    dialect=generation_input.dialect,
                    max_rows=generation_input.max_rows,
                    invalid_sql=candidate,
                    validation_error=exc.message,
                )
                candidate = extract_sql(
                    self._llm.generate(
                        GenerationInput(
                            prompt=repair_prompt,
                            question=generation_input.question,
                            dialect=generation_input.dialect,
                            max_rows=generation_input.max_rows,
                        )
                    )
                )
        raise AssertionError("unreachable")

    def _ensure_execution_allowed(self, dialect: str) -> None:
        if not self._settings.allow_query_execution:
            raise QueryExecutionDisabledError("Query execution is disabled by server policy")
        if dialect != self._settings.database_dialect:
            raise InvalidQueryError("Only the configured database dialect can be executed")

    def _resolve_max_rows(self, requested: int | None) -> int:
        value = requested or self._settings.default_max_rows
        return min(value, self._settings.max_rows_cap)

    def _execute(self, sql: str) -> QueryExecution:
        result = self._gateway.execute(sql)
        return QueryExecution(
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed_ms=result.elapsed_ms,
        )

    def _response(
        self,
        *,
        request_id: str,
        question: str | None,
        dialect: str,
        validated: ValidatedQuery,
        execution: QueryExecution | None,
        elapsed_ms: float,
    ) -> QueryResponse:
        return QueryResponse(
            request_id=request_id,
            question=question,
            sql=validated.sql,
            dialect=dialect,
            model=self._llm.model_id,
            validation=ValidationInfo(
                tables=list(validated.tables),
                applied_row_limit=validated.limit,
            ),
            execution=execution,
            generation_ms=elapsed_ms,
        )
