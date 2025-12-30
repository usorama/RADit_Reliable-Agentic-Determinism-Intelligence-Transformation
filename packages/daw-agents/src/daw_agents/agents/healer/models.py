"""Pydantic models for the Healer Agent.

This module defines the data models used by the Healer Agent:

- HealerStatus: Enum for workflow states
- ErrorInfo: Information about the failed tool output
- FixSuggestion: Suggested fix from LLM
- KnowledgeEntry: Stored error resolution for future RAG
- ValidationResult: Result of running validation tests
- HealerResult: Final result of the healing workflow

The Healer Agent implements error recovery workflow and uses
TaskType.CODING for model routing to generate fixes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HealerStatus(str, Enum):
    """Status enum for Healer Agent workflow states.

    The Healer follows error recovery workflow:
    - DIAGNOSE: Analyze the failed tool output
    - QUERY_KNOWLEDGE: Search Neo4j for similar past errors
    - SUGGEST_FIX: Generate fix based on error and past resolutions
    - APPLY_FIX: Apply the suggested fix
    - VALIDATE: Run tests to verify the fix worked
    - COMPLETE: Workflow completed successfully
    - ERROR: Workflow encountered an unrecoverable error
    """

    DIAGNOSE = "diagnose"
    QUERY_KNOWLEDGE = "query_knowledge"
    SUGGEST_FIX = "suggest_fix"
    APPLY_FIX = "apply_fix"
    VALIDATE = "validate"
    COMPLETE = "complete"
    ERROR = "error"


class ErrorInfo(BaseModel):
    """Information about a failed tool output.

    Attributes:
        tool_name: Name of the tool that produced the error
        error_type: Type/category of the error (e.g., TestFailure, SyntaxError)
        error_message: The actual error message
        stack_trace: Stack trace if available
        source_file: Path to the source file with the error
        test_file: Path to the test file
        source_code: Current source code content
        test_code: Test code that's failing
    """

    tool_name: str = Field(description="Name of the tool that produced the error")
    error_type: str = Field(description="Type/category of the error")
    error_message: str = Field(description="The actual error message")
    stack_trace: str = Field(default="", description="Stack trace if available")
    source_file: str = Field(description="Path to the source file")
    test_file: str = Field(description="Path to the test file")
    source_code: str = Field(default="", description="Current source code")
    test_code: str = Field(default="", description="Test code that's failing")

    def to_signature(self) -> str:
        """Generate an error signature for matching similar errors.

        Creates a normalized hash of error type and key parts of the message
        to enable finding similar past errors in the knowledge graph.

        Returns:
            A string signature representing this error pattern
        """
        # Normalize error message by removing specific values
        normalized_message = self.error_message.lower()
        # Create signature from error type and normalized message start
        signature_base = f"{self.error_type}:{normalized_message[:100]}"
        # Hash for consistency
        signature_hash = hashlib.md5(signature_base.encode()).hexdigest()[:16]
        return f"{self.error_type}:{signature_hash}"


class FixSuggestion(BaseModel):
    """A suggested fix for an error.

    Attributes:
        description: Human-readable description of the fix
        fixed_code: The corrected code
        confidence: Confidence score (0.0 to 1.0)
        based_on_past_resolution: Whether this fix is based on a past resolution
        past_resolution_id: ID of the past resolution if applicable
    """

    description: str = Field(description="Human-readable description of the fix")
    fixed_code: str = Field(description="The corrected code")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score"
    )
    based_on_past_resolution: bool = Field(
        default=False, description="Whether based on past resolution"
    )
    past_resolution_id: str | None = Field(
        default=None, description="ID of past resolution if applicable"
    )


class KnowledgeEntry(BaseModel):
    """A stored error resolution for future RAG retrieval.

    Attributes:
        id: Unique identifier for this entry
        error_signature: Normalized error signature for matching
        error_type: Type of error
        error_pattern: Regex or pattern to match similar errors
        resolution_description: Description of how the error was fixed
        resolution_code: The code that fixed the error
        success_count: Number of times this resolution succeeded
        failure_count: Number of times this resolution failed
        created_at: When this entry was created
        last_used_at: When this entry was last used
    """

    id: str = Field(description="Unique identifier")
    error_signature: str = Field(description="Normalized error signature")
    error_type: str = Field(description="Type of error")
    error_pattern: str = Field(default="", description="Pattern to match similar errors")
    resolution_description: str = Field(description="Description of the fix")
    resolution_code: str = Field(description="The fixing code")
    success_count: int = Field(default=0, description="Successful uses")
    failure_count: int = Field(default=0, description="Failed uses")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Creation timestamp",
    )
    last_used_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Last use timestamp",
    )

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of this resolution.

        Returns:
            Float between 0.0 and 1.0 representing success rate
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total


class ValidationResult(BaseModel):
    """Result of running validation tests.

    Attributes:
        passed: Whether all tests passed
        output: Full output from test execution
        exit_code: Exit code from the test runner
        duration_ms: Time taken to run tests in milliseconds
        error: Error message if test execution failed
    """

    passed: bool = Field(description="Whether all tests passed")
    output: str = Field(default="", description="Full output from test execution")
    exit_code: int = Field(default=0, description="Exit code from test runner")
    duration_ms: float = Field(default=0.0, description="Test execution duration in ms")
    error: str | None = Field(default=None, description="Error message if execution failed")


class HealerResult(BaseModel):
    """Final result of the Healer Agent workflow.

    Attributes:
        success: Whether the healing task completed successfully
        fixed_code: The fixed code if successful
        fix_description: Description of the fix applied
        attempts: Number of attempts taken
        status: Final workflow status
        knowledge_entry_id: ID of the knowledge entry created (if successful)
        error: Error message if workflow failed
    """

    success: bool = Field(description="Whether healing completed successfully")
    fixed_code: str = Field(default="", description="The fixed code")
    fix_description: str = Field(default="", description="Description of the fix")
    attempts: int = Field(default=0, description="Number of attempts taken")
    status: str = Field(description="Final workflow status")
    knowledge_entry_id: str | None = Field(
        default=None, description="ID of knowledge entry created"
    )
    error: str | None = Field(default=None, description="Error message if failed")
