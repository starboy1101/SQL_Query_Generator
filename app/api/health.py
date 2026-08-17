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
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        version=request.app.state.settings.app_version,
        checks={"database": database_ok, "model_configured": bool(request.app.state.query_service.model_id)},
    )
