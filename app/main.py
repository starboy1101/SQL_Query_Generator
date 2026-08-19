from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.health import router as health_router
from app.api.routes import router as api_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, request_id_context
from app.core.metrics import MetricsMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.db.gateway import DatabaseGateway, create_database_engine
from app.db.schema import SchemaIntrospector
from app.db.validator import SQLValidator
from app.llm.factory import create_llm_backend
from app.llm.prompt import PromptBuilder
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(settings.database_url)
        gateway = DatabaseGateway(engine, timeout_seconds=settings.query_timeout_seconds)
        introspector = SchemaIntrospector(
            engine,
            dialect=settings.database_dialect,
            schema_name=settings.database_schema,
            allowed_tables=settings.allowed_tables,
            include_views=settings.include_views,
            cache_ttl_seconds=settings.schema_cache_ttl_seconds,
        )
        llm = create_llm_backend(settings, introspector)
        service = QueryService(
            settings=settings,
            introspector=introspector,
            gateway=gateway,
            llm=llm,
            validator=SQLValidator(),
            prompt_builder=PromptBuilder(),
        )
        app.state.settings = settings
        app.state.gateway = gateway
        app.state.introspector = introspector
        app.state.query_service = service
        if settings.model_warmup_on_start:
            service.warmup()
        logger.info("Application started", extra={"environment": settings.app_env, "model_id": llm.model_id})
        try:
            yield
        finally:
            engine.dispose()
            logger.info("Application stopped")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Schema-aware natural-language-to-SQL generation with read-only validation.",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_requests_per_minute,
        protected_paths=(
            f"{settings.api_prefix}/queries/generate",
            f"{settings.api_prefix}/queries/execute",
        ),
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get("X-Request-ID", "")
        request_id = incoming_id[:128] if incoming_id else str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
            )
            return response
        finally:
            request_id_context.reset(token)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", "-"),
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "The request payload is invalid",
                    "request_id": getattr(request.state, "request_id", "-"),
                    "details": {"errors": jsonable_encoder(exc.errors())},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", "-"),
                    "details": {},
                }
            },
        )

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix, tags=["text-to-sql"])
    if settings.metrics_enabled:
        app.mount("/metrics", make_asgi_app())
    frontend_directory = Path(settings.frontend_dist_dir)
    if settings.serve_frontend and frontend_directory.is_dir():
        app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
    return app


app = create_app()
