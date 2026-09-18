import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("nexus.access")


class LoggingAndTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        start_time = time.perf_counter()
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-MS"] = f"{process_time_ms:.2f}"

        # Don't clutter logs with high-frequency health polls
        if request.url.path != "/health":
            logger.info(
                "http_request_finished",
                status_code=response.status_code,
                duration_ms=round(process_time_ms, 2),
            )

        return response
