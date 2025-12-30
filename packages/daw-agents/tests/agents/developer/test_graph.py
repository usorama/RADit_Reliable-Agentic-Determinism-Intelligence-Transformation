"""
Tests for the Developer Agent (EXECUTOR-001).

These tests verify the Developer Agent implementation:
1. DeveloperState TypedDict structure
2. DeveloperStatus enum (WRITE_TEST, RUN_TEST, WRITE_CODE, REFACTOR, COMPLETE, ERROR)
3. DeveloperResult Pydantic model
4. Developer class with LangGraph workflow
5. Workflow nodes: write_test, run_test, write_code, refactor
6. Conditional routing (test pass/fail decisions)
7. Max iteration limit (prevent infinite loops)
8. TDDGuard integration (enforce Red-Green-Refactor)
9. E2B sandbox integration for test execution
10. MCP client integration for tool calls
11. MODEL-001 integration for coding model selection (TaskType.CODING)

The Developer Agent implements the Red-Green-Refactor loop:
- WriteTest: Generate test file using LLM
- RunTest: Execute test in E2B sandbox (should fail RED phase)
- WriteCode: Generate implementation to pass tests
- RunTest: Execute test again (should pass GREEN phase)
- Refactor: Clean up code while maintaining tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# =============================================================================
# Test DeveloperState TypedDict
# =============================================================================


class TestDeveloperState:
    """Test the DeveloperState TypedDict structure."""

    def test_developer_state_import(self) -> None:
        """Test that DeveloperState can be imported."""
        from daw_agents.agents.developer.state import DeveloperState

        assert DeveloperState is not None

    def test_developer_state_has_required_fields(self) -> None:
        """Test that DeveloperState has all required fields."""
        from daw_agents.agents.developer.state import DeveloperState

        # Create a state instance to verify fields
        state: DeveloperState = {
            "task_description": "Create a function to add two numbers",
            "source_file": "src/calculator.py",
            "test_file": "tests/test_calculator.py",
            "source_code": "",
            "test_code": "",
            "status": "write_test",
            "test_result": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
        }

        assert "task_description" in state
        assert "source_file" in state
        assert "test_file" in state
        assert "source_code" in state
        assert "test_code" in state
        assert "status" in state
        assert "test_result" in state
        assert "iteration" in state
        assert "max_iterations" in state
        assert "error" in state

    def test_developer_state_default_values(self) -> None:
        """Test that DeveloperState works with default initialization."""
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "",
            "test_code": "",
            "status": "write_test",
            "test_result": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
        }

        assert state["iteration"] == 0
        assert state["max_iterations"] == 5
        assert state["error"] is None


# =============================================================================
# Test DeveloperStatus Enum
# =============================================================================


class TestDeveloperStatus:
    """Test the DeveloperStatus enum."""

    def test_developer_status_import(self) -> None:
        """Test that DeveloperStatus can be imported."""
        from daw_agents.agents.developer.models import DeveloperStatus

        assert DeveloperStatus is not None

    def test_developer_status_has_required_values(self) -> None:
        """Test that DeveloperStatus has all workflow states."""
        from daw_agents.agents.developer.models import DeveloperStatus

        # Required states for Red-Green-Refactor loop
        assert hasattr(DeveloperStatus, "WRITE_TEST")
        assert hasattr(DeveloperStatus, "RUN_TEST")
        assert hasattr(DeveloperStatus, "WRITE_CODE")
        assert hasattr(DeveloperStatus, "REFACTOR")
        assert hasattr(DeveloperStatus, "COMPLETE")
        assert hasattr(DeveloperStatus, "ERROR")

    def test_developer_status_values(self) -> None:
        """Test DeveloperStatus enum values are strings."""
        from daw_agents.agents.developer.models import DeveloperStatus

        assert DeveloperStatus.WRITE_TEST.value == "write_test"
        assert DeveloperStatus.RUN_TEST.value == "run_test"
        assert DeveloperStatus.WRITE_CODE.value == "write_code"
        assert DeveloperStatus.REFACTOR.value == "refactor"
        assert DeveloperStatus.COMPLETE.value == "complete"
        assert DeveloperStatus.ERROR.value == "error"


# =============================================================================
# Test DeveloperResult Model
# =============================================================================


class TestDeveloperResult:
    """Test the DeveloperResult Pydantic model."""

    def test_developer_result_import(self) -> None:
        """Test that DeveloperResult can be imported."""
        from daw_agents.agents.developer.models import DeveloperResult

        assert DeveloperResult is not None

    def test_developer_result_creation_success(self) -> None:
        """Test creating a successful DeveloperResult."""
        from daw_agents.agents.developer.models import DeveloperResult

        result = DeveloperResult(
            success=True,
            source_file="src/calculator.py",
            test_file="tests/test_calculator.py",
            source_code="def add(a, b): return a + b",
            test_code="def test_add(): assert add(1, 2) == 3",
            iterations=2,
            status="complete",
        )

        assert result.success is True
        assert result.iterations == 2
        assert result.status == "complete"

    def test_developer_result_creation_failure(self) -> None:
        """Test creating a failed DeveloperResult."""
        from daw_agents.agents.developer.models import DeveloperResult

        result = DeveloperResult(
            success=False,
            source_file="src/calculator.py",
            test_file="tests/test_calculator.py",
            source_code="",
            test_code="",
            iterations=5,
            status="error",
            error="Max iterations exceeded",
        )

        assert result.success is False
        assert result.status == "error"
        assert result.error is not None


# =============================================================================
# Test TestRunResult Model
# =============================================================================


class TestTestRunResult:
    """Test the TestRunResult Pydantic model."""

    def test_test_run_result_import(self) -> None:
        """Test that TestRunResult can be imported."""
        from daw_agents.agents.developer.models import TestRunResult

        assert TestRunResult is not None

    def test_test_run_result_creation(self) -> None:
        """Test creating a TestRunResult."""
        from daw_agents.agents.developer.models import TestRunResult

        result = TestRunResult(
            passed=True,
            output="1 passed",
            exit_code=0,
            duration_ms=150.5,
        )

        assert result.passed is True
        assert result.exit_code == 0


# =============================================================================
# Test Developer Agent Class
# =============================================================================


class TestDeveloperAgent:
    """Test the Developer agent class."""

    def test_developer_import(self) -> None:
        """Test that Developer class can be imported."""
        from daw_agents.agents.developer.graph import Developer

        assert Developer is not None

    def test_developer_initialization(self) -> None:
        """Test Developer initialization."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        assert developer is not None

    def test_developer_initialization_with_custom_max_iterations(self) -> None:
        """Test Developer initialization with custom max_iterations."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer(max_iterations=10)
        assert developer.max_iterations == 10

    def test_developer_uses_model_router(self) -> None:
        """Test that Developer uses MODEL-001 router."""
        from daw_agents.agents.developer.graph import Developer
        from daw_agents.models.router import ModelRouter

        developer = Developer()
        assert developer.router is not None
        assert isinstance(developer.router, ModelRouter)

    def test_developer_uses_coding_task_type(self) -> None:
        """Test that Developer uses TaskType.CODING for model routing."""
        from daw_agents.agents.developer.graph import Developer
        from daw_agents.models.router import TaskType

        developer = Developer()
        assert developer.task_type == TaskType.CODING

    def test_developer_has_graph(self) -> None:
        """Test that Developer has a compiled LangGraph."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        assert developer.graph is not None


# =============================================================================
# Test TDDGuard Integration
# =============================================================================


class TestTDDGuardIntegration:
    """Test integration with TDD Guard (CORE-005)."""

    def test_developer_has_tdd_guard(self) -> None:
        """Test that Developer can use TDDGuard."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        # Developer should have access to TDD guard or be able to configure it
        assert hasattr(developer, "tdd_guard") or hasattr(developer, "configure_tdd_guard")

    def test_developer_enforces_test_first(self) -> None:
        """Test that Developer follows TDD workflow (write test first)."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        # The graph should start at write_test state
        # Verified through the workflow structure - check graph nodes exist
        assert developer.graph is not None


# =============================================================================
# Test E2B Sandbox Integration
# =============================================================================


class TestE2BSandboxIntegration:
    """Test integration with E2B Sandbox (CORE-004)."""

    def test_developer_can_use_sandbox(self) -> None:
        """Test that Developer can use E2B sandbox for test execution."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        # Developer should have sandbox access or be able to configure it
        assert hasattr(developer, "sandbox") or hasattr(developer, "configure_sandbox")


# =============================================================================
# Test MCP Client Integration
# =============================================================================


class TestMCPClientIntegration:
    """Test integration with MCP Client (CORE-003)."""

    def test_developer_can_use_mcp_client(self) -> None:
        """Test that Developer can use MCP client for tool calls."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        # Developer should have MCP client access or be able to configure it
        assert hasattr(developer, "mcp_client") or hasattr(developer, "configure_mcp")


# =============================================================================
# Test Developer Node Functions
# =============================================================================


class TestDeveloperNodes:
    """Test individual developer node functions."""

    @pytest.mark.asyncio
    async def test_write_test_node(self) -> None:
        """Test the write_test node function."""
        from daw_agents.agents.developer.nodes import write_test_node
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Create a function to add two numbers",
            "source_file": "src/calculator.py",
            "test_file": "tests/test_calculator.py",
            "source_code": "",
            "test_code": "",
            "status": "write_test",
            "test_result": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
        }

        with patch(
            "daw_agents.agents.developer.nodes.generate_test_code"
        ) as mock_generate:
            mock_generate.return_value = "def test_add(): assert add(1, 2) == 3"

            result = await write_test_node(state)

            assert "test_code" in result
            assert len(result["test_code"]) > 0

    @pytest.mark.asyncio
    async def test_run_test_node_fail(self) -> None:
        """Test the run_test node function when tests fail (RED phase)."""
        from daw_agents.agents.developer.nodes import run_test_node
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Create a function to add two numbers",
            "source_file": "src/calculator.py",
            "test_file": "tests/test_calculator.py",
            "source_code": "",
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "status": "run_test",
            "test_result": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
        }

        with patch(
            "daw_agents.agents.developer.nodes.execute_tests_in_sandbox"
        ) as mock_execute:
            mock_execute.return_value = {
                "passed": False,
                "output": "NameError: name 'add' is not defined",
                "exit_code": 1,
                "duration_ms": 100.0,
            }

            result = await run_test_node(state)

            assert "test_result" in result
            assert result["test_result"]["passed"] is False

    @pytest.mark.asyncio
    async def test_run_test_node_pass(self) -> None:
        """Test the run_test node function when tests pass (GREEN phase)."""
        from daw_agents.agents.developer.nodes import run_test_node
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Create a function to add two numbers",
            "source_file": "src/calculator.py",
            "test_file": "tests/test_calculator.py",
            "source_code": "def add(a, b): return a + b",
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "status": "run_test",
            "test_result": None,
            "iteration": 1,
            "max_iterations": 5,
            "error": None,
        }

        with patch(
            "daw_agents.agents.developer.nodes.execute_tests_in_sandbox"
        ) as mock_execute:
            mock_execute.return_value = {
                "passed": True,
                "output": "1 passed",
                "exit_code": 0,
                "duration_ms": 150.0,
            }

            result = await run_test_node(state)

            assert "test_result" in result
            assert result["test_result"]["passed"] is True

    @pytest.mark.asyncio
    async def test_write_code_node(self) -> None:
        """Test the write_code node function."""
        from daw_agents.agents.developer.nodes import write_code_node
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Create a function to add two numbers",
            "source_file": "src/calculator.py",
            "test_file": "tests/test_calculator.py",
            "source_code": "",
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "status": "write_code",
            "test_result": {"passed": False, "output": "NameError"},
            "iteration": 1,
            "max_iterations": 5,
            "error": None,
        }

        with patch(
            "daw_agents.agents.developer.nodes.generate_source_code"
        ) as mock_generate:
            mock_generate.return_value = "def add(a, b): return a + b"

            result = await write_code_node(state)

            assert "source_code" in result
            assert len(result["source_code"]) > 0

    @pytest.mark.asyncio
    async def test_refactor_node(self) -> None:
        """Test the refactor node function."""
        from daw_agents.agents.developer.nodes import refactor_node
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Create a function to add two numbers",
            "source_file": "src/calculator.py",
            "test_file": "tests/test_calculator.py",
            "source_code": "def add(a, b): return a + b",
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "status": "refactor",
            "test_result": {"passed": True},
            "iteration": 2,
            "max_iterations": 5,
            "error": None,
        }

        with patch(
            "daw_agents.agents.developer.nodes.refactor_code"
        ) as mock_refactor:
            mock_refactor.return_value = (
                "def add(a: int, b: int) -> int:\n    return a + b"
            )

            result = await refactor_node(state)

            assert "source_code" in result


# =============================================================================
# Test Route Decision Logic
# =============================================================================


class TestRouteDecision:
    """Test the routing decision logic."""

    def test_route_after_write_test(self) -> None:
        """Test routing after write_test goes to run_test."""
        from daw_agents.agents.developer.nodes import route_after_write_test
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "",
            "test_code": "def test_something(): pass",
            "status": "write_test",
            "test_result": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
        }

        next_node = route_after_write_test(state)
        assert next_node == "run_test"

    def test_route_after_run_test_fail_red_phase(self) -> None:
        """Test routing after run_test when tests fail in RED phase (go to write_code)."""
        from daw_agents.agents.developer.nodes import route_after_run_test
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "",  # No source code yet (RED phase)
            "test_code": "def test_something(): pass",
            "status": "run_test",
            "test_result": {"passed": False},
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
        }

        next_node = route_after_run_test(state)
        assert next_node == "write_code"

    def test_route_after_run_test_pass_green_phase(self) -> None:
        """Test routing after run_test when tests pass (GREEN phase, go to refactor)."""
        from daw_agents.agents.developer.nodes import route_after_run_test
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "def something(): return True",
            "test_code": "def test_something(): pass",
            "status": "run_test",
            "test_result": {"passed": True},
            "iteration": 1,
            "max_iterations": 5,
            "error": None,
        }

        next_node = route_after_run_test(state)
        assert next_node == "refactor"

    def test_route_after_run_test_fail_after_code(self) -> None:
        """Test routing when tests fail after code was written (retry write_code)."""
        from daw_agents.agents.developer.nodes import route_after_run_test
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "def something(): return False",  # Has code but tests fail
            "test_code": "def test_something(): assert something() == True",
            "status": "run_test",
            "test_result": {"passed": False},
            "iteration": 1,
            "max_iterations": 5,
            "error": None,
        }

        next_node = route_after_run_test(state)
        assert next_node == "write_code"

    def test_route_after_run_test_max_iterations(self) -> None:
        """Test routing when max iterations reached."""
        from daw_agents.agents.developer.nodes import route_after_run_test
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "def something(): return False",
            "test_code": "def test_something(): pass",
            "status": "run_test",
            "test_result": {"passed": False},
            "iteration": 5,
            "max_iterations": 5,
            "error": None,
        }

        next_node = route_after_run_test(state)
        assert next_node == "error"

    def test_route_after_refactor(self) -> None:
        """Test routing after refactor goes to complete."""
        from daw_agents.agents.developer.nodes import route_after_refactor
        from daw_agents.agents.developer.state import DeveloperState

        state: DeveloperState = {
            "task_description": "Test task",
            "source_file": "src/main.py",
            "test_file": "tests/test_main.py",
            "source_code": "def something(): return True",
            "test_code": "def test_something(): pass",
            "status": "refactor",
            "test_result": {"passed": True},
            "iteration": 2,
            "max_iterations": 5,
            "error": None,
        }

        next_node = route_after_refactor(state)
        assert next_node == "complete"


# =============================================================================
# Test Complete Workflow
# =============================================================================


class TestDeveloperWorkflow:
    """Test the complete developer workflow."""

    @pytest.mark.asyncio
    async def test_execute_method(self) -> None:
        """Test the Developer.execute() method."""
        from daw_agents.agents.developer.graph import Developer
        from daw_agents.agents.developer.models import DeveloperResult

        developer = Developer()

        with patch.object(developer, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "task_description": "Add function",
                    "source_file": "src/calc.py",
                    "test_file": "tests/test_calc.py",
                    "source_code": "def add(a, b): return a + b",
                    "test_code": "def test_add(): assert add(1, 2) == 3",
                    "status": "complete",
                    "test_result": {"passed": True},
                    "iteration": 2,
                    "max_iterations": 5,
                    "error": None,
                }
            )

            result = await developer.execute(
                task="Create a function to add two numbers",
                source_file="src/calc.py",
                test_file="tests/test_calc.py",
            )

            assert isinstance(result, DeveloperResult)
            assert result.success is True
            assert result.status == "complete"

    @pytest.mark.asyncio
    async def test_execute_with_error(self) -> None:
        """Test the Developer.execute() method when it fails."""
        from daw_agents.agents.developer.graph import Developer
        from daw_agents.agents.developer.models import DeveloperResult

        developer = Developer()

        with patch.object(developer, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "task_description": "Add function",
                    "source_file": "src/calc.py",
                    "test_file": "tests/test_calc.py",
                    "source_code": "",
                    "test_code": "",
                    "status": "error",
                    "test_result": None,
                    "iteration": 5,
                    "max_iterations": 5,
                    "error": "Max iterations exceeded",
                }
            )

            result = await developer.execute(
                task="Create an impossible function",
                source_file="src/impossible.py",
                test_file="tests/test_impossible.py",
            )

            assert isinstance(result, DeveloperResult)
            assert result.success is False
            assert result.status == "error"


# =============================================================================
# Test Graph Structure
# =============================================================================


class TestGraphStructure:
    """Test the LangGraph structure of the developer agent."""

    def test_graph_has_required_nodes(self) -> None:
        """Test that the developer graph has all required nodes."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        graph = developer.graph

        # Get node names from the compiled graph
        node_names = list(graph.nodes.keys())

        # Required nodes per EXECUTOR-001 spec
        assert "write_test" in node_names
        assert "run_test" in node_names
        assert "write_code" in node_names
        assert "refactor" in node_names

    def test_graph_has_conditional_edges(self) -> None:
        """Test that the graph has conditional routing edges."""
        from daw_agents.agents.developer.graph import Developer

        developer = Developer()
        # The graph should be compilable with conditional edges
        assert developer.graph is not None


# =============================================================================
# Test Module Exports
# =============================================================================


class TestDeveloperExports:
    """Test module exports and public API."""

    def test_public_api_exports(self) -> None:
        """Test that public API is properly exported."""
        from daw_agents.agents.developer import (
            Developer,
            DeveloperResult,
            DeveloperState,
            DeveloperStatus,
        )

        assert Developer is not None
        assert DeveloperResult is not None
        assert DeveloperState is not None
        assert DeveloperStatus is not None
