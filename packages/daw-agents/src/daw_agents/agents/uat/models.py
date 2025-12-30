"""Pydantic models for the UAT Agent.

This module defines the data models used by the UAT Agent:

- UATStatus: Enum for workflow states
- GherkinStep: Represents a parsed Gherkin step
- ValidationResult: Result of validating a step
- UATResult: Final result of the UAT workflow

The UAT Agent uses Playwright MCP for browser automation and operates
on accessibility snapshots for determinism and speed.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class UATStatus(str, Enum):
    """Status enum for UAT Agent workflow states.

    The UAT Agent follows this workflow:
    - SETUP: Initialize browser via Playwright MCP
    - NAVIGATE: Navigate to target URL
    - INTERACT: Execute user interactions (click, type, etc.)
    - VALIDATE: Check expected outcomes
    - COMPLETE: Workflow completed successfully
    - ERROR: Workflow encountered an error
    """

    SETUP = "setup"
    NAVIGATE = "navigate"
    INTERACT = "interact"
    VALIDATE = "validate"
    COMPLETE = "complete"
    ERROR = "error"


class GherkinStep(BaseModel):
    """Represents a parsed Gherkin step.

    Attributes:
        keyword: The Gherkin keyword (Given, When, Then, And, But)
        text: The step text without the keyword
        action_type: The type of action (navigate, click, type, assert, wait)
        selector: CSS/XPath selector for the target element (optional)
        value: Value for input actions or assertions (optional)
    """

    keyword: str = Field(description="Gherkin keyword (Given, When, Then, And, But)")
    text: str = Field(description="Step text without keyword")
    action_type: str = Field(default="unknown", description="Action type")
    selector: str | None = Field(default=None, description="Element selector")
    value: str | None = Field(default=None, description="Value for input/assertion")


class ValidationResult(BaseModel):
    """Result of validating a Gherkin step.

    Attributes:
        step_index: Index of the step that was validated
        passed: Whether the validation passed
        expected: Expected outcome description
        actual: Actual outcome description
        accessibility_snapshot: Accessibility snapshot at validation time
        error: Error message if validation failed
    """

    step_index: int = Field(description="Index of the validated step")
    passed: bool = Field(description="Whether validation passed")
    expected: str = Field(default="", description="Expected outcome")
    actual: str = Field(default="", description="Actual outcome")
    accessibility_snapshot: dict[str, Any] | None = Field(
        default=None, description="Accessibility snapshot"
    )
    error: str | None = Field(default=None, description="Error message")


class UATResult(BaseModel):
    """Final result of the UAT Agent workflow.

    Attributes:
        success: Whether the UAT scenario completed successfully
        scenario: The Gherkin scenario that was executed
        status: Final workflow status
        validation_report: Summary of validation results
        screenshots: List of screenshot file paths
        traces: List of trace file paths
        timing: Timing measurements
        error: Error message if workflow failed
    """

    success: bool = Field(description="Whether UAT completed successfully")
    scenario: str = Field(description="The executed Gherkin scenario")
    status: str = Field(description="Final workflow status")
    validation_report: dict[str, Any] = Field(
        default_factory=dict, description="Validation summary"
    )
    screenshots: list[str] = Field(default_factory=list, description="Screenshot paths")
    traces: list[str] = Field(default_factory=list, description="Trace paths")
    timing: dict[str, Any] = Field(default_factory=dict, description="Timing data")
    error: str | None = Field(default=None, description="Error message if failed")
