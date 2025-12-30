"""Developer Agent implementation using LangGraph.

This module implements the Developer Agent (EXECUTOR-001) that follows the
Test-Driven Development (TDD) Red-Green-Refactor workflow:

1. WriteTest: Generate a failing test from task description
2. RunTest: Execute test in E2B sandbox (should fail - RED phase)
3. WriteCode: Generate implementation to pass tests
4. RunTest: Execute test again (should pass - GREEN phase)
5. Refactor: Improve code quality while maintaining passing tests

Key Dependencies:
- CORE-003: MCP Client for tool calls (git, filesystem)
- CORE-004: E2B Sandbox for secure test execution
- CORE-005: TDD Guard for workflow enforcement
- MODEL-001: Model Router with TaskType.CODING

CRITICAL ARCHITECTURE DECISION:
The Developer Agent uses TaskType.CODING for model routing, which is
DIFFERENT from the Validator Agent (TaskType.VALIDATION). This ensures
cross-validation between the executor and validator stages.

Workflow Graph:
    START -> write_test -> run_test -> [conditional]
                                        |-> write_code -> run_test (loop)
                                        |-> refactor -> END (complete)
                                        |-> END (error - max iterations)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from daw_agents.agents.developer.models import DeveloperResult
from daw_agents.agents.developer.nodes import (
    refactor_node,
    route_after_refactor,
    route_after_run_test,
    route_after_write_test,
    run_test_node,
    write_code_node,
    write_test_node,
)
from daw_agents.agents.developer.state import DeveloperState
from daw_agents.models.router import ModelRouter, TaskType

if TYPE_CHECKING:
    from daw_agents.mcp.client import MCPClient
    from daw_agents.sandbox.e2b import E2BSandbox
    from daw_agents.tdd.guard import TDDGuard

logger = logging.getLogger(__name__)


class Developer:
    """Developer Agent for TDD-driven code generation.

    The Developer Agent implements the Red-Green-Refactor TDD workflow:
    1. Write a failing test (RED)
    2. Write minimal code to pass (GREEN)
    3. Refactor for quality (REFACTOR)

    The agent uses ModelRouter with TaskType.CODING to ensure it uses
    a coding-optimized model (Claude Sonnet, GPT-4o, etc.).

    Attributes:
        router: ModelRouter instance for LLM calls
        task_type: Always TaskType.CODING for developer tasks
        max_iterations: Maximum TDD iterations to prevent infinite loops
        graph: Compiled LangGraph workflow
        mcp_client: Optional MCP client for tool integration
        sandbox: Optional E2B sandbox for test execution
        tdd_guard: Optional TDD guard for workflow enforcement

    Example:
        developer = Developer()
        result = await developer.execute(
            task="Create a function to add two numbers",
            source_file="src/calculator.py",
            test_file="tests/test_calculator.py"
        )
        if result.success:
            print(f"Generated code:\\n{result.source_code}")
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
        max_iterations: int = 5,
        mcp_client: MCPClient | None = None,
        sandbox: E2BSandbox | None = None,
        tdd_guard: TDDGuard | None = None,
    ) -> None:
        """Initialize the Developer Agent.

        Args:
            router: Optional ModelRouter instance. If None, creates a new one.
            max_iterations: Maximum TDD iterations to prevent infinite loops (default: 5)
            mcp_client: Optional MCP client for tool calls
            sandbox: Optional E2B sandbox for test execution
            tdd_guard: Optional TDD guard for workflow enforcement
        """
        self.router = router or ModelRouter()
        self.task_type = TaskType.CODING
        self.max_iterations = max_iterations
        self.mcp_client = mcp_client
        self.sandbox = sandbox
        self.tdd_guard = tdd_guard
        self.graph = self._build_graph()

        logger.info(
            "Developer Agent initialized with model: %s, max_iterations: %d",
            self.router.get_model_for_task(TaskType.CODING),
            self.max_iterations,
        )

    def _build_graph(self) -> Any:
        """Build the LangGraph TDD workflow.

        Creates a StateGraph with the following flow:
        START -> write_test -> run_test -> [conditional edges]
                                            |-> write_code -> run_test (loop)
                                            |-> refactor -> complete (END)
                                            |-> error (END)

        Returns:
            Compiled LangGraph workflow
        """
        # Create the state graph
        workflow = StateGraph(DeveloperState)

        # Add nodes for each TDD step
        workflow.add_node("write_test", write_test_node)
        workflow.add_node("run_test", run_test_node)
        workflow.add_node("write_code", write_code_node)
        workflow.add_node("refactor", refactor_node)

        # Entry point: Start with write_test
        workflow.add_edge(START, "write_test")

        # After write_test, always run the test (to verify it fails - RED phase)
        workflow.add_conditional_edges(
            "write_test",
            route_after_write_test,
            {
                "run_test": "run_test",
            },
        )

        # After run_test, decide based on results
        workflow.add_conditional_edges(
            "run_test",
            route_after_run_test,
            {
                "write_code": "write_code",
                "refactor": "refactor",
                "error": END,
            },
        )

        # After write_code, run tests again
        workflow.add_edge("write_code", "run_test")

        # After refactor, complete the workflow
        workflow.add_conditional_edges(
            "refactor",
            route_after_refactor,
            {
                "complete": END,
            },
        )

        # Compile the graph
        return workflow.compile()

    def configure_mcp(self, mcp_client: MCPClient) -> None:
        """Configure MCP client for tool integration.

        Args:
            mcp_client: MCPClient instance for tool calls
        """
        self.mcp_client = mcp_client
        logger.info("MCP client configured for Developer Agent")

    def configure_sandbox(self, sandbox: E2BSandbox) -> None:
        """Configure E2B sandbox for test execution.

        Args:
            sandbox: E2BSandbox instance for isolated test execution
        """
        self.sandbox = sandbox
        logger.info("E2B sandbox configured for Developer Agent")

    def configure_tdd_guard(self, tdd_guard: TDDGuard) -> None:
        """Configure TDD guard for workflow enforcement.

        Args:
            tdd_guard: TDDGuard instance for TDD enforcement
        """
        self.tdd_guard = tdd_guard
        logger.info("TDD guard configured for Developer Agent")

    async def execute(
        self,
        task: str,
        source_file: str,
        test_file: str,
    ) -> DeveloperResult:
        """Execute the TDD workflow for a given task.

        Runs the complete TDD cycle:
        1. Generate failing test
        2. Run test (should fail)
        3. Generate implementation
        4. Run test (should pass)
        5. Refactor

        Args:
            task: Description of the programming task to implement
            source_file: Path to the source file to create/modify
            test_file: Path to the test file to create

        Returns:
            DeveloperResult with the generated code and status
        """
        logger.info("Starting Developer workflow for task: %s", task)

        # Initialize state
        initial_state: DeveloperState = {
            "task_description": task,
            "source_file": source_file,
            "test_file": test_file,
            "source_code": "",
            "test_code": "",
            "status": "write_test",
            "test_result": None,
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "error": None,
        }

        # Run the workflow
        final_state = await self.graph.ainvoke(initial_state)

        # Determine success based on final status
        status = final_state.get("status", "error")
        success = status == "complete"

        # If error status, set error message
        error_msg = final_state.get("error")
        if status == "error" and not error_msg:
            if final_state.get("iteration", 0) >= self.max_iterations:
                error_msg = f"Max iterations ({self.max_iterations}) exceeded"
            else:
                error_msg = "Unknown error occurred"

        return DeveloperResult(
            success=success,
            source_file=final_state["source_file"],
            test_file=final_state["test_file"],
            source_code=final_state.get("source_code", ""),
            test_code=final_state.get("test_code", ""),
            iterations=final_state.get("iteration", 0),
            status=status,
            error=error_msg,
        )

    async def generate_test(
        self,
        task: str,
        source_file: str,
        test_file: str,
    ) -> str:
        """Generate a test file for the given task.

        Convenience method to generate just the test without running
        the full TDD cycle.

        Args:
            task: Description of the programming task
            source_file: Path to the source file to test
            test_file: Path to the test file to create

        Returns:
            Generated test code as a string
        """
        from daw_agents.agents.developer.nodes import generate_test_code

        return await generate_test_code(
            task_description=task,
            source_file=source_file,
            test_file=test_file,
        )

    async def generate_implementation(
        self,
        task: str,
        test_code: str,
        source_file: str,
    ) -> str:
        """Generate implementation code for the given test.

        Convenience method to generate implementation without running
        the full TDD cycle.

        Args:
            task: Description of the programming task
            test_code: Test code that the implementation must pass
            source_file: Path to the source file to create

        Returns:
            Generated source code as a string
        """
        from daw_agents.agents.developer.nodes import generate_source_code

        return await generate_source_code(
            task_description=task,
            test_code=test_code,
            test_result=None,
            current_source="",
            source_file=source_file,
        )
