from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidQueryError(AppError):
    status_code = 422
    code = "invalid_query"


class UnsafeQueryError(AppError):
    status_code = 422
    code = "unsafe_query"


class QueryExecutionDisabledError(AppError):
    status_code = 403
    code = "query_execution_disabled"


class QueryExecutionError(AppError):
    status_code = 422
    code = "query_execution_failed"


class ModelUnavailableError(AppError):
    status_code = 503
    code = "model_unavailable"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"


class DirectQueryExecutionDisabledError(AppError):
    status_code = 403
    code = "direct_query_execution_disabled"
