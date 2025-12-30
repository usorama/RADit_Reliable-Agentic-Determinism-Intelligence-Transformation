"""
FastAPI route endpoints for DAW Workbench.

This module defines the API routes:
- POST /api/chat: Send message to Planner agent
- GET /api/workflow/{id}: Get workflow status
- POST /api/workflow/{id}/approve: Human approval for workflow
- DELETE /api/workflow/{id}: Cancel/delete workflow
- WebSocket /ws/trace/{id}: Real-time updates

All routes are protected by Clerk auth middleware.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from daw_agents.api.schemas import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalResponse,
    ChatRequest,
    ChatResponse,
    DeleteWorkflowResponse,
    WebSocketMessage,
    WorkflowStatus,
    WorkflowStatusEnum,
)
from daw_agents.auth.clerk import ClerkConfig, ClerkJWTVerifier, ClerkUser

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI docs
security = HTTPBearer()


# -----------------------------------------------------------------------------
# Workflow Manager (In-Memory Storage for MVP)
# -----------------------------------------------------------------------------


class WorkflowManager:
    """Manages workflow state and operations.

    This is an in-memory implementation for MVP.
    Production implementation should use Redis/Neo4j persistence.
    """

    _workflows: dict[str, dict[str, Any]] = {}
    _user_workflows: dict[str, list[str]] = {}

    @classmethod
    def create_workflow(
        cls,
        user_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new workflow.

        Args:
            user_id: ID of the user creating the workflow
            message: Initial message from user
            context: Optional context dictionary

        Returns:
            Created workflow data
        """
        workflow_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        workflow = {
            "id": workflow_id,
            "user_id": user_id,
            "status": WorkflowStatusEnum.PLANNING,
            "phase": "interview",
            "message": message,
            "context": context,
            "progress": 0.0,
            "tasks_total": 0,
            "tasks_completed": 0,
            "current_task": "Analyzing requirements",
            "created_at": now,
            "updated_at": now,
            "error_message": None,
        }

        cls._workflows[workflow_id] = workflow

        # Track user's workflows
        if user_id not in cls._user_workflows:
            cls._user_workflows[user_id] = []
        cls._user_workflows[user_id].append(workflow_id)

        logger.info("Created workflow %s for user %s", workflow_id, user_id)
        return workflow

    @classmethod
    def get_workflow(cls, workflow_id: str) -> dict[str, Any] | None:
        """Get a workflow by ID.

        Args:
            workflow_id: The workflow ID

        Returns:
            Workflow data or None if not found
        """
        return cls._workflows.get(workflow_id)

    @classmethod
    def update_workflow(
        cls, workflow_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update a workflow.

        Args:
            workflow_id: The workflow ID
            updates: Fields to update

        Returns:
            Updated workflow data or None if not found
        """
        workflow = cls._workflows.get(workflow_id)
        if workflow is None:
            return None

        workflow.update(updates)
        workflow["updated_at"] = datetime.now(UTC)
        return workflow

    @classmethod
    def delete_workflow(cls, workflow_id: str) -> bool:
        """Delete a workflow.

        Args:
            workflow_id: The workflow ID

        Returns:
            True if deleted, False if not found
        """
        workflow = cls._workflows.pop(workflow_id, None)
        if workflow is None:
            return False

        # Remove from user's workflow list
        user_id = workflow.get("user_id")
        if user_id and user_id in cls._user_workflows:
            cls._user_workflows[user_id] = [
                w for w in cls._user_workflows[user_id] if w != workflow_id
            ]

        logger.info("Deleted workflow %s", workflow_id)
        return True

    @classmethod
    def user_owns_workflow(cls, user_id: str, workflow_id: str) -> bool:
        """Check if a user owns a workflow.

        Args:
            user_id: The user ID
            workflow_id: The workflow ID

        Returns:
            True if the user owns the workflow
        """
        workflow = cls._workflows.get(workflow_id)
        if workflow is None:
            return False
        return workflow.get("user_id") == user_id

    @classmethod
    def clear_all(cls) -> None:
        """Clear all workflows (for testing)."""
        cls._workflows.clear()
        cls._user_workflows.clear()


# -----------------------------------------------------------------------------
# Authentication Dependency
# -----------------------------------------------------------------------------


def create_auth_dependency(config: ClerkConfig) -> Any:
    """Create a FastAPI dependency for Clerk authentication.

    Args:
        config: Clerk configuration

    Returns:
        Dependency function that returns ClerkUser
    """
    verifier = ClerkJWTVerifier(config)

    async def verify_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> ClerkUser:
        """Verify JWT token and return user.

        Args:
            credentials: Bearer token credentials

        Returns:
            Verified ClerkUser

        Raises:
            HTTPException: 401 if authentication fails
        """
        try:
            user = await verifier.verify_token(credentials.credentials)
            return user
        except Exception as e:
            logger.warning("Authentication failed: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    return verify_user


# -----------------------------------------------------------------------------
# Router Factory
# -----------------------------------------------------------------------------


def create_router(config: ClerkConfig) -> APIRouter:
    """Create the API router with all endpoints.

    Args:
        config: Clerk configuration for authentication

    Returns:
        Configured APIRouter instance
    """
    router = APIRouter(tags=["workflows"])
    verify_user = create_auth_dependency(config)

    # -------------------------------------------------------------------------
    # POST /chat - Send message to Planner
    # -------------------------------------------------------------------------

    @router.post(
        "/chat",
        response_model=ChatResponse,
        summary="Send message to Planner agent",
        description="Send a message to the Planner agent to create or continue a workflow.",
        responses={
            200: {"description": "Successful response with workflow status"},
            401: {"description": "Authentication required"},
            422: {"description": "Validation error"},
            500: {"description": "Internal server error"},
        },
    )
    async def chat(
        request: ChatRequest,
        user: ClerkUser = Depends(verify_user),
    ) -> ChatResponse:
        """Handle chat message to Planner agent.

        Args:
            request: Chat request with message
            user: Authenticated user

        Returns:
            Chat response with workflow status
        """
        try:
            # Check if continuing existing workflow
            if request.workflow_id:
                workflow = WorkflowManager.get_workflow(request.workflow_id)
                if workflow is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Workflow {request.workflow_id} not found",
                    )
                # Verify ownership
                if not WorkflowManager.user_owns_workflow(
                    user.user_id, request.workflow_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have access to this workflow",
                    )
                # Update workflow with new message
                WorkflowManager.update_workflow(
                    request.workflow_id,
                    {"message": request.message, "context": request.context},
                )
            else:
                # Create new workflow
                workflow = WorkflowManager.create_workflow(
                    user_id=user.user_id,
                    message=request.message,
                    context=request.context,
                )

            # In production, this would trigger the Planner agent
            # For now, return the workflow status
            return ChatResponse(
                workflow_id=workflow["id"],
                message="I'll help you with that. Let me analyze your requirements.",
                status=workflow["status"],
                tasks_generated=workflow.get("tasks_total"),
                phase=workflow.get("phase"),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Chat endpoint error: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing your request",
            ) from e

    # -------------------------------------------------------------------------
    # GET /workflow/{workflow_id} - Get workflow status
    # -------------------------------------------------------------------------

    @router.get(
        "/workflow/{workflow_id}",
        response_model=WorkflowStatus,
        summary="Get workflow status",
        description="Retrieve the current status of a workflow.",
        responses={
            200: {"description": "Workflow status"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
            422: {"description": "Invalid workflow ID format"},
        },
    )
    async def get_workflow(
        workflow_id: str,
        user: ClerkUser = Depends(verify_user),
    ) -> WorkflowStatus:
        """Get workflow status.

        Args:
            workflow_id: The workflow ID (UUID format)
            user: Authenticated user

        Returns:
            Workflow status

        Raises:
            HTTPException: 404 if not found, 403 if not owner
        """
        # Validate UUID format
        try:
            uuid.UUID(workflow_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid workflow ID format. Expected UUID.",
            ) from e

        workflow = WorkflowManager.get_workflow(workflow_id)
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Verify ownership
        if not WorkflowManager.user_owns_workflow(user.user_id, workflow_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workflow",
            )

        return WorkflowStatus(
            id=workflow["id"],
            status=workflow["status"],
            phase=workflow.get("phase"),
            progress=workflow.get("progress"),
            tasks_total=workflow.get("tasks_total"),
            tasks_completed=workflow.get("tasks_completed"),
            current_task=workflow.get("current_task"),
            created_at=workflow["created_at"],
            updated_at=workflow["updated_at"],
            error_message=workflow.get("error_message"),
            user_id=workflow.get("user_id"),
        )

    # -------------------------------------------------------------------------
    # POST /workflow/{workflow_id}/approve - Human approval
    # -------------------------------------------------------------------------

    @router.post(
        "/workflow/{workflow_id}/approve",
        response_model=ApprovalResponse,
        summary="Approve, reject, or modify a workflow",
        description="Submit human approval decision for a workflow awaiting approval.",
        responses={
            200: {"description": "Approval action processed"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def approve_workflow(
        workflow_id: str,
        request: ApprovalRequest,
        user: ClerkUser = Depends(verify_user),
    ) -> ApprovalResponse:
        """Handle workflow approval.

        Args:
            workflow_id: The workflow ID
            request: Approval request with action and optional comment
            user: Authenticated user

        Returns:
            Approval response with new status
        """
        # Validate UUID format
        try:
            uuid.UUID(workflow_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid workflow ID format. Expected UUID.",
            ) from e

        workflow = WorkflowManager.get_workflow(workflow_id)
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Verify ownership
        if not WorkflowManager.user_owns_workflow(user.user_id, workflow_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workflow",
            )

        # Process approval action
        if request.action == ApprovalAction.APPROVE:
            new_status = WorkflowStatusEnum.EXECUTING
            message = "Workflow approved. Starting execution."
        elif request.action == ApprovalAction.REJECT:
            new_status = WorkflowStatusEnum.CANCELLED
            message = "Workflow rejected and cancelled."
        elif request.action == ApprovalAction.MODIFY:
            new_status = WorkflowStatusEnum.PLANNING
            message = "Workflow modifications requested. Returning to planning phase."
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid approval action",
            )

        # Update workflow
        WorkflowManager.update_workflow(
            workflow_id,
            {
                "status": new_status,
                "approval_comment": request.comment,
                "approval_action": request.action,
            },
        )

        return ApprovalResponse(
            success=True,
            workflow_id=workflow_id,
            new_status=new_status.value,
            message=message,
        )

    # -------------------------------------------------------------------------
    # DELETE /workflow/{workflow_id} - Cancel/delete workflow
    # -------------------------------------------------------------------------

    @router.delete(
        "/workflow/{workflow_id}",
        response_model=DeleteWorkflowResponse,
        summary="Cancel or delete a workflow",
        description="Cancel an active workflow or delete a completed/failed one.",
        responses={
            200: {"description": "Workflow deleted/cancelled"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def delete_workflow(
        workflow_id: str,
        user: ClerkUser = Depends(verify_user),
    ) -> DeleteWorkflowResponse:
        """Delete or cancel a workflow.

        Args:
            workflow_id: The workflow ID
            user: Authenticated user

        Returns:
            Delete response

        Raises:
            HTTPException: 404 if not found, 403 if not owner
        """
        # Validate UUID format
        try:
            uuid.UUID(workflow_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid workflow ID format. Expected UUID.",
            ) from e

        workflow = WorkflowManager.get_workflow(workflow_id)
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Verify ownership
        if not WorkflowManager.user_owns_workflow(user.user_id, workflow_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workflow",
            )

        # Delete workflow
        WorkflowManager.delete_workflow(workflow_id)

        return DeleteWorkflowResponse(
            success=True,
            workflow_id=workflow_id,
            message="Workflow deleted successfully",
        )

    return router


# -----------------------------------------------------------------------------
# WebSocket Route (Separate Router for /ws prefix)
# -----------------------------------------------------------------------------


def create_trace_websocket_router(config: ClerkConfig) -> APIRouter:
    """Create the WebSocket router for real-time trace updates.

    This provides authenticated WebSocket access to workflow traces.
    For general streaming, use the websocket module's create_websocket_router.

    Args:
        config: Clerk configuration for authentication

    Returns:
        Configured APIRouter with WebSocket endpoint
    """
    ws_router = APIRouter(tags=["websocket"])
    verifier = ClerkJWTVerifier(config)

    @ws_router.websocket("/trace/{workflow_id}")
    async def websocket_trace(
        websocket: WebSocket,
        workflow_id: str,
        token: str = Query(..., description="JWT token for authentication"),
    ) -> None:
        """WebSocket endpoint for real-time workflow updates.

        Args:
            websocket: WebSocket connection
            workflow_id: The workflow ID to subscribe to
            token: JWT token for authentication (passed as query parameter)
        """
        # Validate token
        try:
            user = await verifier.verify_token(token)
        except Exception as e:
            logger.warning("WebSocket auth failed: %s", str(e))
            await websocket.close(code=4001, reason="Authentication failed")
            return

        # Validate workflow exists and user has access
        workflow = WorkflowManager.get_workflow(workflow_id)
        if workflow is None:
            await websocket.close(code=4004, reason="Workflow not found")
            return

        if not WorkflowManager.user_owns_workflow(user.user_id, workflow_id):
            await websocket.close(code=4003, reason="Access denied")
            return

        # Accept connection
        await websocket.accept()
        logger.info(
            "WebSocket connected: workflow=%s user=%s", workflow_id, user.user_id
        )

        try:
            # Send initial state
            initial_message = WebSocketMessage(
                type="state_update",
                data={
                    "workflow_id": workflow_id,
                    "status": str(workflow["status"]),
                    "phase": workflow.get("phase"),
                },
            )
            await websocket.send_json(initial_message.model_dump(mode="json"))

            # Listen for messages
            while True:
                data = await websocket.receive_json()

                # Handle ping/pong
                if data.get("type") == "ping":
                    pong_message = WebSocketMessage(type="pong", data={"received": True})
                    await websocket.send_json(pong_message.model_dump(mode="json"))
                else:
                    # Echo back other messages for now
                    echo_message = WebSocketMessage(type="echo", data=data)
                    await websocket.send_json(echo_message.model_dump(mode="json"))

        except Exception as e:
            logger.debug("WebSocket disconnected: %s", str(e))
        finally:
            logger.info(
                "WebSocket closed: workflow=%s user=%s", workflow_id, user.user_id
            )

    return ws_router


__all__ = [
    "create_router",
    "create_trace_websocket_router",
    "WorkflowManager",
]
