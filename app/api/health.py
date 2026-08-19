from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse, include_in_schema=False)
def liveness(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", version=request.app.state.settings.app_version)


@router.get("/health/ready", response_model=HealthResponse, include_in_schema=False)
def readiness(request: Request, response: Response) -> HealthResponse:
    database_ok = request.app.state.gateway.ping()
    schema_ok = False
    if database_ok:
        try:
            discovered = request.app.state.introspector.get_schema()
            discovered_names = {name.lower() for name in discovered.table_names}
            expected_names = {name.lower() for name in request.app.state.settings.allowed_tables}
            schema_ok = bool(discovered.tables) and expected_names.issubset(discovered_names)
        except Exception:
            schema_ok = False
    if not database_ok or not schema_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok and schema_ok else "degraded",
        version=request.app.state.settings.app_version,
        checks={
            "database": database_ok,
            "schema": schema_ok,
            "model_configured": bool(request.app.state.query_service.model_id),
        },
    )
