"""
Tests for FastAPI route endpoints.

Following TDD workflow - PHASE 1: RED
These tests define the expected behavior for:
- ChatRequest/ChatResponse schemas
- WorkflowStatus schema
- POST /api/chat endpoint (auth required)
- GET /api/workflow/{id} endpoint
- POST /api/workflow/{id}/approve endpoint
- DELETE /api/workflow/{id} endpoint
- WebSocket /ws/trace/{id} endpoint
- Auth middleware integration
- OpenAPI documentation generation
- Error handling (404, 401, 403)
"""

import time
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def rsa_key_pair() -> dict[str, Any]:
    """Generate RSA key pair for testing."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

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
        "exp": current_time + 3600,
        "nbf": current_time - 60,
        "iat": current_time - 60,
        "iss": "https://clerk.test.com",
        "azp": "https://allowed-origin.com",
        "email": "test@example.com",
        "name": "Test User",
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


@pytest.fixture
def sample_workflow_id() -> str:
    """Generate a sample workflow ID."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_clerk_config() -> Any:
    """Create mock Clerk configuration."""
    from daw_agents.auth.clerk import ClerkConfig

    return ClerkConfig(
        secret_key="sk_test_abc123",
        publishable_key="pk_test_xyz789",
        jwks_url="https://clerk.test.com/.well-known/jwks.json",
        authorized_parties=["https://allowed-origin.com"],
    )


# -----------------------------------------------------------------------------
# Schema Tests
# -----------------------------------------------------------------------------


class TestChatRequestSchema:
    """Tests for ChatRequest schema."""

    def test_chat_request_with_required_fields(self) -> None:
        """ChatRequest should accept required fields."""
        from daw_agents.api.schemas import ChatRequest

        request = ChatRequest(message="Build a todo app with React")
        assert request.message == "Build a todo app with React"

    def test_chat_request_with_optional_context(self) -> None:
        """ChatRequest should support optional context field."""
        from daw_agents.api.schemas import ChatRequest

        request = ChatRequest(
            message="Build a todo app",
            context={"project_type": "web", "framework": "react"},
        )
        assert request.message == "Build a todo app"
        assert request.context == {"project_type": "web", "framework": "react"}

    def test_chat_request_with_optional_workflow_id(self) -> None:
        """ChatRequest should support optional workflow_id for continuing conversations."""
        from daw_agents.api.schemas import ChatRequest

        workflow_id = str(uuid.uuid4())
        request = ChatRequest(
            message="Continue with authentication",
            workflow_id=workflow_id,
        )
        assert request.workflow_id == workflow_id

    def test_chat_request_validates_non_empty_message(self) -> None:
        """ChatRequest should reject empty messages."""
        from pydantic import ValidationError

        from daw_agents.api.schemas import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(message="")


class TestChatResponseSchema:
    """Tests for ChatResponse schema."""

    def test_chat_response_with_all_fields(self) -> None:
        """ChatResponse should hold response data."""
        from daw_agents.api.schemas import ChatResponse

        workflow_id = str(uuid.uuid4())
        response = ChatResponse(
            workflow_id=workflow_id,
            message="I'll help you build a todo app",
            status="processing",
            tasks_generated=5,
        )
        assert response.workflow_id == workflow_id
        assert response.message == "I'll help you build a todo app"
        assert response.status == "processing"
        assert response.tasks_generated == 5

    def test_chat_response_status_enum(self) -> None:
        """ChatResponse status should be a valid enum value."""
        from daw_agents.api.schemas import ChatResponse, WorkflowStatusEnum

        response = ChatResponse(
            workflow_id=str(uuid.uuid4()),
            message="Done",
            status=WorkflowStatusEnum.COMPLETED,
        )
        assert response.status == WorkflowStatusEnum.COMPLETED


class TestWorkflowStatusSchema:
    """Tests for WorkflowStatus schema."""

    def test_workflow_status_with_all_fields(self) -> None:
        """WorkflowStatus should hold workflow state data."""
        from daw_agents.api.schemas import WorkflowStatus

        workflow_id = str(uuid.uuid4())
        status = WorkflowStatus(
            id=workflow_id,
            status="planning",
            phase="roundtable",
            progress=0.35,
            tasks_total=10,
            tasks_completed=3,
            current_task="Analyzing requirements",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert status.id == workflow_id
        assert status.status == "planning"
        assert status.phase == "roundtable"
        assert status.progress == 0.35
        assert status.tasks_total == 10
        assert status.tasks_completed == 3

    def test_workflow_status_with_error(self) -> None:
        """WorkflowStatus should support error field."""
        from daw_agents.api.schemas import WorkflowStatus

        status = WorkflowStatus(
            id=str(uuid.uuid4()),
            status="error",
            phase="execution",
            error_message="Task execution failed: timeout",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert status.status == "error"
        assert "timeout" in str(status.error_message)


class TestApprovalRequestSchema:
    """Tests for ApprovalRequest schema."""

    def test_approval_request_approve(self) -> None:
        """ApprovalRequest should support approval action."""
        from daw_agents.api.schemas import ApprovalAction, ApprovalRequest

        request = ApprovalRequest(
            action=ApprovalAction.APPROVE,
            comment="Looks good, proceed with implementation",
        )
        assert request.action == ApprovalAction.APPROVE
        assert request.comment == "Looks good, proceed with implementation"

    def test_approval_request_reject(self) -> None:
        """ApprovalRequest should support rejection action."""
        from daw_agents.api.schemas import ApprovalAction, ApprovalRequest

        request = ApprovalRequest(
            action=ApprovalAction.REJECT,
            comment="Need to reconsider the architecture",
        )
        assert request.action == ApprovalAction.REJECT

    def test_approval_request_modify(self) -> None:
        """ApprovalRequest should support modify action with changes."""
        from daw_agents.api.schemas import ApprovalAction, ApprovalRequest

        request = ApprovalRequest(
            action=ApprovalAction.MODIFY,
            comment="Please add rate limiting",
            modifications={"add_feature": "rate_limiting"},
        )
        assert request.action == ApprovalAction.MODIFY
        assert request.modifications is not None


class TestApprovalResponseSchema:
    """Tests for ApprovalResponse schema."""

    def test_approval_response_success(self) -> None:
        """ApprovalResponse should indicate success."""
        from daw_agents.api.schemas import ApprovalResponse

        response = ApprovalResponse(
            success=True,
            workflow_id=str(uuid.uuid4()),
            new_status="executing",
            message="Workflow approved and continuing",
        )
        assert response.success is True
        assert response.new_status == "executing"


# -----------------------------------------------------------------------------
# POST /api/chat Endpoint Tests
# -----------------------------------------------------------------------------


class TestChatEndpoint:
    """Tests for POST /api/chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_requires_authentication(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """POST /api/chat should return 401 without auth."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.post(
            "/api/chat",
            json={"message": "Build a todo app"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_creates_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/chat should create workflow and return response."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                "/api/chat",
                json={"message": "Build a todo app with React"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "workflow_id" in data
        assert "message" in data
        assert "status" in data

    @pytest.mark.asyncio
    async def test_chat_continues_existing_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """POST /api/chat should continue existing workflow when workflow_id provided."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                "/api/chat",
                json={
                    "message": "Now add user authentication",
                    "workflow_id": sample_workflow_id,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        # Should either return the workflow or 404 if not found
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_chat_validates_request_body(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/chat should validate request body."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                "/api/chat",
                json={"invalid_field": "test"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 422  # Validation error


# -----------------------------------------------------------------------------
# GET /api/workflow/{id} Endpoint Tests
# -----------------------------------------------------------------------------


class TestGetWorkflowEndpoint:
    """Tests for GET /api/workflow/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_workflow_requires_authentication(
        self,
        mock_clerk_config: Any,
        sample_workflow_id: str,
    ) -> None:
        """GET /api/workflow/{id} should return 401 without auth."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.get(f"/api/workflow/{sample_workflow_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_workflow_returns_status(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """GET /api/workflow/{id} should return workflow status."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{sample_workflow_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Should either return workflow status or 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "status" in data

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """GET /api/workflow/{id} should return 404 for non-existent workflow."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)
        non_existent_id = str(uuid.uuid4())

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{non_existent_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_workflow_validates_uuid_format(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """GET /api/workflow/{id} should validate UUID format."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                "/api/workflow/invalid-uuid-format",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 422  # Validation error


# -----------------------------------------------------------------------------
# POST /api/workflow/{id}/approve Endpoint Tests
# -----------------------------------------------------------------------------


class TestApproveWorkflowEndpoint:
    """Tests for POST /api/workflow/{id}/approve endpoint."""

    @pytest.mark.asyncio
    async def test_approve_workflow_requires_authentication(
        self,
        mock_clerk_config: Any,
        sample_workflow_id: str,
    ) -> None:
        """POST /api/workflow/{id}/approve should return 401 without auth."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.post(
            f"/api/workflow/{sample_workflow_id}/approve",
            json={"action": "approve"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_approve_workflow_success(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """POST /api/workflow/{id}/approve should approve workflow."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{sample_workflow_id}/approve",
                json={"action": "approve", "comment": "LGTM"},
                headers={"Authorization": f"Bearer {token}"},
            )

        # Should either succeed or return 404 if workflow doesn't exist
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data

    @pytest.mark.asyncio
    async def test_reject_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """POST /api/workflow/{id}/approve should support rejection."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{sample_workflow_id}/approve",
                json={"action": "reject", "comment": "Needs more work"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code in [200, 404]


# -----------------------------------------------------------------------------
# DELETE /api/workflow/{id} Endpoint Tests
# -----------------------------------------------------------------------------


class TestDeleteWorkflowEndpoint:
    """Tests for DELETE /api/workflow/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_workflow_requires_authentication(
        self,
        mock_clerk_config: Any,
        sample_workflow_id: str,
    ) -> None:
        """DELETE /api/workflow/{id} should return 401 without auth."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.delete(f"/api/workflow/{sample_workflow_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_workflow_cancels_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """DELETE /api/workflow/{id} should cancel/delete workflow."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.delete(
                f"/api/workflow/{sample_workflow_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Should return 200/204 on success or 404 if not found
        assert response.status_code in [200, 204, 404]

    @pytest.mark.asyncio
    async def test_delete_workflow_not_found(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """DELETE /api/workflow/{id} should return 404 for non-existent workflow."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)
        non_existent_id = str(uuid.uuid4())

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.delete(
                f"/api/workflow/{non_existent_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 404


# -----------------------------------------------------------------------------
# WebSocket /ws/trace/{id} Endpoint Tests
# -----------------------------------------------------------------------------


class TestWebSocketTraceEndpoint:
    """Tests for WebSocket /ws/trace/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_connection_established(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """WebSocket /ws/trace/{id} should establish connection with valid auth."""
        from daw_agents.api.routes import (
            WorkflowManager,
            create_router,
            create_trace_websocket_router,
        )

        app = FastAPI()
        router = create_router(mock_clerk_config)
        ws_router = create_trace_websocket_router(mock_clerk_config)
        app.include_router(router, prefix="/api")
        app.include_router(ws_router, prefix="/ws")

        token = create_test_token(valid_jwt_payload)

        # Create a workflow first so the WebSocket can connect to it
        WorkflowManager.clear_all()
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )

        with patch(
            "daw_agents.api.routes.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            # WebSocket connection with auth token in query param
            with client.websocket_connect(
                f"/ws/trace/{workflow['id']}?token={token}"
            ) as websocket:
                # First message should be the initial state update
                initial_data = websocket.receive_json()
                assert initial_data is not None
                assert initial_data.get("type") == "state_update"

                # Send a ping and expect pong response
                websocket.send_json({"type": "ping"})
                pong_data = websocket.receive_json()
                assert pong_data is not None
                assert pong_data.get("type") == "pong"

        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_auth(
        self,
        mock_clerk_config: Any,
        sample_workflow_id: str,
    ) -> None:
        """WebSocket /ws/trace/{id} should reject invalid auth."""
        from daw_agents.api.routes import create_trace_websocket_router

        app = FastAPI()
        ws_router = create_trace_websocket_router(mock_clerk_config)
        app.include_router(ws_router, prefix="/ws")

        client = TestClient(app)
        # Try to connect without valid token
        with pytest.raises(Exception):  # Should fail to connect
            with client.websocket_connect(
                f"/ws/trace/{sample_workflow_id}?token=invalid_token"
            ):
                pass


# -----------------------------------------------------------------------------
# OpenAPI Documentation Tests
# -----------------------------------------------------------------------------


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation generation."""

    def test_openapi_schema_generated(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """App should generate OpenAPI schema."""
        from daw_agents.api.routes import create_router

        app = FastAPI(title="DAW API", version="1.0.0")
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

    def test_openapi_includes_endpoints(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """OpenAPI schema should include all API endpoints."""
        from daw_agents.api.routes import create_router

        app = FastAPI(title="DAW API", version="1.0.0")
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        paths = schema["paths"]
        assert "/api/chat" in paths
        assert "/api/workflow/{workflow_id}" in paths

    def test_openapi_includes_security_schemes(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """OpenAPI schema should include security schemes."""
        from daw_agents.api.routes import create_router

        app = FastAPI(title="DAW API", version="1.0.0")
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        # Should have security components
        assert "components" in schema
        if "securitySchemes" in schema.get("components", {}):
            assert "HTTPBearer" in schema["components"]["securitySchemes"]


# -----------------------------------------------------------------------------
# Error Handling Tests
# -----------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for API error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_422(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Invalid JSON should return 422."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                "/api/chat",
                content="not valid json",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_server_error_returns_500(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """Internal server errors should return 500."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        # Mock the planner to raise an exception
        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            with patch(
                "daw_agents.api.routes.WorkflowManager.create_workflow",
                side_effect=Exception("Internal error"),
            ):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.post(
                    "/api/chat",
                    json={"message": "Build something"},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 500


# -----------------------------------------------------------------------------
# Authorization Tests (Access Control)
# -----------------------------------------------------------------------------


class TestWorkflowOwnership:
    """Tests for workflow ownership and access control."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_users_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        create_test_token: Any,
        sample_workflow_id: str,
    ) -> None:
        """User should not be able to access another user's workflow."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create token for a different user
        current_time = int(time.time())
        other_user_payload = {
            "sub": "other_user_456",
            "exp": current_time + 3600,
            "nbf": current_time - 60,
            "iat": current_time - 60,
            "iss": "https://clerk.test.com",
            "azp": "https://allowed-origin.com",
        }
        token = create_test_token(other_user_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{sample_workflow_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Should return 403 Forbidden or 404 Not Found
        assert response.status_code in [403, 404]


# -----------------------------------------------------------------------------
# Router Configuration Tests
# -----------------------------------------------------------------------------


class TestRouterConfiguration:
    """Tests for router factory and configuration."""

    def test_create_router_returns_api_router(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """create_router should return a FastAPI APIRouter."""
        from fastapi import APIRouter

        from daw_agents.api.routes import create_router

        router = create_router(mock_clerk_config)
        assert isinstance(router, APIRouter)

    def test_create_router_with_custom_prefix(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """Router should support custom prefixes."""
        from daw_agents.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/v2/api")

        client = TestClient(app)
        # Routes should be available at custom prefix
        response = client.post("/v2/api/chat", json={"message": "test"})
        # Should fail auth but route should exist (401, not 404)
        assert response.status_code in [401, 422]


# -----------------------------------------------------------------------------
# WorkflowManager Tests
# -----------------------------------------------------------------------------


class TestWorkflowManager:
    """Tests for WorkflowManager class."""

    def test_create_workflow(self) -> None:
        """WorkflowManager should create workflows."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Build a todo app",
            context={"project_type": "web"},
        )

        assert workflow["id"] is not None
        assert workflow["user_id"] == "user_123"
        assert workflow["message"] == "Build a todo app"
        assert workflow["context"] == {"project_type": "web"}
        WorkflowManager.clear_all()

    def test_get_workflow(self) -> None:
        """WorkflowManager should retrieve workflows by ID."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        created = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )

        retrieved = WorkflowManager.get_workflow(created["id"])
        assert retrieved is not None
        assert retrieved["id"] == created["id"]
        WorkflowManager.clear_all()

    def test_get_nonexistent_workflow(self) -> None:
        """WorkflowManager should return None for nonexistent workflows."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        result = WorkflowManager.get_workflow("nonexistent-id")
        assert result is None

    def test_update_workflow(self) -> None:
        """WorkflowManager should update workflow fields."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )

        updated = WorkflowManager.update_workflow(
            workflow["id"],
            {"status": "executing", "progress": 0.5},
        )

        assert updated is not None
        assert updated["status"] == "executing"
        assert updated["progress"] == 0.5
        WorkflowManager.clear_all()

    def test_update_nonexistent_workflow(self) -> None:
        """WorkflowManager should return None when updating nonexistent workflow."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        result = WorkflowManager.update_workflow("nonexistent-id", {"status": "done"})
        assert result is None

    def test_delete_workflow(self) -> None:
        """WorkflowManager should delete workflows."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )

        deleted = WorkflowManager.delete_workflow(workflow["id"])
        assert deleted is True

        # Should be gone
        result = WorkflowManager.get_workflow(workflow["id"])
        assert result is None
        WorkflowManager.clear_all()

    def test_delete_nonexistent_workflow(self) -> None:
        """WorkflowManager should return False when deleting nonexistent workflow."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        result = WorkflowManager.delete_workflow("nonexistent-id")
        assert result is False

    def test_user_owns_workflow(self) -> None:
        """WorkflowManager should check workflow ownership."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )

        assert WorkflowManager.user_owns_workflow("user_123", workflow["id"]) is True
        assert WorkflowManager.user_owns_workflow("other_user", workflow["id"]) is False
        assert WorkflowManager.user_owns_workflow("user_123", "nonexistent") is False
        WorkflowManager.clear_all()

    def test_clear_all(self) -> None:
        """WorkflowManager should clear all workflows."""
        from daw_agents.api.routes import WorkflowManager

        WorkflowManager.clear_all()
        WorkflowManager.create_workflow(user_id="user1", message="Workflow 1")
        WorkflowManager.create_workflow(user_id="user2", message="Workflow 2")

        WorkflowManager.clear_all()

        # All should be gone
        assert WorkflowManager.get_workflow("any_id") is None


# -----------------------------------------------------------------------------
# Additional Endpoint Tests for Better Coverage
# -----------------------------------------------------------------------------


class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    @pytest.mark.asyncio
    async def test_chat_with_context(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/chat should handle context parameter."""
        from daw_agents.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                "/api/chat",
                json={
                    "message": "Build a todo app",
                    "context": {"framework": "react", "language": "typescript"},
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "workflow_id" in data
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_approve_workflow_with_modify_action(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/approve should handle modify action."""
        from daw_agents.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create a workflow first
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/approve",
                json={
                    "action": "modify",
                    "comment": "Please add rate limiting",
                    "modifications": {"add_feature": "rate_limiting"},
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "planning"
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_get_workflow_after_creation(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """GET /api/workflow/{id} should return workflow after creation."""
        from daw_agents.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create a workflow
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{workflow['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workflow["id"]
        assert data["status"] == "planning"
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_delete_existing_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """DELETE /api/workflow/{id} should delete existing workflow."""
        from daw_agents.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create a workflow
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.delete(
                f"/api/workflow/{workflow['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workflow_id"] == workflow["id"]
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_cannot_access_other_users_workflow_approve(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """User should not be able to approve another user's workflow."""
        from daw_agents.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow for one user
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )

        # Token for different user
        current_time = int(time.time())
        other_user_payload = {
            "sub": "other_user_456",
            "exp": current_time + 3600,
            "nbf": current_time - 60,
            "iat": current_time - 60,
            "iss": "https://clerk.test.com",
            "azp": "https://allowed-origin.com",
        }
        token = create_test_token(other_user_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/approve",
                json={"action": "approve"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_cannot_delete_other_users_workflow(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """User should not be able to delete another user's workflow."""
        from daw_agents.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow for one user
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )

        # Token for different user
        current_time = int(time.time())
        other_user_payload = {
            "sub": "other_user_456",
            "exp": current_time + 3600,
            "nbf": current_time - 60,
            "iat": current_time - 60,
            "iss": "https://clerk.test.com",
            "azp": "https://allowed-origin.com",
        }
        token = create_test_token(other_user_payload)

        with patch(
            "daw_agents.auth.dependencies.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.delete(
                f"/api/workflow/{workflow['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403
        WorkflowManager.clear_all()
