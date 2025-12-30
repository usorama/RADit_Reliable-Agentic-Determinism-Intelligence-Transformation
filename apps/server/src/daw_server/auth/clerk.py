"""
Clerk JWT verification for FastAPI.

This module provides JWT token verification against Clerk's JWKS endpoint,
including key caching, claim validation, and user extraction.

Based on Clerk's manual JWT verification documentation:
https://clerk.com/docs/backend-requests/manual-jwt

Key verification steps:
1. Extract token from Authorization header
2. Decode JWT header to get kid (key ID)
3. Fetch/cache JWKS from Clerk
4. Find matching key by kid
5. Verify signature with public key
6. Check claims (exp, nbf, azp)
7. Return ClerkUser with claims
"""

import base64
import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from pydantic import BaseModel, Field

from daw_server.auth.exceptions import (
    InvalidTokenError,
    JWKSFetchError,
    KeyNotFoundError,
    TokenExpiredError,
    UnauthorizedPartyError,
)


class ClerkConfig(BaseModel):
    """Configuration for Clerk authentication.

    Attributes:
        secret_key: Clerk secret key (CLERK_SECRET_KEY env var)
        publishable_key: Clerk publishable key (CLERK_PUBLISHABLE_KEY env var)
        jwks_url: URL to Clerk's JWKS endpoint
        authorized_parties: List of allowed azp (authorized party) values
        jwks_cache_ttl: TTL in seconds for JWKS cache (default: 300 = 5 minutes)
    """

    secret_key: str
    publishable_key: str
    jwks_url: str
    authorized_parties: list[str] = Field(default_factory=list)
    jwks_cache_ttl: int = Field(default=300)


class ClerkUser(BaseModel):
    """Authenticated user from Clerk JWT.

    Attributes:
        user_id: Clerk user ID (from 'sub' claim)
        email: User's email address (optional)
        name: User's display name (optional)
        claims: All JWT claims for advanced use cases
    """

    user_id: str
    email: str | None = None
    name: str | None = None
    claims: dict[str, Any]


class ClerkJWTVerifier:
    """Verifies Clerk JWT tokens against JWKS.

    This class handles:
    - Fetching and caching JWKS from Clerk
    - JWT signature verification using RS256
    - Standard claim validation (exp, nbf)
    - Authorized party (azp) validation
    - User extraction from verified tokens
    """

    def __init__(self, config: ClerkConfig) -> None:
        """Initialize the JWT verifier.

        Args:
            config: Clerk configuration including JWKS URL and authorized parties
        """
        self._config = config
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_time: float = 0

    async def verify_token(self, token: str) -> ClerkUser:
        """Verify a JWT token and extract user information.

        Args:
            token: JWT token string (without 'Bearer ' prefix)

        Returns:
            ClerkUser with verified user information

        Raises:
            InvalidTokenError: Token is malformed or has invalid signature
            TokenExpiredError: Token has expired
            UnauthorizedPartyError: azp claim doesn't match authorized parties
            KeyNotFoundError: Key ID not found in JWKS
            JWKSFetchError: Failed to fetch JWKS from Clerk
        """
        # Get JWKS (from cache or fetch)
        jwks = await self._get_jwks()

        try:
            # Decode token header to get kid
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise InvalidTokenError("Token missing 'kid' in header")

            # Find matching key in JWKS
            signing_key = self._find_key_by_kid(jwks, kid)

            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                options={
                    "verify_exp": True,
                    "verify_nbf": True,
                    "require": ["exp", "nbf", "sub"],
                },
            )

            # Validate authorized parties if configured
            if self._config.authorized_parties:
                azp = payload.get("azp")
                if azp and azp not in self._config.authorized_parties:
                    raise UnauthorizedPartyError(
                        f"Token azp '{azp}' not in authorized parties"
                    )

            # Extract user from claims
            return ClerkUser(
                user_id=payload["sub"],
                email=payload.get("email"),
                name=payload.get("name"),
                claims=payload,
            )

        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except jwt.InvalidSignatureError as e:
            raise InvalidTokenError("Invalid token signature") from e
        except jwt.DecodeError as e:
            raise InvalidTokenError(f"Failed to decode token: {e}") from e
        except jwt.MissingRequiredClaimError as e:
            raise InvalidTokenError(f"Missing required claim: {e}") from e

    async def _get_jwks(self) -> dict[str, Any]:
        """Get JWKS from cache or fetch from Clerk.

        Returns:
            JWKS dictionary with keys

        Raises:
            JWKSFetchError: Failed to fetch JWKS
        """
        current_time = time.time()

        # Check if cache is valid
        if self._jwks_cache is not None:
            cache_age = current_time - self._jwks_cache_time
            if cache_age < self._config.jwks_cache_ttl:
                return self._jwks_cache

        # Fetch fresh JWKS
        jwks = await self._fetch_jwks()
        self._jwks_cache = jwks
        self._jwks_cache_time = current_time
        return jwks

    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from Clerk endpoint.

        Returns:
            JWKS dictionary

        Raises:
            JWKSFetchError: Failed to fetch or parse JWKS
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self._config.jwks_url,
                    timeout=10.0,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result
        except httpx.HTTPError as e:
            raise JWKSFetchError(f"Failed to fetch JWKS: {e}") from e
        except ValueError as e:
            raise JWKSFetchError(f"Invalid JWKS response: {e}") from e

    def _find_key_by_kid(self, jwks: dict[str, Any], kid: str) -> Any:
        """Find a key in JWKS by key ID.

        Args:
            jwks: JWKS dictionary
            kid: Key ID to find

        Returns:
            RSA public key for verification

        Raises:
            KeyNotFoundError: Key ID not found in JWKS
        """

        def base64url_decode(data: str) -> bytes:
            """Decode base64url-encoded string."""
            # Add padding if necessary
            padding = 4 - len(data) % 4
            if padding != 4:
                data += "=" * padding
            return base64.urlsafe_b64decode(data)

        def int_from_base64url(data: str) -> int:
            """Convert base64url-encoded string to integer."""
            decoded = base64url_decode(data)
            return int.from_bytes(decoded, byteorder="big")

        keys = jwks.get("keys", [])
        for key in keys:
            if key.get("kid") == kid:
                # Build RSA public key from n and e
                n = int_from_base64url(key["n"])
                e = int_from_base64url(key["e"])

                public_numbers = RSAPublicNumbers(e, n)
                public_key = public_numbers.public_key(default_backend())
                return public_key

        raise KeyNotFoundError(f"Key with kid '{kid}' not found in JWKS")
