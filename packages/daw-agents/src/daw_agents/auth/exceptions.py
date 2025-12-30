"""
Custom exceptions for Clerk authentication.

These exceptions provide specific error types for different authentication
failure scenarios, enabling precise error handling and appropriate HTTP responses.
"""


class AuthenticationError(Exception):
    """Base exception for all authentication errors."""

    def __init__(self, message: str = "Authentication failed") -> None:
        self.message = message
        super().__init__(self.message)


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is invalid (malformed, wrong signature, etc.)."""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message)


class UnauthorizedPartyError(AuthenticationError):
    """Raised when the azp (authorized party) claim doesn't match allowed origins."""

    def __init__(
        self, message: str = "Token not authorized for this application"
    ) -> None:
        super().__init__(message)


class MissingTokenError(AuthenticationError):
    """Raised when no authentication token is provided."""

    def __init__(self, message: str = "Authentication token required") -> None:
        super().__init__(message)


class JWKSFetchError(AuthenticationError):
    """Raised when JWKS endpoint cannot be reached or returns invalid data."""

    def __init__(self, message: str = "Failed to fetch JWKS") -> None:
        super().__init__(message)


class KeyNotFoundError(AuthenticationError):
    """Raised when the key ID (kid) from JWT is not found in JWKS."""

    def __init__(self, message: str = "Signing key not found in JWKS") -> None:
        super().__init__(message)
