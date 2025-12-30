"""Validation state definition for Validator Agent.

This module defines the TypedDict state schema for the LangGraph validation workflow.
The state tracks:
- Code being validated
- Requirements to validate against
- Results from each validation step
- Current workflow position
- Retry tracking for fixable issues
"""

from __future__ import annotations

from typing import Any, TypedDict


class ValidationState(TypedDict):
    """State schema for the Validator Agent LangGraph workflow.

    Attributes:
        code: The source code being validated
        requirements: The requirements/specification to validate against
        test_results: Results from running tests (None if not yet run)
        security_findings: Security scan findings (None if not yet run)
        style_issues: Code style/linting issues (None if not yet run)
        validation_result: Final validation result (None until complete)
        current_node: Current position in the workflow graph
        retry_count: Number of retry attempts made
        max_retries: Maximum allowed retry attempts
    """

    code: str
    requirements: str
    test_results: dict[str, Any] | None
    security_findings: dict[str, Any] | None
    style_issues: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    current_node: str
    retry_count: int
    max_retries: int
