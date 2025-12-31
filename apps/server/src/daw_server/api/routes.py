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

from daw_server.api.schemas import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalResponse,
    ChatRequest,
    ChatResponse,
    DeleteWorkflowResponse,
    Dependency,
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewStatusResponse,
    KanbanBoardResponse,
    KanbanColumnEnum,
    KanbanColumnInfo,
    KanbanStats,
    KanbanTask,
    KanbanUpdateRequest,
    KanbanUpdateResponse,
    Phase,
    PRDReviewAction,
    PRDReviewRequest,
    PRDReviewResponse,
    QuestionSchema,
    QuestionTypeEnum,
    Story,
    StoryPriority,
    Task,
    TaskComplexity,
    TaskPriorityEnum,
    TaskReviewAction,
    TaskReviewRequest,
    TaskReviewResponse,
    TasksListResponse,
    TaskType,
    WebSocketMessage,
    WorkflowStatus,
    WorkflowStatusEnum,
)
from daw_server.auth.clerk import ClerkConfig, ClerkJWTVerifier, ClerkUser

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
    # POST /workflow/{workflow_id}/prd-review - PRD approval gate
    # -------------------------------------------------------------------------

    @router.post(
        "/workflow/{workflow_id}/prd-review",
        response_model=PRDReviewResponse,
        summary="Review the generated PRD",
        description="Approve, reject, or request modifications to the generated PRD before task execution begins.",
        responses={
            200: {"description": "PRD review action processed"},
            400: {"description": "Invalid action or workflow not awaiting PRD approval"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def review_prd(
        workflow_id: str,
        request: PRDReviewRequest,
        user: ClerkUser = Depends(verify_user),
    ) -> PRDReviewResponse:
        """Handle PRD review action (approve, reject, modify).

        This is the human-in-the-loop checkpoint for PRD approval.
        Users must review and approve the PRD before the system proceeds
        to task decomposition and execution.

        Args:
            workflow_id: The workflow ID
            request: PRD review request with action and optional feedback
            user: Authenticated user

        Returns:
            PRD review response with new status

        Raises:
            HTTPException: 400 if workflow not awaiting PRD approval
            HTTPException: 403 if not owner
            HTTPException: 404 if not found
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

        # Verify workflow is in AWAITING_PRD_APPROVAL status
        current_status = workflow.get("status")
        if current_status != WorkflowStatusEnum.AWAITING_PRD_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow is not awaiting PRD approval. Current status: {current_status}",
            )

        # Validate feedback is provided for reject/modify actions
        if request.action in [PRDReviewAction.REJECT, PRDReviewAction.MODIFY]:
            if not request.feedback or not request.feedback.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feedback is required for {request.action.value} action",
                )

        # Process PRD review action
        now = datetime.now(UTC)

        if request.action == PRDReviewAction.APPROVE:
            new_status = WorkflowStatusEnum.EXECUTING
            message = "PRD approved. Proceeding to task execution."
            prd = workflow.get("prd")
        elif request.action == PRDReviewAction.REJECT:
            new_status = WorkflowStatusEnum.PLANNING
            message = "PRD rejected. Returning to interview phase with feedback."
            prd = None
        elif request.action == PRDReviewAction.MODIFY:
            new_status = WorkflowStatusEnum.PLANNING
            message = "PRD modification requested. Regenerating with feedback."
            prd = workflow.get("prd")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PRD review action",
            )

        # Log the audit entry
        audit_log = workflow.get("audit_log", [])
        audit_entry = {
            "timestamp": now.isoformat(),
            "user_id": user.user_id,
            "action": f"prd_{request.action.value}",
            "artifact_type": "prd",
            "feedback": request.feedback,
            "previous_status": str(current_status),
            "new_status": new_status.value,
        }
        audit_log.append(audit_entry)

        # Update workflow
        WorkflowManager.update_workflow(
            workflow_id,
            {
                "status": new_status,
                "prd_review_action": request.action.value,
                "prd_review_feedback": request.feedback,
                "prd_review_timestamp": now.isoformat(),
                "prd_review_user_id": user.user_id,
                "audit_log": audit_log,
            },
        )

        logger.info(
            "PRD review action: workflow=%s action=%s user=%s",
            workflow_id,
            request.action.value,
            user.user_id,
        )

        return PRDReviewResponse(
            success=True,
            status=new_status,
            prd=prd,
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

    # -------------------------------------------------------------------------
    # GET /workflow/{workflow_id}/tasks - Get workflow tasks
    # -------------------------------------------------------------------------

    @router.get(
        "/workflow/{workflow_id}/tasks",
        response_model=TasksListResponse,
        summary="Get workflow tasks",
        description="Retrieve the decomposed tasks for a workflow.",
        responses={
            200: {"description": "Task list with phases, stories, and dependencies"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def get_workflow_tasks(
        workflow_id: str,
        user: ClerkUser = Depends(verify_user),
    ) -> TasksListResponse:
        """Get decomposed tasks for a workflow.

        Args:
            workflow_id: The workflow ID (UUID format)
            user: Authenticated user

        Returns:
            TasksListResponse with phases, stories, tasks, and dependencies
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

        # Get tasks from workflow storage
        # For MVP, return mock data structure until orchestrator produces real tasks
        stored_tasks = workflow.get("tasks", None)
        if stored_tasks is not None:
            return TasksListResponse(**stored_tasks)

        # Return mock data for development/testing
        # In production, orchestrator populates these fields
        mock_tasks = _generate_mock_tasks(workflow_id)
        return mock_tasks

    # -------------------------------------------------------------------------
    # POST /workflow/{workflow_id}/tasks-review - Review tasks
    # -------------------------------------------------------------------------

    @router.post(
        "/workflow/{workflow_id}/tasks-review",
        response_model=TaskReviewResponse,
        summary="Review workflow tasks",
        description="Approve or reject the decomposed tasks for a workflow.",
        responses={
            200: {"description": "Task review processed"},
            400: {"description": "Invalid request"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def review_workflow_tasks(
        workflow_id: str,
        request: TaskReviewRequest,
        user: ClerkUser = Depends(verify_user),
    ) -> TaskReviewResponse:
        """Review and approve/reject workflow tasks.

        Args:
            workflow_id: The workflow ID (UUID format)
            request: TaskReviewRequest with action and optional feedback
            user: Authenticated user

        Returns:
            TaskReviewResponse with new status
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

        # Validate workflow is in correct status
        current_status = workflow.get("status")
        if current_status != WorkflowStatusEnum.AWAITING_TASK_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow is not awaiting task approval. Current status: {current_status}",
            )

        # Process review action
        if request.action == TaskReviewAction.APPROVE:
            new_status = WorkflowStatusEnum.EXECUTING
            message = "Tasks approved. Starting execution."
        elif request.action == TaskReviewAction.REJECT:
            if not request.feedback:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Feedback is required when rejecting tasks.",
                )
            new_status = WorkflowStatusEnum.PLANNING
            message = "Tasks rejected. Returning to planning with feedback."
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid review action",
            )

        # Update workflow
        WorkflowManager.update_workflow(
            workflow_id,
            {
                "status": new_status,
                "task_review_feedback": request.feedback,
                "task_review_action": request.action,
            },
        )

        return TaskReviewResponse(
            success=True,
            workflow_id=workflow_id,
            status=new_status,
            message=message,
        )

    # -------------------------------------------------------------------------
    # GET /workflow/{workflow_id}/kanban - Get Kanban board state
    # -------------------------------------------------------------------------

    @router.get(
        "/workflow/{workflow_id}/kanban",
        response_model=KanbanBoardResponse,
        summary="Get Kanban board state",
        description="Retrieve the current Kanban board state for a workflow.",
        responses={
            200: {"description": "Kanban board state"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def get_kanban_board(
        workflow_id: str,
        user: ClerkUser = Depends(verify_user),
    ) -> KanbanBoardResponse:
        """Get Kanban board state for a workflow.

        Args:
            workflow_id: The workflow ID (UUID format)
            user: Authenticated user

        Returns:
            KanbanBoardResponse with columns, tasks, and stats
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

        # Get Kanban data from workflow storage or generate mock
        kanban_data = workflow.get("kanban_tasks")
        if kanban_data is not None:
            return KanbanBoardResponse(**kanban_data)

        # Generate mock Kanban board from tasks
        return _generate_kanban_board(workflow_id, workflow)

    # -------------------------------------------------------------------------
    # PATCH /workflow/{workflow_id}/kanban/{task_id} - Update task position
    # -------------------------------------------------------------------------

    @router.patch(
        "/workflow/{workflow_id}/kanban/{task_id}",
        response_model=KanbanUpdateResponse,
        summary="Update task position on Kanban board",
        description="Move a task to a different column or update its priority.",
        responses={
            200: {"description": "Task updated successfully"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow or task not found"},
        },
    )
    async def update_kanban_task(
        workflow_id: str,
        task_id: str,
        request: KanbanUpdateRequest,
        user: ClerkUser = Depends(verify_user),
    ) -> KanbanUpdateResponse:
        """Update a task's position on the Kanban board.

        Args:
            workflow_id: The workflow ID (UUID format)
            task_id: The task ID to update
            request: KanbanUpdateRequest with new column and optional priority
            user: Authenticated user

        Returns:
            KanbanUpdateResponse with updated task
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

        # Get or generate Kanban data
        kanban_data = workflow.get("kanban_tasks")
        if kanban_data is None:
            # Generate initial Kanban board
            kanban_response = _generate_kanban_board(workflow_id, workflow)
            kanban_data = {
                "tasks": [t.model_dump(mode="json") for t in kanban_response.tasks],
            }
            workflow["kanban_tasks"] = kanban_data

        # Find and update the task
        tasks = kanban_data.get("tasks", [])
        task_found = False
        updated_task = None

        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                task_found = True
                # Update column
                task["column"] = request.column.value
                # Update priority if provided
                if request.priority is not None:
                    task["priority"] = request.priority.value
                # Update timestamp
                task["updated_at"] = datetime.now(UTC).isoformat()
                updated_task = KanbanTask(**task)
                tasks[i] = task
                break

        if not task_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found in workflow {workflow_id}",
            )

        # Save updated Kanban data
        kanban_data["tasks"] = tasks
        WorkflowManager.update_workflow(workflow_id, {"kanban_tasks": kanban_data})

        return KanbanUpdateResponse(
            success=True,
            task=updated_task,
            message=f"Task moved to {request.column.value}",
        )

    # -------------------------------------------------------------------------
    # GET /workflow/{workflow_id}/interview-status - Get interview status
    # -------------------------------------------------------------------------

    @router.get(
        "/workflow/{workflow_id}/interview-status",
        response_model=InterviewStatusResponse,
        summary="Get interview status",
        description="Retrieve the current state of the requirements interview.",
        responses={
            200: {"description": "Interview status"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found or no interview in progress"},
        },
    )
    async def get_interview_status(
        workflow_id: str,
        user: ClerkUser = Depends(verify_user),
    ) -> InterviewStatusResponse:
        """Get the current interview status for a workflow.

        Args:
            workflow_id: The workflow ID (UUID format)
            user: Authenticated user

        Returns:
            InterviewStatusResponse with current interview state
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

        # Get interview state from workflow
        interview_state = workflow.get("interview_state")
        if interview_state is None:
            # No interview in progress - return empty state
            return InterviewStatusResponse(
                current_question=0,
                total_questions=0,
                questions=[],
                answers={},
                completed=False,
            )

        # Convert interview state to response schema
        questions = [
            QuestionSchema(
                id=q.get("id", f"Q-{i}"),
                type=QuestionTypeEnum(q.get("type", "text")),
                text=q.get("text", ""),
                options=q.get("options"),
                required=q.get("required", True),
                context=q.get("context"),
            )
            for i, q in enumerate(interview_state.get("questions", []))
        ]

        return InterviewStatusResponse(
            current_question=interview_state.get("current_index", 0),
            total_questions=len(questions),
            questions=questions,
            answers=interview_state.get("answers", {}),
            completed=interview_state.get("completed", False),
        )

    # -------------------------------------------------------------------------
    # POST /workflow/{workflow_id}/interview-answer - Submit interview answer
    # -------------------------------------------------------------------------

    @router.post(
        "/workflow/{workflow_id}/interview-answer",
        response_model=InterviewAnswerResponse,
        summary="Submit interview answer",
        description="Submit an answer to the current interview question.",
        responses={
            200: {"description": "Answer accepted, next question or completion"},
            400: {"description": "Invalid answer or no interview in progress"},
            401: {"description": "Authentication required"},
            403: {"description": "Access denied"},
            404: {"description": "Workflow not found"},
        },
    )
    async def submit_interview_answer(
        workflow_id: str,
        request: InterviewAnswerRequest,
        user: ClerkUser = Depends(verify_user),
    ) -> InterviewAnswerResponse:
        """Submit an answer to an interview question.

        Args:
            workflow_id: The workflow ID (UUID format)
            request: InterviewAnswerRequest with question_id and answer
            user: Authenticated user

        Returns:
            InterviewAnswerResponse with next question or completion status
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

        # Get interview state from workflow
        interview_state = workflow.get("interview_state")
        if interview_state is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No interview in progress for this workflow",
            )

        if interview_state.get("completed", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interview is already completed",
            )

        # Verify question exists
        questions = interview_state.get("questions", [])
        question_ids = [q.get("id") for q in questions]
        if request.question_id not in question_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question {request.question_id} not found in interview",
            )

        # Add the answer
        answers = dict(interview_state.get("answers", {}))
        answers[request.question_id] = request.answer

        # Calculate new current index
        current_idx = interview_state.get("current_index", 0)
        for i, q in enumerate(questions):
            if q.get("id") == request.question_id and i >= current_idx:
                current_idx = i + 1
                break

        # Check completion
        if request.skip_remaining:
            # Check if all required questions are answered
            unanswered_required = [
                q
                for q in questions
                if q.get("required", True) and q.get("id") not in answers
            ]
            if unanswered_required:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot skip: {len(unanswered_required)} required "
                    "questions unanswered",
                )
            completed = True
            current_idx = len(questions)
        else:
            # Check if all required questions are answered
            completed = all(
                q.get("id") in answers
                for q in questions
                if q.get("required", True)
            )

        # Update interview state
        updated_interview = {
            **interview_state,
            "answers": answers,
            "current_index": current_idx,
            "completed": completed,
        }

        # Update workflow
        WorkflowManager.update_workflow(
            workflow_id,
            {"interview_state": updated_interview},
        )

        # Find next unanswered question
        next_question: QuestionSchema | None = None
        if not completed:
            for q in questions:
                if q.get("id") not in answers:
                    next_question = QuestionSchema(
                        id=q.get("id", ""),
                        type=QuestionTypeEnum(q.get("type", "text")),
                        text=q.get("text", ""),
                        options=q.get("options"),
                        required=q.get("required", True),
                        context=q.get("context"),
                    )
                    break

        return InterviewAnswerResponse(
            next_question=next_question,
            complete=completed,
            answers_count=len(answers),
            total_questions=len(questions),
        )

    return router


def _generate_mock_tasks(workflow_id: str) -> TasksListResponse:
    """Generate mock task data for development/testing.

    In production, the orchestrator populates real task data.

    Args:
        workflow_id: The workflow ID

    Returns:
        TasksListResponse with mock data
    """
    # Create mock tasks
    task1 = Task(
        id=f"{workflow_id}-task-1",
        description="Set up project structure and dependencies",
        type=TaskType.SETUP,
        complexity=TaskComplexity.LOW,
        dependencies=[],
        estimated_hours=1.0,
    )
    task2 = Task(
        id=f"{workflow_id}-task-2",
        description="Implement core data models",
        type=TaskType.CODE,
        complexity=TaskComplexity.MEDIUM,
        dependencies=[f"{workflow_id}-task-1"],
        estimated_hours=3.0,
    )
    task3 = Task(
        id=f"{workflow_id}-task-3",
        description="Write unit tests for data models",
        type=TaskType.TEST,
        complexity=TaskComplexity.MEDIUM,
        dependencies=[f"{workflow_id}-task-2"],
        estimated_hours=2.0,
    )
    task4 = Task(
        id=f"{workflow_id}-task-4",
        description="Implement API endpoints",
        type=TaskType.CODE,
        complexity=TaskComplexity.HIGH,
        dependencies=[f"{workflow_id}-task-2"],
        estimated_hours=4.0,
    )
    task5 = Task(
        id=f"{workflow_id}-task-5",
        description="Write API documentation",
        type=TaskType.DOCS,
        complexity=TaskComplexity.LOW,
        dependencies=[f"{workflow_id}-task-4"],
        estimated_hours=1.5,
    )

    # Create mock stories
    story1 = Story(
        id=f"{workflow_id}-story-1",
        title="Project Setup",
        priority=StoryPriority.P0,
        tasks=[task1],
    )
    story2 = Story(
        id=f"{workflow_id}-story-2",
        title="Core Implementation",
        priority=StoryPriority.P0,
        tasks=[task2, task3],
    )
    story3 = Story(
        id=f"{workflow_id}-story-3",
        title="API Development",
        priority=StoryPriority.P1,
        tasks=[task4, task5],
    )

    # Create mock phases
    phase1 = Phase(
        id=f"{workflow_id}-phase-1",
        name="Foundation",
        description="Set up project foundation and core components",
        stories=[story1, story2],
    )
    phase2 = Phase(
        id=f"{workflow_id}-phase-2",
        name="Features",
        description="Implement main features and API",
        stories=[story3],
    )

    # Create dependencies
    dependencies = [
        Dependency(source_id=task1.id, target_id=task2.id),
        Dependency(source_id=task2.id, target_id=task3.id),
        Dependency(source_id=task2.id, target_id=task4.id),
        Dependency(source_id=task4.id, target_id=task5.id),
    ]

    # Flatten tasks and stories
    all_tasks = [task1, task2, task3, task4, task5]
    all_stories = [story1, story2, story3]

    return TasksListResponse(
        phases=[phase1, phase2],
        stories=all_stories,
        tasks=all_tasks,
        dependencies=dependencies,
    )


# -----------------------------------------------------------------------------
# Kanban Board Helpers
# -----------------------------------------------------------------------------

# Human-readable column titles
COLUMN_TITLES: dict[KanbanColumnEnum, str] = {
    KanbanColumnEnum.BACKLOG: "Backlog",
    KanbanColumnEnum.PLANNING: "Planning",
    KanbanColumnEnum.CODING: "Coding",
    KanbanColumnEnum.VALIDATING: "Validating",
    KanbanColumnEnum.DEPLOYING: "Deploying",
    KanbanColumnEnum.DONE: "Done",
}


def _generate_kanban_board(
    workflow_id: str, workflow: dict[str, Any]
) -> KanbanBoardResponse:
    """Generate Kanban board data from workflow tasks.

    Converts workflow tasks into Kanban format with columns and statistics.

    Args:
        workflow_id: The workflow ID
        workflow: The workflow data dictionary

    Returns:
        KanbanBoardResponse with columns, tasks, and stats
    """
    now = datetime.now(UTC)

    # Get tasks from workflow or generate mock
    tasks_data = workflow.get("tasks")
    if tasks_data is None:
        # Use mock tasks
        mock_response = _generate_mock_tasks(workflow_id)
        tasks_list = mock_response.tasks
    else:
        tasks_list = tasks_data.get("tasks", [])

    # Convert tasks to KanbanTask format
    kanban_tasks: list[KanbanTask] = []
    for i, task in enumerate(tasks_list):
        # Determine column based on task state
        if isinstance(task, dict):
            task_id = task.get("id", f"{workflow_id}-task-{i}")
            description = task.get("description", "Task")
            deps = task.get("dependencies", [])
            complexity = task.get("complexity", "medium")
        else:
            task_id = task.id
            description = task.description
            deps = task.dependencies
            complexity = task.complexity.value if hasattr(task, "complexity") else "medium"

        # Determine priority from complexity
        priority = TaskPriorityEnum.P2
        if complexity == "high":
            priority = TaskPriorityEnum.P0
        elif complexity == "medium":
            priority = TaskPriorityEnum.P1

        # Default to backlog column
        column = KanbanColumnEnum.BACKLOG

        # Create short title from description
        title = description[:50] if len(description) > 50 else description

        kanban_task = KanbanTask(
            id=task_id,
            title=title,
            description=description,
            column=column,
            priority=priority,
            assigned_agent=None,
            dependencies=deps if isinstance(deps, list) else [],
            dependents=[],
            updated_at=now,
            created_at=now,
        )
        kanban_tasks.append(kanban_task)

    # Build dependents list for each task
    task_id_set = {t.id for t in kanban_tasks}
    for task in kanban_tasks:
        for dep_id in task.dependencies:
            if dep_id in task_id_set:
                for other in kanban_tasks:
                    if other.id == dep_id:
                        other.dependents.append(task.id)

    # Count tasks per column
    column_counts: dict[KanbanColumnEnum, int] = {col: 0 for col in KanbanColumnEnum}
    for task in kanban_tasks:
        column_counts[task.column] += 1

    total_tasks = len(kanban_tasks)
    done_count = column_counts[KanbanColumnEnum.DONE]

    # Build column info
    columns: list[KanbanColumnInfo] = []
    for col in KanbanColumnEnum:
        count = column_counts[col]
        progress = (count / total_tasks * 100) if total_tasks > 0 else 0.0
        columns.append(
            KanbanColumnInfo(
                id=col,
                title=COLUMN_TITLES[col],
                count=count,
                progress_percent=progress,
            )
        )

    # Calculate stats
    in_progress_cols = {
        KanbanColumnEnum.PLANNING,
        KanbanColumnEnum.CODING,
        KanbanColumnEnum.VALIDATING,
        KanbanColumnEnum.DEPLOYING,
    }
    in_progress_count = sum(column_counts[c] for c in in_progress_cols)

    # Count blocked tasks (tasks with unmet dependencies)
    blocked_count = 0
    for task in kanban_tasks:
        if task.column != KanbanColumnEnum.DONE:
            for dep_id in task.dependencies:
                dep_task = next((t for t in kanban_tasks if t.id == dep_id), None)
                if dep_task and dep_task.column != KanbanColumnEnum.DONE:
                    blocked_count += 1
                    break

    completion_percent = (done_count / total_tasks * 100) if total_tasks > 0 else 0.0

    stats = KanbanStats(
        total_tasks=total_tasks,
        completed_tasks=done_count,
        in_progress_tasks=in_progress_count,
        blocked_tasks=blocked_count,
        completion_percent=completion_percent,
    )

    return KanbanBoardResponse(
        columns=columns,
        tasks=kanban_tasks,
        stats=stats,
        last_updated=now,
    )


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
