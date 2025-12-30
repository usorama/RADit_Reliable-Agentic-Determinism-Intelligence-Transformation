"""Pydantic models for Validator Agent.

This module defines the data models for validation results:
- ValidationResult: The final validation outcome
- SecurityFinding: Individual security vulnerability findings
- StyleIssue: Code style/linting issues
- TestResult: Test execution results
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TestResult(BaseModel):
    """Result from running test suite.

    Attributes:
        passed: Whether all tests passed
        total_tests: Total number of tests run
        passed_tests: Number of tests that passed
        failed_tests: Number of tests that failed
        skipped_tests: Number of tests that were skipped
        coverage_percent: Code coverage percentage (0-100)
        failed_test_names: Names of tests that failed
        output: Raw output from test runner
    """

    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    coverage_percent: float = 0.0
    failed_test_names: list[str] = Field(default_factory=list)
    output: str = ""


class SecurityFinding(BaseModel):
    """Individual security vulnerability finding.

    Attributes:
        severity: Severity level (critical, high, medium, low)
        rule_id: Identifier for the security rule that was triggered
        message: Human-readable description of the finding
        file_path: Path to the file containing the vulnerability
        line_number: Line number where the vulnerability was found
    """

    severity: Literal["critical", "high", "medium", "low"]
    rule_id: str
    message: str
    file_path: str = ""
    line_number: int = 0


class StyleIssue(BaseModel):
    """Code style/linting issue.

    Attributes:
        rule_id: Linting rule identifier (e.g., E501, W503)
        message: Description of the style issue
        file_path: Path to the file with the issue
        line_number: Line number of the issue
        fixable: Whether the issue can be auto-fixed
    """

    rule_id: str
    message: str
    file_path: str = ""
    line_number: int = 0
    fixable: bool = False


class ValidationResult(BaseModel):
    """Final validation result for code review.

    Attributes:
        status: Validation outcome (approved, rejected, retry)
        passed_tests: Whether all tests passed
        passed_security: Whether security scan passed
        passed_style: Whether style checks passed
        feedback: Human-readable summary of validation
        suggestions: List of actionable improvement suggestions
        test_result: Detailed test results (optional)
        security_findings: List of security findings (optional)
        style_issues: List of style issues (optional)
    """

    status: Literal["approved", "rejected", "retry"]
    passed_tests: bool = False
    passed_security: bool = False
    passed_style: bool = False
    feedback: str = ""
    suggestions: list[str] = Field(default_factory=list)
    test_result: TestResult | None = None
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    style_issues: list[StyleIssue] = Field(default_factory=list)
