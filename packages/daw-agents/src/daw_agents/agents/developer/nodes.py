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
import time
from typing import Any

from daw_agents.agents.developer.state import DeveloperState
from daw_agents.models.router import ModelRouter, TaskType
from daw_agents.sandbox.e2b import E2BSandbox

logger = logging.getLogger(__name__)

# Module-level router instance (lazy-initialized)
_router: ModelRouter | None = None


def _get_router() -> ModelRouter:
    """Get or create the module-level ModelRouter instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


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
    logger.info("Generating test code for: %s", task_description)

    router = _get_router()

    prompt = f"""You are a TDD expert. Write pytest test code for the following task.

Task Description:
{task_description}

Source file path: {source_file}
Test file path: {test_file}

Requirements:
1. Write comprehensive pytest tests that will initially FAIL (Red phase of TDD)
2. Tests should cover edge cases and error conditions
3. Use descriptive test names that explain what is being tested
4. Include necessary imports (pytest, the module being tested)
5. Do NOT include any implementation code, only tests

Return ONLY the Python test code, no explanations or markdown formatting.
"""

    messages = [{"role": "user", "content": prompt}]

    test_code = await router.route(
        task_type=TaskType.CODING,
        messages=messages,
        metadata={"phase": "red", "source_file": source_file},
    )

    return test_code


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
    logger.info("Executing tests in sandbox: %s", test_file)

    start_time = time.time()

    try:
        sandbox = E2BSandbox.from_env()

        async with sandbox:
            # Write source code to sandbox
            await sandbox.write_file(f"/home/user/{source_file}", source_code)

            # Write test code to sandbox
            await sandbox.write_file(f"/home/user/{test_file}", test_code)

            # Install pytest if not present and run tests
            result = await sandbox.run_command(
                f"cd /home/user && pip install -q pytest && python -m pytest {test_file} -v",
                timeout=120,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Combine stdout and stderr for full output
            output = result.stdout
            if result.stderr:
                output += f"\n\nSTDERR:\n{result.stderr}"

            passed = result.exit_code == 0

            return {
                "passed": passed,
                "output": output,
                "exit_code": result.exit_code,
                "duration_ms": duration_ms,
            }

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("Sandbox execution failed: %s", str(e))
        return {
            "passed": False,
            "output": f"Sandbox execution error: {e}",
            "exit_code": -1,
            "duration_ms": duration_ms,
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
    logger.info("Generating source code for: %s", task_description)

    router = _get_router()

    # Build context about test failures if available
    test_context = ""
    if test_result:
        test_context = f"""
Previous Test Run Results:
- Passed: {test_result.get('passed', False)}
- Exit Code: {test_result.get('exit_code', 'N/A')}
- Output:
{test_result.get('output', 'No output')}
"""

    current_source_context = ""
    if current_source and current_source.strip():
        current_source_context = f"""
Current Implementation (needs fixing):
```python
{current_source}
```
"""

    prompt = f"""You are a TDD expert implementing the GREEN phase. Write Python code that makes the tests pass.

Task Description:
{task_description}

Tests to Pass:
```python
{test_code}
```
{test_context}
{current_source_context}
Source file path: {source_file}

Requirements:
1. Write minimal implementation code to make ALL tests pass
2. Follow Python best practices and type hints
3. Include proper docstrings
4. Do NOT modify the tests, only implement the source code

Return ONLY the Python source code, no explanations or markdown formatting.
"""

    messages = [{"role": "user", "content": prompt}]

    source_code = await router.route(
        task_type=TaskType.CODING,
        messages=messages,
        metadata={"phase": "green", "source_file": source_file},
    )

    return source_code


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
    logger.info("Refactoring source code")

    router = _get_router()

    prompt = f"""You are a TDD expert performing the REFACTOR phase. Improve the code quality while ensuring tests still pass.

Original Task Description:
{task_description}

Current Implementation:
```python
{source_code}
```

Tests That Must Still Pass:
```python
{test_code}
```

Refactoring Guidelines:
1. Improve code readability and maintainability
2. Apply SOLID principles where appropriate
3. Improve naming for clarity
4. Add or improve type hints
5. Optimize performance if possible without sacrificing readability
6. Ensure proper error handling
7. DO NOT change the public API - tests must still pass

Return ONLY the refactored Python source code, no explanations or markdown formatting.
"""

    messages = [{"role": "user", "content": prompt}]

    refactored_code = await router.route(
        task_type=TaskType.CODING,
        messages=messages,
        metadata={"phase": "refactor"},
    )

    return refactored_code


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
