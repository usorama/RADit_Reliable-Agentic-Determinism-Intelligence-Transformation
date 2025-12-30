"""
Pydantic schemas for API request/response models.

This module defines the data models for:
- ChatRequest/ChatResponse: Interaction with the Planner agent
- WorkflowStatus: Current state of a workflow
- ApprovalRequest/ApprovalResponse: Human-in-the-loop approval
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class WorkflowStatusEnum(str, Enum):
    """Status values for a workflow."""

    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"


class ApprovalAction(str, Enum):
    """Actions for workflow approval."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


# -----------------------------------------------------------------------------
# Chat Models
# -----------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request schema for POST /api/chat endpoint.

    Attributes:
        message: The user's message to the Planner agent.
        context: Optional context dictionary for additional information.
        workflow_id: Optional workflow ID to continue an existing conversation.
    """

    message: str = Field(
        ...,
        description="The user's message to the Planner agent",
        min_length=1,
        examples=["Build a todo app with React and FastAPI"],
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional context dictionary for additional information",
        examples=[{"project_type": "web", "framework": "react"}],
    )
    workflow_id: str | None = Field(
        default=None,
        description="Optional workflow ID to continue an existing conversation",
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_empty(cls, v: str) -> str:
        """Validate that message is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v


class ChatResponse(BaseModel):
    """Response schema for POST /api/chat endpoint.

    Attributes:
        workflow_id: The ID of the created or continued workflow.
        message: Response message from the Planner agent.
        status: Current status of the workflow.
        tasks_generated: Number of tasks generated (if PRD phase complete).
        phase: Current phase of the workflow (interview, roundtable, etc.).
    """

    workflow_id: str = Field(
        ...,
        description="The ID of the created or continued workflow",
    )
    message: str = Field(
        ...,
        description="Response message from the Planner agent",
    )
    status: WorkflowStatusEnum | str = Field(
        ...,
        description="Current status of the workflow",
    )
    tasks_generated: int | None = Field(
        default=None,
        description="Number of tasks generated (if PRD phase complete)",
    )
    phase: str | None = Field(
        default=None,
        description="Current phase of the workflow",
    )


# -----------------------------------------------------------------------------
# Workflow Status Models
# -----------------------------------------------------------------------------


class WorkflowStatus(BaseModel):
    """Response schema for GET /api/workflow/{id} endpoint.

    Provides detailed information about the current state of a workflow.

    Attributes:
        id: Unique identifier for the workflow.
        status: Current status of the workflow.
        phase: Current phase (interview, roundtable, generate_prd, etc.).
        progress: Progress percentage (0.0 to 1.0).
        tasks_total: Total number of tasks in the workflow.
        tasks_completed: Number of completed tasks.
        current_task: Description of the current task being executed.
        created_at: Timestamp when the workflow was created.
        updated_at: Timestamp of last update.
        error_message: Error message if status is 'error'.
        user_id: ID of the user who owns this workflow.
    """

    id: str = Field(..., description="Unique identifier for the workflow")
    status: WorkflowStatusEnum | str = Field(
        ..., description="Current status of the workflow"
    )
    phase: str | None = Field(
        default=None,
        description="Current phase (interview, roundtable, generate_prd, etc.)",
    )
    progress: float | None = Field(
        default=None,
        description="Progress percentage (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    tasks_total: int | None = Field(
        default=None,
        description="Total number of tasks in the workflow",
    )
    tasks_completed: int | None = Field(
        default=None,
        description="Number of completed tasks",
    )
    current_task: str | None = Field(
        default=None,
        description="Description of the current task being executed",
    )
    created_at: datetime = Field(..., description="Timestamp when created")
    updated_at: datetime = Field(..., description="Timestamp of last update")
    error_message: str | None = Field(
        default=None,
        description="Error message if status is 'error'",
    )
    user_id: str | None = Field(
        default=None,
        description="ID of the user who owns this workflow",
    )


# -----------------------------------------------------------------------------
# Approval Models
# -----------------------------------------------------------------------------


class ApprovalRequest(BaseModel):
    """Request schema for POST /api/workflow/{id}/approve endpoint.

    Allows users to approve, reject, or request modifications to a workflow.

    Attributes:
        action: The approval action (approve, reject, modify).
        comment: Optional comment explaining the decision.
        modifications: Optional modifications to apply (for modify action).
    """

    action: ApprovalAction = Field(
        ...,
        description="The approval action (approve, reject, modify)",
    )
    comment: str | None = Field(
        default=None,
        description="Optional comment explaining the decision",
    )
    modifications: dict[str, Any] | None = Field(
        default=None,
        description="Optional modifications to apply (for modify action)",
    )


class ApprovalResponse(BaseModel):
    """Response schema for POST /api/workflow/{id}/approve endpoint.

    Attributes:
        success: Whether the approval action was successful.
        workflow_id: The workflow ID.
        new_status: The new status after the action.
        message: Description of what happened.
    """

    success: bool = Field(..., description="Whether the action was successful")
    workflow_id: str = Field(..., description="The workflow ID")
    new_status: str = Field(..., description="The new status after the action")
    message: str = Field(..., description="Description of what happened")


# -----------------------------------------------------------------------------
# Delete Workflow Response
# -----------------------------------------------------------------------------


class DeleteWorkflowResponse(BaseModel):
    """Response schema for DELETE /api/workflow/{id} endpoint.

    Attributes:
        success: Whether the deletion was successful.
        workflow_id: The deleted workflow ID.
        message: Description of what happened.
    """

    success: bool = Field(..., description="Whether the deletion was successful")
    workflow_id: str = Field(..., description="The deleted workflow ID")
    message: str = Field(..., description="Description of what happened")


# -----------------------------------------------------------------------------
# WebSocket Models
# -----------------------------------------------------------------------------


class WebSocketMessage(BaseModel):
    """Message format for WebSocket communication.

    Attributes:
        type: Message type (ping, pong, state_update, error, etc.).
        data: Optional data payload.
        timestamp: Message timestamp.
    """

    type: str = Field(..., description="Message type")
    data: dict[str, Any] | None = Field(
        default=None, description="Optional data payload"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Message timestamp"
    )


# -----------------------------------------------------------------------------
# Error Models
# -----------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error response schema.

    Attributes:
        detail: Error detail message.
        error_code: Optional error code for programmatic handling.
    """

    detail: str = Field(..., description="Error detail message")
    error_code: str | None = Field(
        default=None, description="Optional error code for programmatic handling"
    )


__all__ = [
    "WorkflowStatusEnum",
    "ApprovalAction",
    "ChatRequest",
    "ChatResponse",
    "WorkflowStatus",
    "ApprovalRequest",
    "ApprovalResponse",
    "DeleteWorkflowResponse",
    "WebSocketMessage",
    "ErrorResponse",
]
