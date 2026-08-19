from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import QueryServiceDependency, SchemaDependency, verify_api_key
from app.api.schemas import (
    CapabilitiesResponse,
    DatabaseSchemaResponse,
    ExecuteQueryRequest,
    GenerateQueryRequest,
    QueryResponse,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="Return public API limits and feature availability",
)
def get_capabilities(request: Request, service: QueryServiceDependency) -> CapabilitiesResponse:
    settings = request.app.state.settings
    return CapabilitiesResponse(
        dialect=settings.database_dialect,
        model=service.model_id,
        execution_enabled=settings.allow_query_execution,
        default_max_rows=settings.default_max_rows,
        max_rows_cap=settings.max_rows_cap,
        max_question_length=settings.max_question_length,
    )


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
def get_database_schema(introspector: SchemaDependency) -> DatabaseSchemaResponse:
    schema = introspector.get_schema()
    return DatabaseSchemaResponse.model_validate(schema.to_dict())
