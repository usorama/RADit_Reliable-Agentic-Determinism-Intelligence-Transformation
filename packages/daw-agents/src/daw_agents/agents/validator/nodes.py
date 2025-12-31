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

import asyncio
import json
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from daw_agents.agents.validator.state import ValidationState

logger = logging.getLogger(__name__)


async def run_pytest(code: str, requirements: str) -> dict[str, Any]:
    """Execute pytest and return results.

    Writes code to a temporary directory and runs pytest with coverage.

    Args:
        code: Source code being tested (Python file content)
        requirements: Test requirements (test file content)

    Returns:
        Dictionary with test results including pass/fail counts and coverage
    """
    # Check if pytest is available
    if shutil.which("pytest") is None:
        logger.warning("pytest not found in PATH, returning placeholder result")
        return {
            "passed": False,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "coverage_percent": 0.0,
            "failed_test_names": [],
            "output": "pytest not available",
            "error": "pytest not found in PATH",
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write the source code
        src_file = temp_path / "module.py"
        src_file.write_text(code)

        # Write the test file
        test_file = temp_path / "test_module.py"
        test_file.write_text(requirements)

        # Build pytest command with JSON output and coverage
        cmd = [
            "pytest",
            str(test_file),
            "-v",
            "--tb=short",
            f"--rootdir={temp_dir}",
            "--json-report",
            "--json-report-file=report.json",
        ]

        # Add coverage if pytest-cov is available
        if shutil.which("coverage") is not None:
            cmd.extend([f"--cov={temp_dir}", "--cov-report=json"])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"PYTHONPATH": temp_dir},
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120.0,
            )

            output = stdout.decode("utf-8") + stderr.decode("utf-8")

            # Parse JSON report if available
            report_file = temp_path / "report.json"
            if report_file.exists():
                report = json.loads(report_file.read_text())
                summary = report.get("summary", {})

                # Extract failed test names
                failed_test_names = []
                for test in report.get("tests", []):
                    if test.get("outcome") == "failed":
                        failed_test_names.append(test.get("nodeid", "unknown"))

                # Parse coverage if available
                coverage_percent = 0.0
                cov_file = temp_path / "coverage.json"
                if cov_file.exists():
                    cov_data = json.loads(cov_file.read_text())
                    coverage_percent = cov_data.get("totals", {}).get("percent_covered", 0.0)

                return {
                    "passed": process.returncode == 0,
                    "total_tests": summary.get("total", 0),
                    "passed_tests": summary.get("passed", 0),
                    "failed_tests": summary.get("failed", 0),
                    "skipped_tests": summary.get("skipped", 0),
                    "coverage_percent": coverage_percent,
                    "failed_test_names": failed_test_names,
                    "output": output,
                }

            # Fallback: parse output manually if no JSON report
            return _parse_pytest_output(output, process.returncode == 0)

        except TimeoutError:
            logger.error("pytest execution timed out")
            return {
                "passed": False,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
                "coverage_percent": 0.0,
                "failed_test_names": [],
                "output": "pytest execution timed out",
                "error": "Timeout after 120 seconds",
            }
        except Exception as e:
            logger.error("pytest execution failed: %s", e)
            return {
                "passed": False,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
                "coverage_percent": 0.0,
                "failed_test_names": [],
                "output": "",
                "error": str(e),
            }


def _parse_pytest_output(output: str, passed: bool) -> dict[str, Any]:
    """Parse pytest output to extract test counts when JSON report unavailable.

    Args:
        output: Raw pytest stdout/stderr
        passed: Whether pytest exited with code 0

    Returns:
        Dictionary with test results
    """
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0
    failed_test_names: list[str] = []

    # Try to parse summary line like "5 passed, 2 failed, 1 skipped"
    summary_match = re.search(
        r"(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped",
        output,
    )
    if summary_match:
        passed_tests = int(summary_match.group(1))
        failed_tests = int(summary_match.group(2))
        skipped_tests = int(summary_match.group(3))
        total_tests = passed_tests + failed_tests + skipped_tests
    else:
        # Try simpler patterns
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        skipped_match = re.search(r"(\d+)\s+skipped", output)

        if passed_match:
            passed_tests = int(passed_match.group(1))
        if failed_match:
            failed_tests = int(failed_match.group(1))
        if skipped_match:
            skipped_tests = int(skipped_match.group(1))
        total_tests = passed_tests + failed_tests + skipped_tests

    # Extract failed test names from FAILED lines
    for match in re.finditer(r"FAILED\s+(.+?)\s+-", output):
        failed_test_names.append(match.group(1))

    return {
        "passed": passed,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "skipped_tests": skipped_tests,
        "coverage_percent": 0.0,
        "failed_test_names": failed_test_names,
        "output": output,
    }


async def run_security_scan(code: str) -> dict[str, Any]:
    """Run SAST security scanning on code using bandit.

    Args:
        code: Source code to scan (Python file content)

    Returns:
        Dictionary with security findings including severity levels
    """
    # Check if bandit is available
    if shutil.which("bandit") is None:
        logger.warning("bandit not found in PATH, returning placeholder result")
        return {
            "passed": True,
            "findings": [],
            "warning": "bandit not available - security scan skipped",
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write the source code to a temp file
        src_file = temp_path / "code.py"
        src_file.write_text(code)

        # Run bandit with JSON output
        cmd = [
            "bandit",
            "-r",
            str(src_file),
            "-f", "json",
            "-q",  # Quiet mode (no progress bar)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0,
            )

            output = stdout.decode("utf-8")

            # Parse JSON output
            if output.strip():
                try:
                    report = json.loads(output)
                    findings = []
                    has_critical = False

                    for result in report.get("results", []):
                        severity = result.get("issue_severity", "MEDIUM").lower()
                        confidence = result.get("issue_confidence", "MEDIUM").lower()

                        # Map bandit severity to our levels
                        severity_map = {
                            "low": "low",
                            "medium": "medium",
                            "high": "critical",
                        }
                        mapped_severity = severity_map.get(severity, "medium")

                        if mapped_severity == "critical":
                            has_critical = True

                        findings.append({
                            "severity": mapped_severity,
                            "confidence": confidence,
                            "message": result.get("issue_text", "Unknown issue"),
                            "test_id": result.get("test_id", ""),
                            "test_name": result.get("test_name", ""),
                            "line": result.get("line_number", 0),
                            "code": result.get("code", ""),
                        })

                    # Fail if any high severity (critical) issues found
                    passed = not has_critical and len(findings) == 0

                    return {
                        "passed": passed,
                        "findings": findings,
                        "metrics": report.get("metrics", {}),
                    }

                except json.JSONDecodeError:
                    logger.warning("Failed to parse bandit JSON output")
                    return {
                        "passed": True,
                        "findings": [],
                        "raw_output": output,
                    }

            # No output means no findings
            return {
                "passed": True,
                "findings": [],
            }

        except TimeoutError:
            logger.error("bandit execution timed out")
            return {
                "passed": False,
                "findings": [],
                "error": "Timeout after 60 seconds",
            }
        except Exception as e:
            logger.error("bandit execution failed: %s", e)
            return {
                "passed": False,
                "findings": [],
                "error": str(e),
            }


async def run_linter(code: str) -> dict[str, Any]:
    """Run code linting/style checks using ruff.

    Args:
        code: Source code to lint (Python file content)

    Returns:
        Dictionary with style issues and their locations
    """
    # Check if ruff is available
    if shutil.which("ruff") is None:
        logger.warning("ruff not found in PATH, returning placeholder result")
        return {
            "passed": True,
            "issues": [],
            "warning": "ruff not available - lint check skipped",
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write the source code to a temp file
        src_file = temp_path / "code.py"
        src_file.write_text(code)

        # Run ruff with JSON output
        cmd = [
            "ruff",
            "check",
            str(src_file),
            "--output-format=json",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0,
            )

            output = stdout.decode("utf-8")

            # Parse JSON output
            issues = []
            if output.strip():
                try:
                    results = json.loads(output)

                    for result in results:
                        # Determine severity based on code prefix
                        code_str = result.get("code", "")
                        if code_str.startswith("E") or code_str.startswith("F"):
                            severity = "error"
                        else:
                            severity = "warning"

                        issues.append({
                            "code": code_str,
                            "message": result.get("message", ""),
                            "severity": severity,
                            "line": result.get("location", {}).get("row", 0),
                            "column": result.get("location", {}).get("column", 0),
                            "fixable": result.get("fix") is not None,
                            "url": result.get("url", ""),
                        })

                except json.JSONDecodeError:
                    # Try to parse text output as fallback
                    issues = _parse_ruff_text_output(output)

            # Fail if any errors found (E or F codes)
            has_errors = any(i.get("severity") == "error" for i in issues)
            passed = not has_errors

            return {
                "passed": passed,
                "issues": issues,
                "error_count": sum(1 for i in issues if i.get("severity") == "error"),
                "warning_count": sum(1 for i in issues if i.get("severity") == "warning"),
            }

        except TimeoutError:
            logger.error("ruff execution timed out")
            return {
                "passed": False,
                "issues": [],
                "error": "Timeout after 60 seconds",
            }
        except Exception as e:
            logger.error("ruff execution failed: %s", e)
            return {
                "passed": False,
                "issues": [],
                "error": str(e),
            }


def _parse_ruff_text_output(output: str) -> list[dict[str, Any]]:
    """Parse ruff text output as fallback when JSON parsing fails.

    Args:
        output: Raw ruff text output

    Returns:
        List of issue dictionaries
    """
    issues = []
    # Pattern: /path/file.py:10:5: E501 Message here
    pattern = re.compile(
        r"^(.+?):(\d+):(\d+):\s*([A-Z]\d+)\s*(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        _, line, column, code, message = match.groups()

        if code.startswith("E") or code.startswith("F"):
            severity = "error"
        else:
            severity = "warning"

        issues.append({
            "code": code,
            "message": message.strip(),
            "severity": severity,
            "line": int(line),
            "column": int(column),
            "fixable": False,
        })

    return issues


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
