"""Node functions for Validator Agent LangGraph workflow.

This module implements the node functions for each validation step:
- run_tests_node: Execute test suite and collect results
- security_scan_node: Run SAST security scanning
- policy_check_node: Check code style/linting
- generate_report_node: Generate final validation report
- route_decision: Determine next step (approve/retry/escalate)

CRITICAL: All validation uses TaskType.VALIDATION for model routing
to ensure cross-validation (different model than Executor/CODING).
"""

from __future__ import annotations

import logging
from typing import Any

from daw_agents.agents.validator.state import ValidationState

logger = logging.getLogger(__name__)


async def run_pytest(code: str, requirements: str) -> dict[str, Any]:
    """Execute pytest and return results.

    This is a placeholder that would integrate with actual test execution.
    In production, this would:
    1. Write code to temp directory
    2. Run pytest with coverage
    3. Parse and return results

    Args:
        code: Source code being tested
        requirements: Test requirements

    Returns:
        Dictionary with test results
    """
    # Placeholder implementation - in production would run actual tests
    return {
        "passed": True,
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "skipped_tests": 0,
        "coverage_percent": 0.0,
        "failed_test_names": [],
        "output": "No tests executed (placeholder)",
    }


async def run_security_scan(code: str) -> dict[str, Any]:
    """Run SAST security scanning on code.

    This is a placeholder that would integrate with security tools.
    In production, this would:
    1. Run bandit (Python) or similar SAST tool
    2. Parse findings by severity
    3. Return structured results

    Args:
        code: Source code to scan

    Returns:
        Dictionary with security findings
    """
    # Placeholder implementation - in production would run actual scanner
    return {
        "passed": True,
        "findings": [],
    }


async def run_linter(code: str) -> dict[str, Any]:
    """Run code linting/style checks.

    This is a placeholder that would integrate with linting tools.
    In production, this would:
    1. Run ruff (Python) or eslint (JS/TS)
    2. Collect style issues
    3. Return structured results

    Args:
        code: Source code to lint

    Returns:
        Dictionary with style issues
    """
    # Placeholder implementation - in production would run actual linter
    return {
        "passed": True,
        "issues": [],
    }


async def run_tests_node(state: ValidationState) -> dict[str, Any]:
    """Execute test suite and update state with results.

    This node:
    1. Runs pytest on the code being validated
    2. Collects pass/fail counts and coverage
    3. Updates state with test_results

    Args:
        state: Current validation state

    Returns:
        State update with test_results
    """
    logger.info("Running tests for validation")

    test_results = await run_pytest(state["code"], state["requirements"])

    logger.info(
        "Test results: %d passed, %d failed",
        test_results.get("passed_tests", 0),
        test_results.get("failed_tests", 0),
    )

    return {
        "test_results": test_results,
        "current_node": "security_scan",
    }


async def security_scan_node(state: ValidationState) -> dict[str, Any]:
    """Run security scanning and update state with findings.

    This node:
    1. Runs SAST security scanner on code
    2. Categorizes findings by severity
    3. Updates state with security_findings

    Args:
        state: Current validation state

    Returns:
        State update with security_findings
    """
    logger.info("Running security scan")

    security_results = await run_security_scan(state["code"])

    findings_count = len(security_results.get("findings", []))
    logger.info("Security scan complete: %d findings", findings_count)

    return {
        "security_findings": security_results,
        "current_node": "policy_check",
    }


async def policy_check_node(state: ValidationState) -> dict[str, Any]:
    """Run policy/style checks and update state with issues.

    This node:
    1. Runs linter/style checker on code
    2. Collects style issues and fixable status
    3. Updates state with style_issues

    Args:
        state: Current validation state

    Returns:
        State update with style_issues
    """
    logger.info("Running policy/style check")

    style_results = await run_linter(state["code"])

    issues_count = len(style_results.get("issues", []))
    logger.info("Style check complete: %d issues", issues_count)

    return {
        "style_issues": style_results,
        "current_node": "generate_report",
    }


async def generate_report_node(state: ValidationState) -> dict[str, Any]:
    """Generate final validation report based on all checks.

    This node:
    1. Aggregates results from all validation steps
    2. Determines final status (approved/rejected/retry)
    3. Generates feedback and suggestions
    4. Updates state with validation_result

    Args:
        state: Current validation state

    Returns:
        State update with validation_result
    """
    logger.info("Generating validation report")

    # Extract results from state
    test_results = state.get("test_results") or {}
    security_findings = state.get("security_findings") or {}
    style_issues = state.get("style_issues") or {}

    # Determine pass/fail for each category
    tests_passed = test_results.get("passed", True)
    security_passed = security_findings.get("passed", True)
    style_passed = style_issues.get("passed", True)

    # Check for critical security issues
    has_critical_security = False
    for finding in security_findings.get("findings", []):
        if finding.get("severity") == "critical":
            has_critical_security = True
            break

    # Determine overall status
    all_passed = tests_passed and security_passed and style_passed

    if all_passed:
        status = "approved"
        feedback = "Code passes all validation checks."
        suggestions: list[str] = []
    elif has_critical_security:
        status = "rejected"
        feedback = "Critical security issues found. Manual review required."
        suggestions = [
            f["message"] for f in security_findings.get("findings", [])
            if f.get("severity") == "critical"
        ]
    elif not tests_passed:
        # Tests failed but no critical security - retry possible
        status = "retry"
        feedback = f"Tests failed: {test_results.get('failed_tests', 0)} failures."
        suggestions = [f"Fix failing tests: {test_results.get('failed_test_names', [])}"]
    elif not style_passed:
        # Style issues - retry possible
        status = "retry"
        feedback = f"Style check failed: {len(style_issues.get('issues', []))} issues."
        suggestions = ["Fix style issues before resubmitting."]
    else:
        # Security issues (non-critical)
        status = "retry"
        feedback = "Security warnings found."
        suggestions = [f["message"] for f in security_findings.get("findings", [])]

    validation_result = {
        "status": status,
        "passed_tests": tests_passed,
        "passed_security": security_passed,
        "passed_style": style_passed,
        "feedback": feedback,
        "suggestions": suggestions,
    }

    logger.info("Validation result: %s", status)

    return {
        "validation_result": validation_result,
        "current_node": "route_decision",
    }


def route_decision(state: ValidationState) -> str:
    """Determine the next step based on validation results.

    Routing logic:
    - approved: Go to END (success)
    - retry: Go back to executor if under max retries
    - rejected/escalate: Go to human review

    Args:
        state: Current validation state

    Returns:
        Next node name: "end", "retry", or "escalate"
    """
    validation_result = state.get("validation_result") or {}
    status = validation_result.get("status", "rejected")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    # Check for critical security issues - always escalate
    security_findings = state.get("security_findings") or {}
    for finding in security_findings.get("findings", []):
        if finding.get("severity") == "critical":
            logger.warning("Critical security issue - escalating to human review")
            return "escalate"

    if status == "approved":
        logger.info("Validation approved")
        return "end"
    elif status == "retry" and retry_count < max_retries:
        logger.info("Validation failed, retrying (%d/%d)", retry_count + 1, max_retries)
        return "retry"
    else:
        logger.warning("Max retries exceeded or rejected - escalating")
        return "escalate"
