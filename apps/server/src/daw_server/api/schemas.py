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
    AWAITING_PRD_APPROVAL = "awaiting_prd_approval"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_TASK_APPROVAL = "awaiting_task_approval"
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


class TaskReviewAction(str, Enum):
    """Actions for task review approval."""

    APPROVE = "approve"
    REJECT = "reject"


class PRDReviewAction(str, Enum):
    """Actions for PRD review approval gate.

    - APPROVE: Accept the PRD and proceed to task execution
    - REJECT: Reject the PRD and return to interview phase
    - MODIFY: Request modifications to the PRD
    """

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class QuestionTypeEnum(str, Enum):
    """Types of interview questions."""

    TEXT = "text"
    MULTI_CHOICE = "multi_choice"
    CHECKBOX = "checkbox"


class TaskType(str, Enum):
    """Task type classification."""

    SETUP = "setup"
    CODE = "code"
    TEST = "test"
    DOCS = "docs"


class TaskComplexity(str, Enum):
    """Task complexity level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StoryPriority(str, Enum):
    """Story priority level."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


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
# PRD Review Models
# -----------------------------------------------------------------------------


class PRDReviewRequest(BaseModel):
    """Request schema for POST /api/workflow/{id}/prd-review endpoint.

    Allows users to approve, reject, or request modifications to a generated PRD.

    Attributes:
        action: The review action (approve, reject, modify).
        feedback: Optional feedback explaining the decision (required for reject/modify).
    """

    action: PRDReviewAction = Field(
        ...,
        description="The review action (approve, reject, modify)",
    )
    feedback: str | None = Field(
        default=None,
        description="Optional feedback explaining the decision (required for reject/modify)",
    )


class PRDReviewResponse(BaseModel):
    """Response schema for POST /api/workflow/{id}/prd-review endpoint.

    Attributes:
        success: Whether the review action was successful.
        status: The new workflow status after the action.
        prd: The PRD document (if action was approve or modify).
        message: Description of what happened.
    """

    success: bool = Field(..., description="Whether the action was successful")
    status: WorkflowStatusEnum = Field(
        ..., description="The new workflow status after the action"
    )
    prd: dict[str, Any] | None = Field(
        default=None, description="The PRD document (if applicable)"
    )
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


# -----------------------------------------------------------------------------
# Task Review Models
# -----------------------------------------------------------------------------


class Task(BaseModel):
    """A single atomic task in the workflow.

    Attributes:
        id: Unique identifier for the task.
        description: Description of what the task accomplishes.
        type: Task type (setup, code, test, docs).
        complexity: Complexity level (low, medium, high).
        dependencies: List of task IDs this task depends on.
        estimatedHours: Optional estimated hours to complete.
    """

    model_config = {"populate_by_name": True}

    id: str = Field(..., description="Unique identifier for the task")
    description: str = Field(..., description="Description of what the task accomplishes")
    type: TaskType = Field(..., description="Task type classification")
    complexity: TaskComplexity = Field(..., description="Complexity level")
    dependencies: list[str] = Field(
        default_factory=list, description="List of task IDs this task depends on"
    )
    estimated_hours: float | None = Field(
        default=None,
        description="Optional estimated hours to complete",
        serialization_alias="estimatedHours",
        validation_alias="estimatedHours",
    )


class Story(BaseModel):
    """A user story containing multiple tasks.

    Attributes:
        id: Unique identifier for the story.
        title: Story title.
        priority: Priority level (P0, P1, P2).
        tasks: List of tasks belonging to this story.
    """

    id: str = Field(..., description="Unique identifier for the story")
    title: str = Field(..., description="Story title")
    priority: StoryPriority = Field(..., description="Priority level")
    tasks: list[Task] = Field(default_factory=list, description="List of tasks")


class Phase(BaseModel):
    """A development phase containing multiple stories.

    Attributes:
        id: Unique identifier for the phase.
        name: Phase name.
        description: Phase description.
        stories: List of stories in this phase.
    """

    id: str = Field(..., description="Unique identifier for the phase")
    name: str = Field(..., description="Phase name")
    description: str = Field(..., description="Phase description")
    stories: list[Story] = Field(default_factory=list, description="List of stories")


class Dependency(BaseModel):
    """A dependency relationship between tasks.

    Attributes:
        source_id: ID of the source task.
        target_id: ID of the target task (depends on source).
    """

    model_config = {"populate_by_name": True}

    source_id: str = Field(
        ...,
        description="ID of the source task",
        serialization_alias="sourceId",
        validation_alias="sourceId",
    )
    target_id: str = Field(
        ...,
        description="ID of the target task",
        serialization_alias="targetId",
        validation_alias="targetId",
    )


class TasksListResponse(BaseModel):
    """Response schema for GET /api/workflow/{id}/tasks endpoint.

    Attributes:
        phases: List of development phases.
        stories: Flat list of all stories (for convenience).
        tasks: Flat list of all tasks (for convenience).
        dependencies: List of task dependencies.
    """

    phases: list[Phase] = Field(..., description="List of development phases")
    stories: list[Story] = Field(..., description="Flat list of all stories")
    tasks: list[Task] = Field(..., description="Flat list of all tasks")
    dependencies: list[Dependency] = Field(..., description="List of task dependencies")


class TaskReviewRequest(BaseModel):
    """Request schema for POST /api/workflow/{id}/tasks-review endpoint.

    Attributes:
        action: The review action (approve or reject).
        feedback: Optional feedback comment (required for reject).
    """

    action: TaskReviewAction = Field(
        ..., description="The review action (approve or reject)"
    )
    feedback: str | None = Field(
        default=None, description="Optional feedback comment (required for reject)"
    )


class TaskReviewResponse(BaseModel):
    """Response schema for POST /api/workflow/{id}/tasks-review endpoint.

    Attributes:
        success: Whether the review action was successful.
        workflow_id: The workflow ID.
        status: The new workflow status after the action.
        message: Description of what happened.
    """

    success: bool = Field(..., description="Whether the action was successful")
    workflow_id: str = Field(..., description="The workflow ID")
    status: WorkflowStatusEnum = Field(
        ..., description="The new workflow status after the action"
    )
    message: str = Field(..., description="Description of what happened")


# -----------------------------------------------------------------------------
# Interview Models
# -----------------------------------------------------------------------------


class QuestionSchema(BaseModel):
    """Schema for an interview question.

    Represents a single question to be asked during the requirements
    clarification interview.

    Attributes:
        id: Unique question identifier (e.g., Q-001)
        type: Question type (text, multi_choice, checkbox)
        text: The question text to display
        options: Available options for multi_choice/checkbox questions
        required: Whether the question must be answered
        context: Additional context to help user answer
    """

    id: str = Field(..., description="Unique question identifier (e.g., Q-001)")
    type: QuestionTypeEnum = Field(
        default=QuestionTypeEnum.TEXT, description="Question type"
    )
    text: str = Field(..., description="The question text to display")
    options: list[str] | None = Field(
        default=None, description="Available options for multi_choice/checkbox"
    )
    required: bool = Field(default=True, description="Whether answer is required")
    context: str | None = Field(
        default=None, description="Additional context to help user answer"
    )


class InterviewAnswerRequest(BaseModel):
    """Request schema for POST /api/workflow/{id}/interview-answer endpoint.

    Allows users to submit an answer to an interview question.

    Attributes:
        question_id: ID of the question being answered
        answer: User's answer (string or list of strings for checkbox)
        skip_remaining: Whether to skip remaining optional questions
    """

    question_id: str = Field(..., description="ID of the question being answered")
    answer: str | list[str] = Field(
        ..., description="User's answer (string or list for checkbox)"
    )
    skip_remaining: bool = Field(
        default=False, description="Whether to skip remaining optional questions"
    )


class InterviewAnswerResponse(BaseModel):
    """Response schema for POST /api/workflow/{id}/interview-answer endpoint.

    Returns the next question or indicates interview completion.

    Attributes:
        next_question: The next question to answer, or null if complete
        complete: Whether the interview is complete
        answers_count: Number of answers submitted so far
        total_questions: Total number of questions in the interview
    """

    next_question: QuestionSchema | None = Field(
        default=None, description="Next question to answer, or null if complete"
    )
    complete: bool = Field(
        default=False, description="Whether the interview is complete"
    )
    answers_count: int = Field(
        default=0, description="Number of answers submitted so far"
    )
    total_questions: int = Field(
        default=0, description="Total number of questions in the interview"
    )


class InterviewStatusResponse(BaseModel):
    """Response schema for GET /api/workflow/{id}/interview-status endpoint.

    Returns the current state of the interview.

    Attributes:
        current_question: Index of the current question (0-based)
        total_questions: Total number of questions
        questions: List of all interview questions
        answers: Dictionary of submitted answers (question_id -> answer)
        completed: Whether the interview is complete
    """

    current_question: int = Field(
        default=0, description="Index of the current question (0-based)"
    )
    total_questions: int = Field(default=0, description="Total number of questions")
    questions: list[QuestionSchema] = Field(
        default_factory=list, description="List of all interview questions"
    )
    answers: dict[str, str | list[str]] = Field(
        default_factory=dict, description="Submitted answers (question_id -> answer)"
    )
    completed: bool = Field(default=False, description="Whether the interview is complete")


# -----------------------------------------------------------------------------
# Kanban Board Models
# -----------------------------------------------------------------------------


class KanbanColumnEnum(str, Enum):
    """Kanban column identifiers representing workflow stages."""

    BACKLOG = "backlog"
    PLANNING = "planning"
    CODING = "coding"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    DONE = "done"


class TaskPriorityEnum(str, Enum):
    """Priority levels for Kanban tasks."""

    P0 = "P0"  # Critical (red)
    P1 = "P1"  # High (yellow)
    P2 = "P2"  # Normal (blue)


class KanbanTask(BaseModel):
    """A single task on the Kanban board.

    Attributes:
        id: Unique task identifier.
        title: Short title for the task.
        description: Full description of the task.
        column: Current column/stage.
        priority: Task priority (P0 = critical, P1 = high, P2 = normal).
        assigned_agent: Agent currently assigned to this task (if any).
        dependencies: List of task IDs this task depends on.
        dependents: List of task IDs that depend on this task.
        updated_at: ISO timestamp of last update.
        created_at: ISO timestamp of creation.
    """

    id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Short title for the task")
    description: str = Field(..., description="Full description of the task")
    column: KanbanColumnEnum = Field(..., description="Current column/stage")
    priority: TaskPriorityEnum = Field(
        default=TaskPriorityEnum.P2, description="Task priority"
    )
    assigned_agent: str | None = Field(
        default=None, description="Agent currently assigned to this task"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="List of task IDs this task depends on"
    )
    dependents: list[str] = Field(
        default_factory=list, description="List of task IDs that depend on this task"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )


class KanbanColumnInfo(BaseModel):
    """Column metadata for display.

    Attributes:
        id: Column identifier.
        title: Display title.
        count: Number of tasks in this column.
        progress_percent: Progress percentage (0-100).
    """

    id: KanbanColumnEnum = Field(..., description="Column identifier")
    title: str = Field(..., description="Display title")
    count: int = Field(default=0, description="Number of tasks in this column")
    progress_percent: float = Field(
        default=0.0, description="Progress percentage (0-100)", ge=0.0, le=100.0
    )


class KanbanStats(BaseModel):
    """Overall board statistics.

    Attributes:
        total_tasks: Total number of tasks.
        completed_tasks: Number of completed tasks.
        in_progress_tasks: Number of in-progress tasks.
        blocked_tasks: Number of blocked tasks.
        completion_percent: Overall completion percentage (0-100).
    """

    total_tasks: int = Field(default=0, description="Total number of tasks")
    completed_tasks: int = Field(default=0, description="Number of completed tasks")
    in_progress_tasks: int = Field(
        default=0, description="Number of in-progress tasks"
    )
    blocked_tasks: int = Field(default=0, description="Number of blocked tasks")
    completion_percent: float = Field(
        default=0.0,
        description="Overall completion percentage (0-100)",
        ge=0.0,
        le=100.0,
    )


class KanbanBoardResponse(BaseModel):
    """Response schema for GET /api/workflow/{id}/kanban endpoint.

    Attributes:
        columns: Column metadata.
        tasks: All tasks on the board.
        stats: Board statistics.
        last_updated: Last update timestamp.
    """

    columns: list[KanbanColumnInfo] = Field(..., description="Column metadata")
    tasks: list[KanbanTask] = Field(..., description="All tasks on the board")
    stats: KanbanStats = Field(..., description="Board statistics")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )


class KanbanUpdateRequest(BaseModel):
    """Request schema for PATCH /api/workflow/{id}/kanban/{task_id} endpoint.

    Attributes:
        column: Target column for the task.
        priority: New priority for the task (optional).
    """

    column: KanbanColumnEnum = Field(..., description="Target column for the task")
    priority: TaskPriorityEnum | None = Field(
        default=None, description="New priority for the task"
    )


class KanbanUpdateResponse(BaseModel):
    """Response schema for PATCH /api/workflow/{id}/kanban/{task_id} endpoint.

    Attributes:
        success: Whether the update was successful.
        task: The updated task.
        message: Description of what happened.
    """

    success: bool = Field(..., description="Whether the update was successful")
    task: KanbanTask = Field(..., description="The updated task")
    message: str = Field(..., description="Description of what happened")


__all__ = [
    "WorkflowStatusEnum",
    "ApprovalAction",
    "TaskReviewAction",
    "PRDReviewAction",
    "QuestionTypeEnum",
    "TaskType",
    "TaskComplexity",
    "StoryPriority",
    "ChatRequest",
    "ChatResponse",
    "WorkflowStatus",
    "ApprovalRequest",
    "ApprovalResponse",
    "PRDReviewRequest",
    "PRDReviewResponse",
    "DeleteWorkflowResponse",
    "WebSocketMessage",
    "ErrorResponse",
    "Task",
    "Story",
    "Phase",
    "Dependency",
    "TasksListResponse",
    "TaskReviewRequest",
    "TaskReviewResponse",
    "QuestionSchema",
    "InterviewAnswerRequest",
    "InterviewAnswerResponse",
    "InterviewStatusResponse",
    # Kanban models
    "KanbanColumnEnum",
    "TaskPriorityEnum",
    "KanbanTask",
    "KanbanColumnInfo",
    "KanbanStats",
    "KanbanBoardResponse",
    "KanbanUpdateRequest",
    "KanbanUpdateResponse",
]
