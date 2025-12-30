"""Node functions for the Developer Agent LangGraph workflow.

This module implements the node functions for the TDD workflow:

1. write_test_node: Generate a failing test from task description
2. run_test_node: Execute tests in E2B sandbox
3. write_code_node: Generate implementation to pass tests
4. refactor_node: Improve code quality

And routing functions:
- route_after_write_test: Always go to run_test
- route_after_run_test: Decide based on pass/fail and iteration count
- route_after_refactor: Go to complete

Dependencies:
- CORE-003: MCP Client for tool calls
- CORE-004: E2B Sandbox for test execution
- CORE-005: TDD Guard for workflow enforcement
- MODEL-001: Model Router with TaskType.CODING
"""

from __future__ import annotations

import logging
from typing import Any

from daw_agents.agents.developer.state import DeveloperState

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions (to be mocked in tests)
# =============================================================================


async def generate_test_code(
    task_description: str,
    source_file: str,
    test_file: str,
) -> str:
    """Generate test code from task description using LLM.

    This function is called by write_test_node and can be mocked in tests.

    Args:
        task_description: Description of the programming task
        source_file: Path to the source file to test
        test_file: Path to the test file to create

    Returns:
        Generated test code as a string
    """
    # In production, this would use ModelRouter with TaskType.CODING
    # For now, return a placeholder
    logger.info("Generating test code for: %s", task_description)
    return f'"""Tests for {source_file}"""\n\ndef test_placeholder():\n    pass'


async def execute_tests_in_sandbox(
    test_code: str,
    source_code: str,
    test_file: str,
    source_file: str,
) -> dict[str, Any]:
    """Execute tests in E2B sandbox.

    This function is called by run_test_node and can be mocked in tests.

    Args:
        test_code: Test code to execute
        source_code: Source code to test against
        test_file: Path to test file
        source_file: Path to source file

    Returns:
        Dictionary with test results (passed, output, exit_code, duration_ms)
    """
    # In production, this would use E2B sandbox (CORE-004)
    logger.info("Executing tests in sandbox: %s", test_file)
    return {
        "passed": False,
        "output": "No tests executed (placeholder)",
        "exit_code": 1,
        "duration_ms": 0.0,
    }


async def generate_source_code(
    task_description: str,
    test_code: str,
    test_result: dict[str, Any] | None,
    current_source: str,
    source_file: str,
) -> str:
    """Generate source code to pass the tests using LLM.

    This function is called by write_code_node and can be mocked in tests.

    Args:
        task_description: Description of the programming task
        test_code: Test code to pass
        test_result: Result from the last test run
        current_source: Current source code (for iterative fixes)
        source_file: Path to source file

    Returns:
        Generated source code as a string
    """
    # In production, this would use ModelRouter with TaskType.CODING
    logger.info("Generating source code for: %s", task_description)
    return f'"""Implementation for {source_file}"""\n\ndef placeholder():\n    pass'


async def refactor_code(
    source_code: str,
    test_code: str,
    task_description: str,
) -> str:
    """Refactor source code while maintaining passing tests.

    This function is called by refactor_node and can be mocked in tests.

    Args:
        source_code: Current source code
        test_code: Test code that must still pass
        task_description: Original task description for context

    Returns:
        Refactored source code as a string
    """
    # In production, this would use ModelRouter with TaskType.CODING
    logger.info("Refactoring source code")
    return source_code  # Return unchanged for now


# =============================================================================
# Node Functions
# =============================================================================


async def write_test_node(state: DeveloperState) -> dict[str, Any]:
    """Generate a failing test from the task description.

    This is the first step in the TDD workflow (RED phase).
    The generated test should fail because the implementation doesn't exist yet.

    Args:
        state: Current developer state

    Returns:
        State updates with generated test_code and updated status
    """
    logger.info("Executing write_test_node for: %s", state["task_description"])

    test_code = await generate_test_code(
        task_description=state["task_description"],
        source_file=state["source_file"],
        test_file=state["test_file"],
    )

    return {
        "test_code": test_code,
        "status": "run_test",
    }


async def run_test_node(state: DeveloperState) -> dict[str, Any]:
    """Execute tests in the E2B sandbox.

    This node runs tests and records the results.
    In RED phase, tests should fail.
    In GREEN phase, tests should pass.

    Args:
        state: Current developer state

    Returns:
        State updates with test_result and incremented iteration
    """
    logger.info("Executing run_test_node, iteration: %d", state["iteration"])

    result = await execute_tests_in_sandbox(
        test_code=state["test_code"],
        source_code=state["source_code"],
        test_file=state["test_file"],
        source_file=state["source_file"],
    )

    return {
        "test_result": result,
        "iteration": state["iteration"] + 1,
    }


async def write_code_node(state: DeveloperState) -> dict[str, Any]:
    """Generate implementation code to pass the tests.

    This is the GREEN phase - write minimal code to make tests pass.

    Args:
        state: Current developer state

    Returns:
        State updates with generated source_code and updated status
    """
    logger.info("Executing write_code_node, iteration: %d", state["iteration"])

    source_code = await generate_source_code(
        task_description=state["task_description"],
        test_code=state["test_code"],
        test_result=state["test_result"],
        current_source=state["source_code"],
        source_file=state["source_file"],
    )

    return {
        "source_code": source_code,
        "status": "run_test",
    }


async def refactor_node(state: DeveloperState) -> dict[str, Any]:
    """Refactor code while maintaining passing tests.

    This is the REFACTOR phase - improve code quality.

    Args:
        state: Current developer state

    Returns:
        State updates with refactored source_code and updated status
    """
    logger.info("Executing refactor_node")

    source_code = await refactor_code(
        source_code=state["source_code"],
        test_code=state["test_code"],
        task_description=state["task_description"],
    )

    return {
        "source_code": source_code,
        "status": "complete",
    }


# =============================================================================
# Routing Functions
# =============================================================================


def route_after_write_test(state: DeveloperState) -> str:
    """Route after write_test node.

    Always proceeds to run_test to verify the test fails (RED phase).

    Args:
        state: Current developer state

    Returns:
        Next node name: "run_test"
    """
    return "run_test"


def route_after_run_test(state: DeveloperState) -> str:
    """Route after run_test node based on test results.

    Decision logic:
    - If max iterations exceeded: go to "error"
    - If tests pass: go to "refactor" (GREEN phase complete)
    - If tests fail and no source code: go to "write_code" (RED phase, write impl)
    - If tests fail and has source code: go to "write_code" (fix implementation)

    Args:
        state: Current developer state

    Returns:
        Next node name: "refactor", "write_code", or "error"
    """
    test_result = state.get("test_result", {})
    passed = test_result.get("passed", False) if test_result else False
    iteration = state["iteration"]
    max_iterations = state["max_iterations"]

    # Check for max iterations
    if iteration >= max_iterations:
        logger.warning("Max iterations (%d) reached", max_iterations)
        return "error"

    # Tests passed - move to refactor phase
    if passed:
        logger.info("Tests passed - moving to refactor phase")
        return "refactor"

    # Tests failed - need to write/fix code
    logger.info("Tests failed - moving to write_code")
    return "write_code"


def route_after_refactor(state: DeveloperState) -> str:
    """Route after refactor node.

    After refactoring, the workflow is complete.

    Args:
        state: Current developer state

    Returns:
        Next node name: "complete"
    """
    return "complete"
