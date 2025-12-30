"""
FastAPI middleware for Clerk authentication.

This middleware intercepts requests to protected routes and validates
the JWT token in the Authorization header against Clerk's JWKS.
"""

from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from daw_agents.auth.clerk import ClerkConfig, ClerkJWTVerifier
from daw_agents.auth.exceptions import (
    AuthenticationError,
    TokenExpiredError,
)


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for Clerk JWT authentication.

    This middleware:
    - Validates Authorization header format (Bearer <token>)
    - Verifies JWT tokens against Clerk JWKS
    - Stores verified user in request state for access by route handlers
    - Returns 401 for missing/invalid tokens
    - Supports excluding specific paths from authentication

    Usage:
        config = ClerkConfig(...)
        app.add_middleware(
            ClerkAuthMiddleware,
            config=config,
            exclude_paths=["/health", "/docs"]
        )
    """

    def __init__(
        self,
        app: Any,
        config: ClerkConfig,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: FastAPI application
            config: Clerk configuration
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self._verifier = ClerkJWTVerifier(config)
        self._exclude_paths = exclude_paths or []

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        """Process the request and validate authentication.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response from route or 401 error response
        """
        # Check if path is excluded from authentication
        if self._is_excluded_path(request.url.path):
            response: Response = await call_next(request)
            return response

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return self._unauthorized_response("Missing Authorization header")

        # Validate Bearer format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return self._unauthorized_response(
                "Invalid Authorization header format. Expected: Bearer <token>"
            )

        token = parts[1]

        try:
            # Verify token and get user
            user = await self._verifier.verify_token(token)

            # Store user in request state for access by route handlers
            request.state.user = user

            result: Response = await call_next(request)
            return result

        except TokenExpiredError:
            return self._unauthorized_response("Token has expired")
        except AuthenticationError as e:
            return self._unauthorized_response(str(e.message))

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from authentication.

        Args:
            path: Request URL path

        Returns:
            True if path should be excluded
        """
        for excluded in self._exclude_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False

    def _unauthorized_response(self, detail: str) -> JSONResponse:
        """Create a 401 Unauthorized response.

        Args:
            detail: Error detail message

        Returns:
            JSONResponse with 401 status
        """
        return JSONResponse(
            status_code=401,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )
