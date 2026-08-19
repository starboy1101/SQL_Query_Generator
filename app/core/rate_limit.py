from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small single-process limiter for anonymous demo deployments.

    Production systems running multiple replicas should enforce an additional
    distributed limit at the gateway or with a shared counter store.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        requests_per_minute: int,
        protected_paths: tuple[str, ...],
    ) -> None:
        super().__init__(app)
        self._limit = requests_per_minute
        self._protected_paths = set(protected_paths)
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._limit == 0 or request.url.path not in self._protected_paths:
            return await call_next(request)

        now = time.monotonic()
        cutoff = now - 60.0
        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"

        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self._limit:
                retry_after = max(1, math.ceil(60.0 - (now - timestamps[0])))
                return JSONResponse(
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self._limit),
                        "X-RateLimit-Remaining": "0",
                    },
                    content={
                        "error": {
                            "code": "rate_limit_exceeded",
                            "message": "Too many requests. Please wait before trying again.",
                            "request_id": getattr(request.state, "request_id", "-"),
                            "details": {"retry_after_seconds": retry_after},
                        }
                    },
                )
            timestamps.append(now)
            remaining = self._limit - len(timestamps)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
