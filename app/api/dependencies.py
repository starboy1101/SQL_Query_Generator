from __future__ import annotations

import secrets
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.core.errors import AuthenticationError
from app.db.gateway import DatabaseGateway
from app.db.schema import SchemaIntrospector
from app.services.query_service import QueryService

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(request: Request, supplied_key: str | None = Depends(_api_key_header)) -> None:
    expected_key = request.app.state.settings.api_key
    if expected_key and (not supplied_key or not secrets.compare_digest(supplied_key, expected_key)):
        raise AuthenticationError("A valid API key is required")


def get_query_service(request: Request) -> QueryService:
    return cast(QueryService, request.app.state.query_service)


def get_introspector(request: Request) -> SchemaIntrospector:
    return cast(SchemaIntrospector, request.app.state.introspector)


def get_gateway(request: Request) -> DatabaseGateway:
    return cast(DatabaseGateway, request.app.state.gateway)


QueryServiceDependency = Annotated[QueryService, Depends(get_query_service)]
SchemaDependency = Annotated[SchemaIntrospector, Depends(get_introspector)]
GatewayDependency = Annotated[DatabaseGateway, Depends(get_gateway)]
