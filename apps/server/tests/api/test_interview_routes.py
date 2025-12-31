"""
Tests for Interview API endpoints (INTERACT-001).

Tests for:
- GET /api/workflow/{id}/interview-status
- POST /api/workflow/{id}/interview-answer
"""

import time
import uuid
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
def mock_clerk_config() -> Any:
    """Create mock Clerk configuration."""
    from daw_server.auth.clerk import ClerkConfig

    return ClerkConfig(
        secret_key="sk_test_abc123",
        publishable_key="pk_test_xyz789",
        jwks_url="https://clerk.test.com/.well-known/jwks.json",
        authorized_parties=["https://allowed-origin.com"],
    )


@pytest.fixture
def sample_interview_state() -> dict[str, Any]:
    """Create sample interview state."""
    return {
        "workflow_id": "wf-123",
        "questions": [
            {
                "id": "Q-001",
                "type": "text",
                "text": "What features do you need?",
                "required": True,
                "context": "Understanding requirements",
            },
            {
                "id": "Q-002",
                "type": "multi_choice",
                "text": "What is your tech stack?",
                "options": ["React", "Vue", "Angular"],
                "required": True,
            },
            {
                "id": "Q-003",
                "type": "checkbox",
                "text": "Which platforms?",
                "options": ["Web", "Mobile", "Desktop"],
                "required": False,
            },
        ],
        "answers": {},
        "current_index": 0,
        "completed": False,
    }


# -----------------------------------------------------------------------------
# Interview Schema Tests
# -----------------------------------------------------------------------------


class TestInterviewSchemas:
    """Tests for interview-related schemas."""

    def test_question_schema_text(self) -> None:
        """QuestionSchema should handle text questions."""
        from daw_server.api.schemas import QuestionSchema, QuestionTypeEnum

        question = QuestionSchema(
            id="Q-001",
            type=QuestionTypeEnum.TEXT,
            text="What do you need?",
            required=True,
            context="Understanding requirements",
        )
        assert question.id == "Q-001"
        assert question.type == QuestionTypeEnum.TEXT
        assert question.options is None

    def test_question_schema_multi_choice(self) -> None:
        """QuestionSchema should handle multi-choice questions."""
        from daw_server.api.schemas import QuestionSchema, QuestionTypeEnum

        question = QuestionSchema(
            id="Q-002",
            type=QuestionTypeEnum.MULTI_CHOICE,
            text="Choose your stack",
            options=["React", "Vue", "Angular"],
            required=True,
        )
        assert question.type == QuestionTypeEnum.MULTI_CHOICE
        assert len(question.options) == 3

    def test_interview_answer_request_string(self) -> None:
        """InterviewAnswerRequest should accept string answers."""
        from daw_server.api.schemas import InterviewAnswerRequest

        request = InterviewAnswerRequest(
            question_id="Q-001",
            answer="My detailed answer",
            skip_remaining=False,
        )
        assert request.question_id == "Q-001"
        assert request.answer == "My detailed answer"

    def test_interview_answer_request_list(self) -> None:
        """InterviewAnswerRequest should accept list answers for checkbox."""
        from daw_server.api.schemas import InterviewAnswerRequest

        request = InterviewAnswerRequest(
            question_id="Q-003",
            answer=["Web", "Mobile"],
            skip_remaining=False,
        )
        assert isinstance(request.answer, list)
        assert len(request.answer) == 2

    def test_interview_answer_response(self) -> None:
        """InterviewAnswerResponse should have all fields."""
        from daw_server.api.schemas import (
            InterviewAnswerResponse,
            QuestionSchema,
            QuestionTypeEnum,
        )

        next_q = QuestionSchema(
            id="Q-002",
            type=QuestionTypeEnum.TEXT,
            text="Next question",
        )
        response = InterviewAnswerResponse(
            next_question=next_q,
            complete=False,
            answers_count=1,
            total_questions=3,
        )
        assert response.next_question is not None
        assert response.complete is False

    def test_interview_status_response(self) -> None:
        """InterviewStatusResponse should have all fields."""
        from daw_server.api.schemas import (
            InterviewStatusResponse,
            QuestionSchema,
            QuestionTypeEnum,
        )

        questions = [
            QuestionSchema(id="Q-001", type=QuestionTypeEnum.TEXT, text="Q1"),
        ]
        response = InterviewStatusResponse(
            current_question=0,
            total_questions=1,
            questions=questions,
            answers={},
            completed=False,
        )
        assert response.current_question == 0
        assert len(response.questions) == 1


# -----------------------------------------------------------------------------
# GET /api/workflow/{id}/interview-status Tests
# -----------------------------------------------------------------------------


class TestGetInterviewStatusEndpoint:
    """Tests for GET /api/workflow/{id}/interview-status endpoint."""

    @pytest.mark.asyncio
    async def test_get_interview_status_requires_auth(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """GET /api/workflow/{id}/interview-status should require auth."""
        from daw_server.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        workflow_id = str(uuid.uuid4())
        response = client.get(f"/api/workflow/{workflow_id}/interview-status")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_interview_status_returns_empty_when_no_interview(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """GET /api/workflow/{id}/interview-status returns empty when no interview."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow without interview state
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{workflow['id']}/interview-status",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_questions"] == 0
        assert data["questions"] == []
        assert data["completed"] is False
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_get_interview_status_returns_interview_state(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_interview_state: dict[str, Any],
    ) -> None:
        """GET /api/workflow/{id}/interview-status returns interview state."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow with interview state
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": sample_interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{workflow['id']}/interview-status",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_questions"] == 3
        assert len(data["questions"]) == 3
        assert data["completed"] is False
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_get_interview_status_validates_uuid(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """GET /api/workflow/{id}/interview-status validates UUID format."""
        from daw_server.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                "/api/workflow/invalid-uuid/interview-status",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_interview_status_not_found(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """GET /api/workflow/{id}/interview-status returns 404 for unknown workflow."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        token = create_test_token(valid_jwt_payload)
        unknown_id = str(uuid.uuid4())

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{unknown_id}/interview-status",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 404
        WorkflowManager.clear_all()


# -----------------------------------------------------------------------------
# POST /api/workflow/{id}/interview-answer Tests
# -----------------------------------------------------------------------------


class TestSubmitInterviewAnswerEndpoint:
    """Tests for POST /api/workflow/{id}/interview-answer endpoint."""

    @pytest.mark.asyncio
    async def test_submit_answer_requires_auth(
        self,
        mock_clerk_config: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer should require auth."""
        from daw_server.api.routes import create_router

        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        client = TestClient(app)
        workflow_id = str(uuid.uuid4())
        response = client.post(
            f"/api/workflow/{workflow_id}/interview-answer",
            json={"question_id": "Q-001", "answer": "Test"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_submit_answer_no_interview(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer returns 400 when no interview."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow without interview state
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-001", "answer": "Test answer"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 400
        assert "No interview in progress" in response.json()["detail"]
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_success(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_interview_state: dict[str, Any],
    ) -> None:
        """POST /api/workflow/{id}/interview-answer submits answer successfully."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow with interview state
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": sample_interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-001", "answer": "I need CRUD features"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answers_count"] == 1
        assert data["total_questions"] == 3
        assert data["complete"] is False
        assert data["next_question"] is not None
        assert data["next_question"]["id"] == "Q-002"
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_invalid_question_id(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
        sample_interview_state: dict[str, Any],
    ) -> None:
        """POST /api/workflow/{id}/interview-answer returns 400 for invalid question."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow with interview state
        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": sample_interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-999", "answer": "Answer"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 400
        assert "not found in interview" in response.json()["detail"]
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_completes_interview(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer completes when all required answered."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create interview with just one required question
        interview_state = {
            "workflow_id": "wf-123",
            "questions": [
                {
                    "id": "Q-001",
                    "type": "text",
                    "text": "Only question",
                    "required": True,
                },
            ],
            "answers": {},
            "current_index": 0,
            "completed": False,
        }

        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-001", "answer": "Final answer"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["complete"] is True
        assert data["next_question"] is None
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_list_for_checkbox(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer accepts list for checkbox."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        interview_state = {
            "workflow_id": "wf-123",
            "questions": [
                {
                    "id": "Q-001",
                    "type": "checkbox",
                    "text": "Select platforms",
                    "options": ["Web", "Mobile", "Desktop"],
                    "required": True,
                },
            ],
            "answers": {},
            "current_index": 0,
            "completed": False,
        }

        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-001", "answer": ["Web", "Mobile"]},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["complete"] is True
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_skip_remaining_success(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer skip_remaining works."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        interview_state = {
            "workflow_id": "wf-123",
            "questions": [
                {
                    "id": "Q-001",
                    "type": "text",
                    "text": "Required Q",
                    "required": True,
                },
                {
                    "id": "Q-002",
                    "type": "text",
                    "text": "Optional Q",
                    "required": False,
                },
            ],
            "answers": {"Q-001": "Answered"},
            "current_index": 1,
            "completed": False,
        }

        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={
                    "question_id": "Q-002",
                    "answer": "Optional answer",
                    "skip_remaining": True,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["complete"] is True
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_skip_remaining_fails_required_unanswered(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer skip fails if required unanswered."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        interview_state = {
            "workflow_id": "wf-123",
            "questions": [
                {
                    "id": "Q-001",
                    "type": "text",
                    "text": "Required Q1",
                    "required": True,
                },
                {
                    "id": "Q-002",
                    "type": "text",
                    "text": "Required Q2",
                    "required": True,
                },
            ],
            "answers": {},
            "current_index": 0,
            "completed": False,
        }

        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={
                    "question_id": "Q-001",
                    "answer": "First answer",
                    "skip_remaining": True,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 400
        assert "Cannot skip" in response.json()["detail"]
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_submit_answer_already_completed_interview(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        valid_jwt_payload: dict[str, Any],
        create_test_token: Any,
    ) -> None:
        """POST /api/workflow/{id}/interview-answer returns 400 when already completed."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        interview_state = {
            "workflow_id": "wf-123",
            "questions": [
                {
                    "id": "Q-001",
                    "type": "text",
                    "text": "Question",
                    "required": True,
                },
            ],
            "answers": {"Q-001": "Already answered"},
            "current_index": 1,
            "completed": True,
        }

        workflow = WorkflowManager.create_workflow(
            user_id="user_test123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": interview_state},
        )

        token = create_test_token(valid_jwt_payload)

        with patch(
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-001", "answer": "New answer"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"]
        WorkflowManager.clear_all()


# -----------------------------------------------------------------------------
# Access Control Tests
# -----------------------------------------------------------------------------


class TestInterviewAccessControl:
    """Tests for interview endpoint access control."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_user_interview_status(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        create_test_token: Any,
        sample_interview_state: dict[str, Any],
    ) -> None:
        """User cannot access another user's interview status."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow for user_123
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": sample_interview_state},
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
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.get(
                f"/api/workflow/{workflow['id']}/interview-status",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403
        WorkflowManager.clear_all()

    @pytest.mark.asyncio
    async def test_cannot_submit_answer_to_other_user_interview(
        self,
        mock_clerk_config: Any,
        mock_jwks: dict[str, Any],
        create_test_token: Any,
        sample_interview_state: dict[str, Any],
    ) -> None:
        """User cannot submit answer to another user's interview."""
        from daw_server.api.routes import WorkflowManager, create_router

        WorkflowManager.clear_all()
        app = FastAPI()
        router = create_router(mock_clerk_config)
        app.include_router(router, prefix="/api")

        # Create workflow for user_123
        workflow = WorkflowManager.create_workflow(
            user_id="user_123",
            message="Test workflow",
        )
        WorkflowManager.update_workflow(
            workflow["id"],
            {"interview_state": sample_interview_state},
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
            "daw_server.auth.clerk.ClerkJWTVerifier._fetch_jwks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_jwks

            client = TestClient(app)
            response = client.post(
                f"/api/workflow/{workflow['id']}/interview-answer",
                json={"question_id": "Q-001", "answer": "Attempted answer"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403
        WorkflowManager.clear_all()
