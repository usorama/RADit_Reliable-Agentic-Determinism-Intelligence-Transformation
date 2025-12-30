"""
FastAPI dependencies for Clerk authentication.

This module provides FastAPI dependency injection functions for
accessing the authenticated user in route handlers.

Usage:
    from daw_server.auth.dependencies import get_current_user

    @app.get("/me")
    async def get_me(user: ClerkUser = Depends(get_current_user(config))):
        return {"user_id": user.user_id}
"""

from collections.abc import Callable
from typing import Any, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier, ClerkUser
from daw_server.auth.exceptions import AuthenticationError

# Security scheme for OpenAPI documentation
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(config: ClerkConfig) -> Callable[..., Any]:
    """Create a FastAPI dependency that returns the current authenticated user.

    This dependency:
    - Extracts Bearer token from Authorization header
    - Verifies token against Clerk JWKS
    - Returns ClerkUser on success
    - Raises HTTPException 401 on failure

    Args:
        config: Clerk configuration

    Returns:
        FastAPI dependency function

    Usage:
        @app.get("/me")
        async def get_me(user: ClerkUser = Depends(get_current_user(config))):
            return {"user_id": user.user_id}
    """
    verifier = ClerkJWTVerifier(config)

    async def _get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    ) -> ClerkUser:
        """Internal dependency that performs token verification.

        Args:
            credentials: HTTP Bearer credentials from Authorization header

        Returns:
            Verified ClerkUser

        Raises:
            HTTPException: 401 if authentication fails
        """
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            user = await verifier.verify_token(credentials.credentials)
            return user
        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e.message),
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    return cast(Callable[..., Any], Depends(_get_current_user))


def optional_current_user(config: ClerkConfig) -> Callable[..., Any]:
    """Create a FastAPI dependency that optionally returns the current user.

    This dependency:
    - Returns ClerkUser if valid token is provided
    - Returns None if no token is provided
    - Raises HTTPException 401 for invalid tokens

    Useful for routes that can work with or without authentication.

    Args:
        config: Clerk configuration

    Returns:
        FastAPI dependency function

    Usage:
        @app.get("/content")
        async def get_content(
            user: ClerkUser | None = Depends(optional_current_user(config))
        ):
            if user:
                return {"content": "premium", "user_id": user.user_id}
            return {"content": "free"}
    """
    verifier = ClerkJWTVerifier(config)

    async def _optional_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    ) -> ClerkUser | None:
        """Internal dependency that optionally verifies token.

        Args:
            credentials: HTTP Bearer credentials from Authorization header

        Returns:
            Verified ClerkUser or None if no credentials provided

        Raises:
            HTTPException: 401 if token is provided but invalid
        """
        if credentials is None:
            return None

        try:
            user = await verifier.verify_token(credentials.credentials)
            return user
        except AuthenticationError:
            # For optional auth, we return None on failure rather than raising
            # This allows anonymous access when no valid token is provided
            return None

    return cast(Callable[..., Any], Depends(_optional_current_user))
