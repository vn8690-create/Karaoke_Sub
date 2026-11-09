"""
Audit logging middleware for tracking all HTTP requests.

This middleware captures request metadata and logs it to Cloud Logging
for audit trail and user activity investigation purposes.
"""
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("audit")

# Endpoints to exclude from audit logging (high-frequency health checks)
EXCLUDED_PATHS = {
    "/",
    "/api/health",
    "/api/health/detailed",
    "/api/readiness",
    "/healthz",
    "/ready",
}


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests for audit purposes.

    Captures:
    - request_id: UUID for correlating with auth logs
    - method: HTTP method
    - path: Request path
    - status_code: Response status
    - latency_ms: Request duration
    - client_ip: Client IP (from X-Forwarded-For for proxied requests)
    - user_agent: Browser/client identifier

    The request_id is stored in request.state and added to response headers,
    allowing correlation with auth logs that capture user_email.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip excluded paths (health checks)
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # Generate unique request ID for correlation
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Capture start time
        start_time = time.time()

        # Extract client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Process request
        try:
            response = await call_next(request)
        except Exception:
            # Log failed requests too (exception() auto-includes stack trace)
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception(
                "request_audit_error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": str(request.query_params) if request.query_params else None,
                    "latency_ms": latency_ms,
                    "client_ip": client_ip,
                    "user_agent": user_agent[:200] if user_agent else None,
                    "audit_type": "http_request",
                }
            )
            raise

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log audit entry (INFO level for successful requests)
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            "request_audit",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_string": str(request.query_params) if request.query_params else None,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "client_ip": client_ip,
                "user_agent": user_agent[:200] if user_agent else None,
                "audit_type": "http_request",
            }
        )

        # Add request_id to response headers for debugging/correlation
        response.headers["X-Request-ID"] = request_id

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address, handling proxy scenarios.

        Cloud Run and other proxies set X-Forwarded-For header.
        """
        # Check X-Forwarded-For for proxy scenarios (Cloud Run, load balancers)
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # First IP is the original client
            return forwarded.split(",")[0].strip()

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"
