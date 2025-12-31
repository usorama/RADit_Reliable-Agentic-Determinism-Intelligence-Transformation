"""Request ID middleware for correlation."""

import uuid
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from daw_server.logging_config import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to each request for log correlation.

    This middleware:
    - Reads X-Request-ID from incoming request headers if present
    - Generates a new request ID if not present
    - Stores the request ID in a context variable for logging
    - Adds X-Request-ID to response headers for client correlation
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Process the request and add request ID.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response with X-Request-ID header
        """
        # Get from header or generate new ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(request_id)

        response: Response = await call_next(request)

        # Add to response headers for client correlation
        response.headers["X-Request-ID"] = request_id

        return response
