"""
Clerk Authentication module for DAW Backend.

This module provides JWT authentication against Clerk's JWKS endpoint.

Exports:
    - ClerkConfig: Configuration model for Clerk settings
    - ClerkUser: Model representing an authenticated user
    - ClerkJWTVerifier: JWT token verification class
    - ClerkAuthMiddleware: FastAPI middleware for route protection
    - get_current_user: FastAPI dependency for required authentication
    - optional_current_user: FastAPI dependency for optional authentication
    - Authentication exceptions

Example usage with middleware:
    from daw_agents.auth import ClerkConfig, ClerkAuthMiddleware

    config = ClerkConfig(
        secret_key=os.environ["CLERK_SECRET_KEY"],
        publishable_key=os.environ["CLERK_PUBLISHABLE_KEY"],
        jwks_url="https://your-instance.clerk.accounts.dev/.well-known/jwks.json",
        authorized_parties=["https://your-app.com"],
    )

    app = FastAPI()
    app.add_middleware(
        ClerkAuthMiddleware,
        config=config,
        exclude_paths=["/health", "/docs"],
    )

Example usage with dependency injection:
    from daw_agents.auth import ClerkConfig, ClerkUser, get_current_user

    @app.get("/me")
    async def get_me(user: ClerkUser = Depends(get_current_user(config))):
        return {"user_id": user.user_id, "email": user.email}
"""

from daw_agents.auth.clerk import ClerkConfig, ClerkJWTVerifier, ClerkUser
from daw_agents.auth.dependencies import get_current_user, optional_current_user
from daw_agents.auth.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    JWKSFetchError,
    KeyNotFoundError,
    MissingTokenError,
    TokenExpiredError,
    UnauthorizedPartyError,
)
from daw_agents.auth.middleware import ClerkAuthMiddleware

__all__ = [
    # Config and models
    "ClerkConfig",
    "ClerkUser",
    # Verifier
    "ClerkJWTVerifier",
    # Middleware
    "ClerkAuthMiddleware",
    # Dependencies
    "get_current_user",
    "optional_current_user",
    # Exceptions
    "AuthenticationError",
    "InvalidTokenError",
    "TokenExpiredError",
    "UnauthorizedPartyError",
    "MissingTokenError",
    "JWKSFetchError",
    "KeyNotFoundError",
]
