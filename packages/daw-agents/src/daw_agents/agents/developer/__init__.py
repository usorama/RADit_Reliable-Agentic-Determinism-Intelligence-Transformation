"""Developer Agent package for TDD-driven code generation.

This package implements the Developer Agent (EXECUTOR-001) which follows
the Test-Driven Development (TDD) Red-Green-Refactor workflow.

Exports:
    Developer: Main agent class with LangGraph workflow
    DeveloperState: TypedDict state schema for the workflow
    DeveloperStatus: Enum for workflow states
    DeveloperResult: Pydantic model for workflow results
    TestRunResult: Pydantic model for test execution results

Dependencies:
    - CORE-003: MCP Client for tool calls
    - CORE-004: E2B Sandbox for test execution
    - CORE-005: TDD Guard for workflow enforcement
    - MODEL-001: Model Router with TaskType.CODING

Example:
    from daw_agents.agents.developer import Developer, DeveloperResult

    developer = Developer()
    result = await developer.execute(
        task="Create a function to add two numbers",
        source_file="src/calculator.py",
        test_file="tests/test_calculator.py"
    )
    if result.success:
        print(f"Generated code:\n{result.source_code}")
"""

from daw_agents.agents.developer.graph import Developer
from daw_agents.agents.developer.models import (
    DeveloperResult,
    DeveloperStatus,
    TestRunResult,
)
from daw_agents.agents.developer.state import DeveloperState

__all__ = [
    "Developer",
    "DeveloperResult",
    "DeveloperState",
    "DeveloperStatus",
    "TestRunResult",
]
