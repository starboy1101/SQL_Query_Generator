from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import QueryServiceDependency, SchemaDependency, verify_api_key
from app.api.schemas import (
    DatabaseSchemaResponse,
    ExecuteQueryRequest,
    GenerateQueryRequest,
    QueryResponse,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post(
    "/queries/generate",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a validated SQL query from natural language",
)
def generate_query(
    payload: GenerateQueryRequest,
    request: Request,
    service: QueryServiceDependency,
) -> QueryResponse:
    return service.generate(payload, request_id=request.state.request_id)


@router.post(
    "/queries/execute",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and execute one read-only SQL query",
)
def execute_query(
    payload: ExecuteQueryRequest,
    request: Request,
    service: QueryServiceDependency,
) -> QueryResponse:
    return service.execute(payload, request_id=request.state.request_id)


@router.get(
    "/schema",
    response_model=DatabaseSchemaResponse,
    summary="Return the schema visible to the language model",
)
def get_database_schema(introspector: SchemaDependency, refresh: bool = False) -> DatabaseSchemaResponse:
    schema = introspector.get_schema(force_refresh=refresh)
    return DatabaseSchemaResponse.model_validate(schema.to_dict())
