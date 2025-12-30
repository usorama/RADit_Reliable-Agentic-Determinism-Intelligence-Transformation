"""
Pydantic schemas for the evolution/self-learning module.

This module defines the data models for:
- Experience: Task completion records for learning
- Skill: Reusable code patterns
- Artifact: Produced outputs (code, tests, docs)
- Insight: Lessons learned from reflection

Neo4j Schema:
(:Experience {task_type, success, prompt_version, model_used, tokens_used, cost_usd})
  -[:USED_SKILL]->(:Skill {name, pattern, success_rate})
  -[:PRODUCED]->(:Artifact {type, path})
  -[:REFLECTED_AS]->(:Insight {what_worked, lesson_learned})
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Task types for categorizing experiences."""

    PLANNING = "planning"
    CODING = "coding"
    VALIDATION = "validation"
    FAST = "fast"
    DEBUGGING = "debugging"
    DOCUMENTATION = "documentation"


class ArtifactType(str, Enum):
    """Types of artifacts produced by tasks."""

    CODE = "code"
    TEST = "test"
    DOCUMENTATION = "documentation"
    CONFIG = "config"
    PRD = "prd"


class Experience(BaseModel):
    """
    Represents a task completion experience for learning.

    This is the core data structure for the self-evolution system,
    storing all metadata about task executions for future retrieval
    and learning.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = Field(..., description="ID of the task that was executed")
    task_type: TaskType = Field(..., description="Type of task")
    success: bool = Field(..., description="Whether the task succeeded")
    prompt_version: str = Field(..., description="Version of prompt used")
    model_used: str = Field(..., description="LLM model used for execution")
    tokens_used: int = Field(..., ge=0, description="Total tokens consumed")
    cost_usd: float = Field(..., ge=0, description="Cost in USD")
    duration_ms: int = Field(..., ge=0, description="Duration in milliseconds")
    retries: int = Field(default=0, ge=0, description="Number of retry attempts")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the experience occurred",
    )
    error_message: str | None = Field(
        default=None, description="Error message if failed"
    )
    error_type: str | None = Field(default=None, description="Error type if failed")

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to properties dict for Neo4j node creation."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "success": self.success,
            "prompt_version": self.prompt_version,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "error_type": self.error_type,
        }


class Skill(BaseModel):
    """
    Represents a reusable code pattern or skill.

    Skills are extracted from successful experiences and can be
    referenced in future tasks via the USED_SKILL relationship.
    """

    name: str = Field(..., description="Unique name for the skill")
    pattern: str = Field(..., description="Code pattern or approach")
    description: str | None = Field(
        default=None, description="Human-readable description"
    )
    success_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Success rate when using this skill"
    )
    usage_count: int = Field(default=0, ge=0, description="Number of times used")

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to properties dict for Neo4j node creation."""
        return {
            "name": self.name,
            "pattern": self.pattern,
            "description": self.description,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
        }


class Artifact(BaseModel):
    """
    Represents an artifact produced by a task.

    Artifacts include code files, tests, documentation, and other
    outputs created during task execution.
    """

    artifact_type: ArtifactType = Field(..., description="Type of artifact")
    path: str = Field(..., description="File path of the artifact")
    description: str | None = Field(
        default=None, description="Description of the artifact"
    )

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to properties dict for Neo4j node creation."""
        return {
            "type": self.artifact_type.value,
            "path": self.path,
            "description": self.description,
        }


class Insight(BaseModel):
    """
    Represents a lesson learned from reflection.

    Insights are created by the reflection hook after task completion
    to capture what worked well and what could be improved.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    what_worked: str = Field(..., description="What worked well in this experience")
    lesson_learned: str = Field(..., description="Key lesson to remember")
    improvement_suggestion: str | None = Field(
        default=None, description="Suggestion for future improvement"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the insight was created",
    )

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to properties dict for Neo4j node creation."""
        return {
            "id": self.id,
            "what_worked": self.what_worked,
            "lesson_learned": self.lesson_learned,
            "improvement_suggestion": self.improvement_suggestion,
            "created_at": self.created_at.isoformat(),
        }


class ExperienceQuery(BaseModel):
    """
    Query parameters for retrieving similar experiences.

    Used for RAG-style retrieval of past experiences based on
    various criteria.
    """

    task_type: TaskType | None = Field(default=None, description="Filter by task type")
    success: bool | None = Field(default=None, description="Filter by success status")
    model_used: str | None = Field(default=None, description="Filter by model")
    error_type: str | None = Field(default=None, description="Filter by error type")
    start_time: datetime | None = Field(
        default=None, description="Filter experiences after this time"
    )
    end_time: datetime | None = Field(
        default=None, description="Filter experiences before this time"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")


class SuccessRate(BaseModel):
    """
    Success rate statistics for a task type/model combination.
    """

    task_type: TaskType | None = Field(default=None, description="Task type if grouped")
    model_used: str | None = Field(default=None, description="Model if grouped")
    success_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Success rate (0.0-1.0)"
    )
    total_count: int = Field(default=0, ge=0, description="Total number of experiences")
    success_count: int = Field(
        default=0, ge=0, description="Number of successful experiences"
    )
