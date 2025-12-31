"""
Tests for Clerk JWT authentication middleware and dependencies.

Following TDD workflow - PHASE 1: RED
These tests define the expected behavior for:
- JWT verification against Clerk JWKS
- JWKS caching mechanism
- User extraction from verified JWT
- FastAPI middleware and dependencies
"""

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Test fixtures for RSA key pair generation
@pytest.fixture
def rsa_key_pair() -> dict[str, Any]:
    """Generate RSA key pair for testing."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Get public key numbers for JWKS format
    public_numbers = public_key.public_numbers()

    return {
        "private_key": private_key,
        "public_key": public_key,
        "private_pem": private_pem,
        "public_pem": public_pem,
        "n": public_numbers.n,
        "e": public_numbers.e,
    }


@pytest.fixture
def mock_jwks(rsa_key_pair: dict[str, Any]) -> dict[str, Any]:
    """Create mock JWKS response."""
    import base64

    def int_to_base64url(num: int) -> str:
        """Convert an integer to Base64URL-encoded string."""
        byte_length = (num.bit_length() + 7) // 8
        num_bytes = num.to_bytes(byte_length, byteorder="big")
        return base64.urlsafe_b64encode(num_bytes).rstrip(b"=").decode("utf-8")

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": "test-key-id",
                "alg": "RS256",
                "n": int_to_base64url(rsa_key_pair["n"]),
                "e": int_to_base64url(rsa_key_pair["e"]),
            }
        ]
    }


@pytest.fixture
def valid_jwt_payload() -> dict[str, Any]:
    """Create valid JWT payload with Clerk claims."""
    current_time = int(time.time())
    return {
        "sub": "user_test123",
        "exp": current_time + 3600,  # 1 hour from now
        "nbf": current_time - 60,  # 1 minute ago
        "iat": current_time - 60,
        "iss": "https://clerk.test.com",
        "azp": "https://allowed-origin.com",
        "email": "test@example.com",
        "name": "Test User",
    }


@pytest.fixture
def expired_jwt_payload() -> dict[str, Any]:
    """Create expired JWT payload."""
    current_time = int(time.time())
    return {
        "sub": "user_test123",
        "exp": current_time - 3600,  # 1 hour ago (expired)
        "nbf": current_time - 7200,  # 2 hours ago
        "iat": current_time - 7200,
        "iss": "https://clerk.test.com",
        "azp": "https://allowed-origin.com",
    }


@pytest.fixture
def create_test_token(rsa_key_pair: dict[str, Any]) -> Any:
    """Factory fixture to create test JWT tokens."""
    import jwt

    def _create_token(
        payload: dict[str, Any], key_id: str = "test-key-id"
    ) -> str:
        return jwt.encode(
            payload,
            rsa_key_pair["private_pem"],
            algorithm="RS256",
            headers={"kid": key_id},
        )

    return _create_token


class TestClerkConfig:
    """Tests for ClerkConfig model."""

    def test_config_with_required_fields(self) -> None:
        """Config should accept required fields."""
        from daw_server.auth.clerk import ClerkConfig

        config = ClerkConfig(
            secret_key="sk_test_abc123",
            publishable_key="pk_test_xyz789",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )
        assert config.secret_key == "sk_test_abc123"
        assert config.publishable_key == "pk_test_xyz789"
        assert config.jwks_url == "https://clerk.test.com/.well-known/jwks.json"

    def test_config_with_authorized_parties(self) -> None:
        """Config should support authorized parties for azp claim validation."""
        from daw_server.auth.clerk import ClerkConfig

        config = ClerkConfig(
            secret_key="sk_test_abc123",
            publishable_key="pk_test_xyz789",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            authorized_parties=["https://app1.com", "https://app2.com"],
        )
        assert config.authorized_parties == ["https://app1.com", "https://app2.com"]


class TestClerkUser:
    """Tests for ClerkUser model."""

    def test_user_model_with_all_fields(self) -> None:
        """User model should hold all user information."""
        from daw_server.auth.clerk import ClerkUser

        user = ClerkUser(
            user_id="user_123",
            email="test@example.com",
            name="Test User",
            claims={"role": "admin"},
        )
        assert user.user_id == "user_123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.claims == {"role": "admin"}

    def test_user_model_with_optional_fields(self) -> None:
        """User model should work with minimal required fields."""
        from daw_server.auth.clerk import ClerkUser

        user = ClerkUser(user_id="user_123", claims={})
        assert user.user_id == "user_123"
        assert user.email is None
        assert user.name is None
        assert user.claims == {}


class TestClerkJWTVerifier:
    """Tests for ClerkJWTVerifier class."""

    @pytest.mark.asyncio
    async def test_verify_valid_token(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should successfully verify a valid JWT token."""
        from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            authorized_parties=["https://allowed-origin.com"],
        )
        verifier = ClerkJWTVerifier(config)

        token = create_test_token(valid_jwt_payload)

        with patch.object(
            verifier, "_fetch_jwks", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks
            user = await verifier.verify_token(token)

        assert user.user_id == "user_test123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"

    @pytest.mark.asyncio
    async def test_verify_expired_token_raises(
        self,
        mock_jwks: dict[str, Any],
        expired_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should raise exception for expired token."""
        from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier
        from daw_server.auth.exceptions import TokenExpiredError

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )
        verifier = ClerkJWTVerifier(config)

        token = create_test_token(expired_jwt_payload)

        with patch.object(
            verifier, "_fetch_jwks", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks
            with pytest.raises(TokenExpiredError):
                await verifier.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_invalid_signature_raises(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        rsa_key_pair: dict[str, Any],
    ) -> None:
        """Should raise exception for invalid token signature."""
        import jwt

        # Generate a different key pair for signing
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier
        from daw_server.auth.exceptions import InvalidTokenError

        different_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        different_private_pem = different_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Sign token with different key
        token = jwt.encode(
            valid_jwt_payload,
            different_private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-id"},
        )

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )
        verifier = ClerkJWTVerifier(config)

        with patch.object(
            verifier, "_fetch_jwks", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks
            with pytest.raises(InvalidTokenError):
                await verifier.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_invalid_authorized_party_raises(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should raise exception when azp claim doesn't match authorized parties."""
        from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier
        from daw_server.auth.exceptions import UnauthorizedPartyError

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            authorized_parties=["https://different-origin.com"],  # Not matching
        )
        verifier = ClerkJWTVerifier(config)

        token = create_test_token(valid_jwt_payload)

        with patch.object(
            verifier, "_fetch_jwks", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks
            with pytest.raises(UnauthorizedPartyError):
                await verifier.verify_token(token)

    @pytest.mark.asyncio
    async def test_jwks_caching(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should cache JWKS and not fetch on every request."""
        from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            jwks_cache_ttl=300,  # 5 minutes
        )
        verifier = ClerkJWTVerifier(config)

        token = create_test_token(valid_jwt_payload)

        with patch.object(
            verifier, "_fetch_jwks", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            # First verification - should fetch
            await verifier.verify_token(token)
            assert mock_fetch.call_count == 1

            # Second verification - should use cache
            await verifier.verify_token(token)
            assert mock_fetch.call_count == 1  # Still 1, used cache

    @pytest.mark.asyncio
    async def test_jwks_cache_expiration(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should refetch JWKS when cache expires."""
        from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            jwks_cache_ttl=1,  # 1 second TTL
        )
        verifier = ClerkJWTVerifier(config)

        token = create_test_token(valid_jwt_payload)

        with patch.object(
            verifier, "_fetch_jwks", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            # First verification - should fetch
            await verifier.verify_token(token)
            assert mock_fetch.call_count == 1

            # Wait for cache to expire
            time.sleep(1.5)

            # Third verification - should refetch (cache expired)
            await verifier.verify_token(token)
            assert mock_fetch.call_count == 2


class TestClerkAuthMiddleware:
    """Tests for FastAPI Clerk authentication middleware."""

    def test_missing_auth_header_raises_401(self) -> None:
        """Should return 401 when Authorization header is missing."""
        from daw_server.auth.clerk import ClerkConfig
        from daw_server.auth.middleware import ClerkAuthMiddleware

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )

        app = FastAPI()
        app.add_middleware(ClerkAuthMiddleware, config=config)

        @app.get("/protected")
        async def protected_route() -> dict[str, str]:
            return {"message": "protected"}

        client = TestClient(app)
        response = client.get("/protected")

        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_invalid_bearer_format_raises_401(self) -> None:
        """Should return 401 when Authorization header format is invalid."""
        from daw_server.auth.clerk import ClerkConfig
        from daw_server.auth.middleware import ClerkAuthMiddleware

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )

        app = FastAPI()
        app.add_middleware(ClerkAuthMiddleware, config=config)

        @app.get("/protected")
        async def protected_route() -> dict[str, str]:
            return {"message": "protected"}

        client = TestClient(app)
        response = client.get("/protected", headers={"Authorization": "NotBearer token"})

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_allows_access(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should allow access with valid token."""
        from daw_server.auth.clerk import ClerkConfig
        from daw_server.auth.middleware import ClerkAuthMiddleware

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            authorized_parties=["https://allowed-origin.com"],
        )

        app = FastAPI()
        app.add_middleware(ClerkAuthMiddleware, config=config)

        @app.get("/protected")
        async def protected_route() -> dict[str, str]:
            return {"message": "protected"}

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                "/protected", headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 200
        assert response.json() == {"message": "protected"}

    def test_health_endpoint_not_protected(self) -> None:
        """Health endpoint should not require authentication."""
        from daw_server.auth.clerk import ClerkConfig
        from daw_server.auth.middleware import ClerkAuthMiddleware

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )

        app = FastAPI()
        app.add_middleware(
            ClerkAuthMiddleware,
            config=config,
            exclude_paths=["/health", "/docs", "/openapi.json"],
        )

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy"}

        @app.get("/protected")
        async def protected_route() -> dict[str, str]:
            return {"message": "protected"}

        client = TestClient(app)

        # Health should work without auth
        health_response = client.get("/health")
        assert health_response.status_code == 200

        # Protected should fail without auth
        protected_response = client.get("/protected")
        assert protected_response.status_code == 401


class TestGetCurrentUser:
    """Tests for get_current_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_extract_user_from_request(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should extract user from verified JWT in request."""
        from daw_server.auth.clerk import ClerkConfig, ClerkUser
        from daw_server.auth.dependencies import get_current_user

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            authorized_parties=["https://allowed-origin.com"],
        )

        app = FastAPI()

        @app.get("/me")
        async def get_me(user: ClerkUser = get_current_user(config)) -> dict[str, Any]:
            return {
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
            }

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_test123"
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self) -> None:
        """Should raise 401 when token is missing."""
        from daw_server.auth.clerk import ClerkConfig, ClerkUser
        from daw_server.auth.dependencies import get_current_user

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )

        app = FastAPI()

        @app.get("/me")
        async def get_me(user: ClerkUser = get_current_user(config)) -> dict[str, Any]:
            return {"user_id": user.user_id}

        client = TestClient(app)
        response = client.get("/me")

        assert response.status_code == 401


class TestOptionalCurrentUser:
    """Tests for optional_current_user dependency (allows anonymous access)."""

    @pytest.mark.asyncio
    async def test_returns_none_without_token(self) -> None:
        """Should return None when no token is provided."""
        from daw_server.auth.clerk import ClerkConfig, ClerkUser
        from daw_server.auth.dependencies import optional_current_user

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
        )

        app = FastAPI()

        @app.get("/optional")
        async def optional_route(
            user: ClerkUser | None = optional_current_user(config),
        ) -> dict[str, Any]:
            return {"user_id": user.user_id if user else None}

        client = TestClient(app)
        response = client.get("/optional")

        assert response.status_code == 200
        assert response.json() == {"user_id": None}

    @pytest.mark.asyncio
    async def test_returns_user_with_valid_token(
        self,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Should return user when valid token is provided."""
        from daw_server.auth.clerk import ClerkConfig, ClerkUser
        from daw_server.auth.dependencies import optional_current_user

        config = ClerkConfig(
            secret_key="sk_test_abc",
            publishable_key="pk_test_xyz",
            jwks_url="https://clerk.test.com/.well-known/jwks.json",
            authorized_parties=["https://allowed-origin.com"],
        )

        app = FastAPI()

        @app.get("/optional")
        async def optional_route(
            user: ClerkUser | None = optional_current_user(config),
        ) -> dict[str, Any]:
            return {"user_id": user.user_id if user else None}

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                "/optional", headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 200
        assert response.json() == {"user_id": "user_test123"}
