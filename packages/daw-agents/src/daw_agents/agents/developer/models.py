"""Pydantic models for the Developer Agent.

This module defines the data models used by the Developer Agent:

- DeveloperStatus: Enum for workflow states
- TestRunResult: Result of running tests in sandbox
- DeveloperResult: Final result of the development workflow

The Developer Agent implements the Red-Green-Refactor TDD loop and uses
TaskType.CODING for model routing (different from Validator's TaskType.VALIDATION).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DeveloperStatus(str, Enum):
    """Status enum for Developer Agent workflow states.

    The Developer follows the TDD cycle:
    - WRITE_TEST: First write a failing test (start of RED phase)
    - RUN_TEST: Execute tests to verify pass/fail status
    - WRITE_CODE: Write implementation to pass tests (GREEN phase)
    - REFACTOR: Improve code quality while maintaining tests
    - COMPLETE: Workflow completed successfully
    - ERROR: Workflow encountered an unrecoverable error
    """

    WRITE_TEST = "write_test"
    RUN_TEST = "run_test"
    WRITE_CODE = "write_code"
    REFACTOR = "refactor"
    COMPLETE = "complete"
    ERROR = "error"


class TestRunResult(BaseModel):
    """Result of running tests in the sandbox.

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


class DeveloperResult(BaseModel):
    """Final result of the Developer Agent workflow.

    Attributes:
        success: Whether the development task completed successfully
        source_file: Path to the source file that was created/modified
        test_file: Path to the test file that was created
        source_code: Final source code content
        test_code: Final test code content
        iterations: Number of TDD iterations performed
        status: Final workflow status
        error: Error message if workflow failed
    """

    success: bool = Field(description="Whether development completed successfully")
    source_file: str = Field(description="Path to source file")
    test_file: str = Field(description="Path to test file")
    source_code: str = Field(default="", description="Final source code")
    test_code: str = Field(default="", description="Final test code")
    iterations: int = Field(default=0, description="Number of TDD iterations")
    status: str = Field(description="Final workflow status")
    error: str | None = Field(default=None, description="Error message if failed")
