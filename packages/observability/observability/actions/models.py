"""
Pydantic models for the Remediation Action Registry.

This module defines the data models for configurable remediation actions
used by the observability self-healing system.

Part of OBS-010: Remediation Action Registry
See: docs/planning/epics/EPIC-13-OBSERVABILITY.md
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Types of remediation actions supported by the system."""

    RESTART = "restart"
    SCALE = "scale"
    ROLLBACK = "rollback"
    CLEAR_CACHE = "clear_cache"
    CUSTOM = "custom"


class TriggerType(str, Enum):
    """Types of triggers that can activate an action."""

    CONTAINER_UNHEALTHY = "container_unhealthy"
    HIGH_CPU_SUSTAINED = "high_cpu_sustained"
    HIGH_MEMORY_SUSTAINED = "high_memory_sustained"
    ERROR_RATE_SPIKE = "error_rate_spike"
    CACHE_MEMORY_HIGH = "cache_memory_high"
    SERVICE_DOWN = "service_down"
    LATENCY_HIGH = "latency_high"
    CUSTOM = "custom"


class ApprovalLevel(str, Enum):
    """Approval levels for action execution."""

    NONE = "none"  # Auto-execute without approval
    NOTIFY = "notify"  # Execute and notify
    REQUIRE = "require"  # Require explicit approval before execution


class ActionDefinition(BaseModel):
    """Definition of a remediation action.

    This model defines the configuration for a single remediation action,
    including its trigger conditions, execution command, and safety constraints.

    Attributes:
        name: Unique identifier for this action
        action_type: Type of remediation action
        trigger: Event that triggers this action
        description: Human-readable description of what this action does
        command: Command or script to execute (templated with {variables})
        cooldown_seconds: Minimum seconds between executions
        max_attempts: Maximum number of attempts per incident
        requires_approval: Approval level required before execution
        enabled: Whether this action is active
        priority: Execution priority (lower = higher priority)
        timeout_seconds: Maximum execution time before timeout
        rollback_command: Optional command to undo this action
        parameters: Additional action-specific parameters
        tags: Tags for categorization and filtering
    """

    name: str = Field(..., min_length=1, max_length=100)
    action_type: ActionType
    trigger: TriggerType
    description: str = Field(default="", max_length=500)
    command: str = Field(..., min_length=1)
    cooldown_seconds: int = Field(default=300, ge=0, le=86400)  # Max 24 hours
    max_attempts: int = Field(default=3, ge=1, le=10)
    requires_approval: ApprovalLevel = Field(default=ApprovalLevel.NONE)
    enabled: bool = Field(default=True)
    priority: int = Field(default=50, ge=0, le=100)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    rollback_command: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate action name is lowercase with underscores."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Action name must contain only alphanumeric characters and underscores")
        return v.lower()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Normalize tags to lowercase."""
        return [tag.lower().strip() for tag in v if tag.strip()]

    def render_command(self, variables: dict[str, str]) -> str:
        """Render the command template with provided variables.

        Args:
            variables: Dictionary of variable names to values

        Returns:
            The command string with variables substituted

        Raises:
            KeyError: If a required variable is missing
        """
        try:
            return self.command.format(**variables)
        except KeyError as e:
            raise KeyError(f"Missing required variable for command: {e}")


class ActionExecution(BaseModel):
    """Record of an action execution attempt.

    Tracks the execution history for cooldown and max_attempts enforcement.

    Attributes:
        action_name: Name of the action that was executed
        target: The service/container/resource this action targeted
        timestamp: When the execution occurred
        success: Whether the execution succeeded
        dry_run: Whether this was a dry-run execution
        duration_ms: How long the execution took
        error: Error message if execution failed
        output: Output from the execution
        approved_by: Who approved the execution (if approval required)
    """

    action_name: str
    target: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    success: bool
    dry_run: bool = False
    duration_ms: int | None = None
    error: str | None = None
    output: str | None = None
    approved_by: str | None = None


class ValidationResult(BaseModel):
    """Result of validating whether an action can be executed.

    Attributes:
        can_execute: Whether the action is allowed to execute
        action_name: Name of the action that was validated
        target: The target for the action
        reason: Human-readable explanation of the decision
        cooldown_remaining_seconds: Seconds until cooldown expires (if in cooldown)
        attempts_remaining: Number of attempts remaining (if limited)
        requires_approval: Whether approval is still needed
    """

    can_execute: bool
    action_name: str
    target: str
    reason: str
    cooldown_remaining_seconds: int | None = None
    attempts_remaining: int | None = None
    requires_approval: bool = False


class DryRunResult(BaseModel):
    """Result of a dry-run action execution.

    Shows what would happen if the action were executed for real.

    Attributes:
        action_name: Name of the action
        action_type: Type of the action
        target: The target for the action
        command: The rendered command that would be executed
        validation: Whether this action would pass validation
        estimated_duration_seconds: Estimated execution time
        warnings: Any warnings about this execution
        rollback_available: Whether a rollback command is available
    """

    action_name: str
    action_type: ActionType
    target: str
    command: str
    validation: ValidationResult
    estimated_duration_seconds: int | None = None
    warnings: list[str] = Field(default_factory=list)
    rollback_available: bool = False


class ActionRegistryConfig(BaseModel):
    """Configuration for the action registry.

    Attributes:
        version: Schema version of this configuration
        default_cooldown_seconds: Default cooldown if not specified per-action
        default_max_attempts: Default max attempts if not specified per-action
        global_rate_limit_per_hour: Maximum actions across all types per hour
        actions: List of action definitions
    """

    version: str = Field(default="1.0.0")
    default_cooldown_seconds: int = Field(default=300, ge=0)
    default_max_attempts: int = Field(default=3, ge=1)
    global_rate_limit_per_hour: int = Field(default=10, ge=1, le=100)
    actions: list[ActionDefinition] = Field(default_factory=list)

    @field_validator("actions")
    @classmethod
    def validate_unique_names(cls, v: list[ActionDefinition]) -> list[ActionDefinition]:
        """Ensure all action names are unique."""
        names = [action.name for action in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(f"Duplicate action names found: {set(duplicates)}")
        return v
