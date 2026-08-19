from __future__ import annotations

import time

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "text_to_sql_http_requests_total",
    "Total HTTP requests",
    ("method", "route", "status"),
)
HTTP_LATENCY = Histogram(
    "text_to_sql_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ("method", "route"),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        route_object = request.scope.get("route")
        route = getattr(route_object, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, route).observe(time.perf_counter() - started_at)
        return response
