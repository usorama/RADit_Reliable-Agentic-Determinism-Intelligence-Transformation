"""Developer state definition for Developer Agent.

This module defines the TypedDict state schema for the LangGraph Developer workflow.
The Developer Agent implements the Red-Green-Refactor TDD loop:

1. WriteTest: Generate failing test first
2. RunTest: Execute test (should fail in RED phase)
3. WriteCode: Generate implementation to pass tests
4. RunTest: Execute test again (should pass in GREEN phase)
5. Refactor: Clean up code while maintaining passing tests

The state tracks:
- Task description and file paths
- Source and test code content
- Current workflow status
- Test results
- Iteration count and limits
- Error information
"""

from __future__ import annotations

from typing import Any, TypedDict


class DeveloperState(TypedDict):
    """State schema for the Developer Agent LangGraph workflow.

    Attributes:
        task_description: The programming task to implement
        source_file: Path to the source file to create/modify
        test_file: Path to the test file to create/modify
        source_code: Current source code content
        test_code: Current test code content
        status: Current workflow status (write_test, run_test, write_code, refactor, complete, error)
        test_result: Result from the last test execution (None if not yet run)
        iteration: Current iteration count in the TDD loop
        max_iterations: Maximum allowed iterations to prevent infinite loops
        error: Error message if workflow fails (None if no error)
    """

    task_description: str
    source_file: str
    test_file: str
    source_code: str
    test_code: str
    status: str
    test_result: dict[str, Any] | None
    iteration: int
    max_iterations: int
    error: str | None
