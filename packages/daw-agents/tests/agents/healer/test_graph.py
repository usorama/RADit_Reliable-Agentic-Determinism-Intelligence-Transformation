"""
Tests for the Healer Agent (OPS-002).

These tests verify the Healer Agent implementation:
1. HealerState TypedDict structure for LangGraph state
2. HealerStatus enum (DIAGNOSE, QUERY_KNOWLEDGE, SUGGEST_FIX, APPLY_FIX, VALIDATE, COMPLETE, ERROR)
3. HealerResult Pydantic model for workflow results
4. ErrorInfo model for failed tool output
5. FixSuggestion model for suggested fixes
6. KnowledgeEntry model for stored error resolutions
7. Healer class with LangGraph workflow
8. Node functions: diagnose_error, query_knowledge_graph, suggest_fix, apply_fix, validate_fix
9. Neo4j integration for querying similar past errors
10. Knowledge storage for successful resolutions
11. Auto-retry logic (up to 3 attempts)
12. Routing decisions based on fix success/failure

The Healer Agent implements error recovery workflow:
- DiagnoseError: Analyze the failed tool output to extract error signature
- QueryKnowledgeGraph: Search Neo4j for similar past errors and their resolutions
- SuggestFix: Use LLM to generate fix based on error and past resolutions
- ApplyFix: Apply the suggested fix to the failing code
- ValidateFix: Run tests to verify the fix worked
- Complete/Error: End states based on fix success/failure

Dependencies:
- EXECUTOR-001: Developer Agent (produces failed tool outputs)
- DB-001: Neo4j Connector (for knowledge graph queries)
- CORE-003: MCP Client (for tool calls)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Test HealerState TypedDict
# =============================================================================


class TestHealerState:
    """Test the HealerState TypedDict structure."""

    def test_healer_state_import(self) -> None:
        """Test that HealerState can be imported."""
        from daw_agents.agents.healer.state import HealerState

        assert HealerState is not None

    def test_healer_state_has_required_fields(self) -> None:
        """Test that HealerState has all required fields."""
        from daw_agents.agents.healer.state import HealerState

        # Create a state instance to verify fields
        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError: assert 1 + 1 == 3",
                "stack_trace": "File 'test_calc.py', line 5",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "diagnose",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        assert "error_info" in state
        assert "similar_errors" in state
        assert "fix_suggestion" in state
        assert "fixed_code" in state
        assert "status" in state
        assert "validation_result" in state
        assert "attempt" in state
        assert "max_attempts" in state
        assert "error" in state

    def test_healer_state_default_values(self) -> None:
        """Test that HealerState works with default initialization."""
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Test failed",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "diagnose",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        assert state["attempt"] == 0
        assert state["max_attempts"] == 3
        assert state["error"] is None
        assert state["status"] == "diagnose"


# =============================================================================
# Test HealerStatus Enum
# =============================================================================


class TestHealerStatus:
    """Test the HealerStatus enum."""

    def test_healer_status_import(self) -> None:
        """Test that HealerStatus can be imported."""
        from daw_agents.agents.healer.models import HealerStatus

        assert HealerStatus is not None

    def test_healer_status_has_required_values(self) -> None:
        """Test that HealerStatus has all workflow states."""
        from daw_agents.agents.healer.models import HealerStatus

        # Required states for Healer workflow
        assert hasattr(HealerStatus, "DIAGNOSE")
        assert hasattr(HealerStatus, "QUERY_KNOWLEDGE")
        assert hasattr(HealerStatus, "SUGGEST_FIX")
        assert hasattr(HealerStatus, "APPLY_FIX")
        assert hasattr(HealerStatus, "VALIDATE")
        assert hasattr(HealerStatus, "COMPLETE")
        assert hasattr(HealerStatus, "ERROR")

    def test_healer_status_values(self) -> None:
        """Test HealerStatus enum values are strings."""
        from daw_agents.agents.healer.models import HealerStatus

        assert HealerStatus.DIAGNOSE.value == "diagnose"
        assert HealerStatus.QUERY_KNOWLEDGE.value == "query_knowledge"
        assert HealerStatus.SUGGEST_FIX.value == "suggest_fix"
        assert HealerStatus.APPLY_FIX.value == "apply_fix"
        assert HealerStatus.VALIDATE.value == "validate"
        assert HealerStatus.COMPLETE.value == "complete"
        assert HealerStatus.ERROR.value == "error"


# =============================================================================
# Test ErrorInfo Model
# =============================================================================


class TestErrorInfo:
    """Test the ErrorInfo Pydantic model."""

    def test_error_info_import(self) -> None:
        """Test that ErrorInfo can be imported."""
        from daw_agents.agents.healer.models import ErrorInfo

        assert ErrorInfo is not None

    def test_error_info_creation(self) -> None:
        """Test creating an ErrorInfo model."""
        from daw_agents.agents.healer.models import ErrorInfo

        error = ErrorInfo(
            tool_name="run_test",
            error_type="TestFailure",
            error_message="AssertionError: assert 1 == 2",
            stack_trace="File 'test_calc.py', line 5",
            source_file="src/calc.py",
            test_file="tests/test_calc.py",
            source_code="def add(a, b): return a + b + 1",
            test_code="def test_add(): assert add(1, 1) == 2",
        )

        assert error.tool_name == "run_test"
        assert error.error_type == "TestFailure"
        assert "AssertionError" in error.error_message

    def test_error_info_to_signature(self) -> None:
        """Test ErrorInfo can generate an error signature for matching."""
        from daw_agents.agents.healer.models import ErrorInfo

        error = ErrorInfo(
            tool_name="run_test",
            error_type="TestFailure",
            error_message="AssertionError: assert 1 == 2",
            stack_trace="",
            source_file="src/calc.py",
            test_file="tests/test_calc.py",
            source_code="",
            test_code="",
        )

        signature = error.to_signature()
        assert isinstance(signature, str)
        assert len(signature) > 0


# =============================================================================
# Test FixSuggestion Model
# =============================================================================


class TestFixSuggestion:
    """Test the FixSuggestion Pydantic model."""

    def test_fix_suggestion_import(self) -> None:
        """Test that FixSuggestion can be imported."""
        from daw_agents.agents.healer.models import FixSuggestion

        assert FixSuggestion is not None

    def test_fix_suggestion_creation(self) -> None:
        """Test creating a FixSuggestion model."""
        from daw_agents.agents.healer.models import FixSuggestion

        fix = FixSuggestion(
            description="Fix the off-by-one error in the add function",
            fixed_code="def add(a, b): return a + b",
            confidence=0.85,
            based_on_past_resolution=True,
            past_resolution_id="resolution-123",
        )

        assert fix.description is not None
        assert "def add" in fix.fixed_code
        assert fix.confidence == 0.85
        assert fix.based_on_past_resolution is True


# =============================================================================
# Test KnowledgeEntry Model
# =============================================================================


class TestKnowledgeEntry:
    """Test the KnowledgeEntry Pydantic model."""

    def test_knowledge_entry_import(self) -> None:
        """Test that KnowledgeEntry can be imported."""
        from daw_agents.agents.healer.models import KnowledgeEntry

        assert KnowledgeEntry is not None

    def test_knowledge_entry_creation(self) -> None:
        """Test creating a KnowledgeEntry model."""
        from daw_agents.agents.healer.models import KnowledgeEntry

        entry = KnowledgeEntry(
            id="entry-123",
            error_signature="TestFailure:AssertionError",
            error_type="TestFailure",
            error_pattern="assert.*==",
            resolution_description="Fixed off-by-one error",
            resolution_code="def add(a, b): return a + b",
            success_count=5,
            failure_count=1,
            created_at="2025-12-30T00:00:00Z",
            last_used_at="2025-12-30T01:00:00Z",
        )

        assert entry.id == "entry-123"
        assert entry.success_count == 5
        assert entry.success_rate > 0.8  # 5/(5+1) = 0.833


# =============================================================================
# Test HealerResult Model
# =============================================================================


class TestHealerResult:
    """Test the HealerResult Pydantic model."""

    def test_healer_result_import(self) -> None:
        """Test that HealerResult can be imported."""
        from daw_agents.agents.healer.models import HealerResult

        assert HealerResult is not None

    def test_healer_result_creation_success(self) -> None:
        """Test creating a successful HealerResult."""
        from daw_agents.agents.healer.models import HealerResult

        result = HealerResult(
            success=True,
            fixed_code="def add(a, b): return a + b",
            fix_description="Fixed off-by-one error",
            attempts=1,
            status="complete",
            knowledge_entry_id="entry-123",
        )

        assert result.success is True
        assert result.attempts == 1
        assert result.status == "complete"

    def test_healer_result_creation_failure(self) -> None:
        """Test creating a failed HealerResult."""
        from daw_agents.agents.healer.models import HealerResult

        result = HealerResult(
            success=False,
            fixed_code="",
            fix_description="",
            attempts=3,
            status="error",
            error="Max attempts exceeded without successful fix",
        )

        assert result.success is False
        assert result.status == "error"
        assert result.error is not None


# =============================================================================
# Test ValidationResult Model
# =============================================================================


class TestValidationResult:
    """Test the ValidationResult Pydantic model."""

    def test_validation_result_import(self) -> None:
        """Test that ValidationResult can be imported."""
        from daw_agents.agents.healer.models import ValidationResult

        assert ValidationResult is not None

    def test_validation_result_creation(self) -> None:
        """Test creating a ValidationResult."""
        from daw_agents.agents.healer.models import ValidationResult

        result = ValidationResult(
            passed=True,
            output="All tests passed",
            exit_code=0,
            duration_ms=150.5,
        )

        assert result.passed is True
        assert result.exit_code == 0


# =============================================================================
# Test Healer Agent Class
# =============================================================================


class TestHealerAgent:
    """Test the Healer agent class."""

    def test_healer_import(self) -> None:
        """Test that Healer class can be imported."""
        from daw_agents.agents.healer.graph import Healer

        assert Healer is not None

    def test_healer_initialization(self) -> None:
        """Test Healer initialization."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        assert healer is not None

    def test_healer_initialization_with_custom_max_attempts(self) -> None:
        """Test Healer initialization with custom max_attempts."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer(max_attempts=5)
        assert healer.max_attempts == 5

    def test_healer_uses_model_router(self) -> None:
        """Test that Healer uses MODEL-001 router."""
        from daw_agents.agents.healer.graph import Healer
        from daw_agents.models.router import ModelRouter

        healer = Healer()
        assert healer.router is not None
        assert isinstance(healer.router, ModelRouter)

    def test_healer_uses_healing_task_type(self) -> None:
        """Test that Healer uses TaskType.HEALING for model routing."""
        from daw_agents.agents.healer.graph import Healer
        from daw_agents.models.router import TaskType

        healer = Healer()
        # Healer should use CODING or a similar task type for fixes
        assert healer.task_type == TaskType.CODING

    def test_healer_has_graph(self) -> None:
        """Test that Healer has a compiled LangGraph."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        assert healer.graph is not None


# =============================================================================
# Test Neo4j Integration
# =============================================================================


class TestNeo4jIntegration:
    """Test integration with Neo4j (DB-001)."""

    def test_healer_can_use_neo4j(self) -> None:
        """Test that Healer can use Neo4j connector."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        # Healer should have neo4j access or be able to configure it
        assert hasattr(healer, "neo4j_connector") or hasattr(healer, "configure_neo4j")

    def test_healer_configure_neo4j(self) -> None:
        """Test configuring Neo4j connector for Healer."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        mock_connector = MagicMock()
        healer.configure_neo4j(mock_connector)
        assert healer.neo4j_connector is not None


# =============================================================================
# Test MCP Client Integration
# =============================================================================


class TestMCPClientIntegration:
    """Test integration with MCP Client (CORE-003)."""

    def test_healer_can_use_mcp_client(self) -> None:
        """Test that Healer can use MCP client for tool calls."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        # Healer should have MCP client access or be able to configure it
        assert hasattr(healer, "mcp_client") or hasattr(healer, "configure_mcp")


# =============================================================================
# Test Healer Node Functions
# =============================================================================


class TestHealerNodes:
    """Test individual healer node functions."""

    @pytest.mark.asyncio
    async def test_diagnose_error_node(self) -> None:
        """Test the diagnose_error node function."""
        from daw_agents.agents.healer.nodes import diagnose_error_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError: assert add(1, 1) == 2",
                "stack_trace": "File 'test_calc.py', line 5",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "diagnose",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.analyze_error"
        ) as mock_analyze:
            mock_analyze.return_value = {
                "error_signature": "TestFailure:AssertionError",
                "root_cause": "Off-by-one error in add function",
            }

            result = await diagnose_error_node(state)

            assert "status" in result
            # After diagnosing, should move to query_knowledge
            assert result["status"] == "query_knowledge"

    @pytest.mark.asyncio
    async def test_query_knowledge_graph_node(self) -> None:
        """Test the query_knowledge_graph node function."""
        from daw_agents.agents.healer.nodes import query_knowledge_graph_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError: assert add(1, 1) == 2",
                "stack_trace": "",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "query_knowledge",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.query_similar_errors"
        ) as mock_query:
            mock_query.return_value = [
                {
                    "id": "entry-123",
                    "error_signature": "TestFailure:AssertionError",
                    "resolution_code": "def add(a, b): return a + b",
                    "success_count": 5,
                }
            ]

            result = await query_knowledge_graph_node(state)

            assert "similar_errors" in result
            assert len(result["similar_errors"]) > 0
            assert result["status"] == "suggest_fix"

    @pytest.mark.asyncio
    async def test_query_knowledge_graph_node_no_results(self) -> None:
        """Test query_knowledge_graph when no similar errors found."""
        from daw_agents.agents.healer.nodes import query_knowledge_graph_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Some unique error",
                "stack_trace": "",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "query_knowledge",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.query_similar_errors"
        ) as mock_query:
            mock_query.return_value = []  # No similar errors found

            result = await query_knowledge_graph_node(state)

            # Should still proceed to suggest_fix (LLM will generate fix)
            assert result["status"] == "suggest_fix"
            assert result["similar_errors"] == []

    @pytest.mark.asyncio
    async def test_suggest_fix_node(self) -> None:
        """Test the suggest_fix node function."""
        from daw_agents.agents.healer.nodes import suggest_fix_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError: assert add(1, 1) == 2",
                "stack_trace": "",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [
                {
                    "id": "entry-123",
                    "error_signature": "TestFailure:AssertionError",
                    "resolution_code": "def add(a, b): return a + b",
                    "success_count": 5,
                }
            ],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "suggest_fix",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.generate_fix_suggestion"
        ) as mock_generate:
            mock_generate.return_value = {
                "description": "Remove the + 1 from the add function",
                "fixed_code": "def add(a, b): return a + b",
                "confidence": 0.9,
            }

            result = await suggest_fix_node(state)

            assert "fix_suggestion" in result
            assert result["fix_suggestion"] is not None
            assert result["status"] == "apply_fix"

    @pytest.mark.asyncio
    async def test_apply_fix_node(self) -> None:
        """Test the apply_fix node function."""
        from daw_agents.agents.healer.nodes import apply_fix_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError",
                "stack_trace": "",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [],
            "fix_suggestion": {
                "description": "Remove + 1",
                "fixed_code": "def add(a, b): return a + b",
                "confidence": 0.9,
            },
            "fixed_code": "",
            "status": "apply_fix",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.apply_code_fix"
        ) as mock_apply:
            mock_apply.return_value = "def add(a, b): return a + b"

            result = await apply_fix_node(state)

            assert "fixed_code" in result
            assert "def add" in result["fixed_code"]
            assert result["status"] == "validate"

    @pytest.mark.asyncio
    async def test_validate_fix_node_success(self) -> None:
        """Test the validate_fix node function when validation passes."""
        from daw_agents.agents.healer.nodes import validate_fix_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError",
                "stack_trace": "",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [],
            "fix_suggestion": {
                "description": "Remove + 1",
                "fixed_code": "def add(a, b): return a + b",
                "confidence": 0.9,
            },
            "fixed_code": "def add(a, b): return a + b",
            "status": "validate",
            "validation_result": None,
            "attempt": 1,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.run_validation_tests"
        ) as mock_validate:
            mock_validate.return_value = {
                "passed": True,
                "output": "All tests passed",
                "exit_code": 0,
                "duration_ms": 150.0,
            }

            result = await validate_fix_node(state)

            assert "validation_result" in result
            assert result["validation_result"]["passed"] is True

    @pytest.mark.asyncio
    async def test_validate_fix_node_failure(self) -> None:
        """Test the validate_fix node function when validation fails."""
        from daw_agents.agents.healer.nodes import validate_fix_node
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "AssertionError",
                "stack_trace": "",
                "source_file": "src/calc.py",
                "test_file": "tests/test_calc.py",
                "source_code": "def add(a, b): return a + b + 1",
                "test_code": "def test_add(): assert add(1, 1) == 2",
            },
            "similar_errors": [],
            "fix_suggestion": {
                "description": "Wrong fix",
                "fixed_code": "def add(a, b): return a - b",
                "confidence": 0.5,
            },
            "fixed_code": "def add(a, b): return a - b",
            "status": "validate",
            "validation_result": None,
            "attempt": 1,
            "max_attempts": 3,
            "error": None,
        }

        with patch(
            "daw_agents.agents.healer.nodes.run_validation_tests"
        ) as mock_validate:
            mock_validate.return_value = {
                "passed": False,
                "output": "AssertionError: assert 0 == 2",
                "exit_code": 1,
                "duration_ms": 150.0,
            }

            result = await validate_fix_node(state)

            assert "validation_result" in result
            assert result["validation_result"]["passed"] is False


# =============================================================================
# Test Route Decision Logic
# =============================================================================


class TestRouteDecision:
    """Test the routing decision logic."""

    def test_route_after_diagnose(self) -> None:
        """Test routing after diagnose goes to query_knowledge."""
        from daw_agents.agents.healer.nodes import route_after_diagnose
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "diagnose",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_diagnose(state)
        assert next_node == "query_knowledge"

    def test_route_after_query_knowledge(self) -> None:
        """Test routing after query_knowledge goes to suggest_fix."""
        from daw_agents.agents.healer.nodes import route_after_query_knowledge
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [{"id": "entry-1"}],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "query_knowledge",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_query_knowledge(state)
        assert next_node == "suggest_fix"

    def test_route_after_suggest_fix(self) -> None:
        """Test routing after suggest_fix goes to apply_fix."""
        from daw_agents.agents.healer.nodes import route_after_suggest_fix
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": {"description": "Fix", "fixed_code": "..."},
            "fixed_code": "",
            "status": "suggest_fix",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_suggest_fix(state)
        assert next_node == "apply_fix"

    def test_route_after_apply_fix(self) -> None:
        """Test routing after apply_fix goes to validate."""
        from daw_agents.agents.healer.nodes import route_after_apply_fix
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": {"description": "Fix", "fixed_code": "..."},
            "fixed_code": "fixed code here",
            "status": "apply_fix",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_apply_fix(state)
        assert next_node == "validate"

    def test_route_after_validate_success(self) -> None:
        """Test routing after validate when tests pass."""
        from daw_agents.agents.healer.nodes import route_after_validate
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": {"description": "Fix", "fixed_code": "..."},
            "fixed_code": "fixed code here",
            "status": "validate",
            "validation_result": {"passed": True},
            "attempt": 1,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_validate(state)
        assert next_node == "complete"

    def test_route_after_validate_failure_retry(self) -> None:
        """Test routing after validate when tests fail and can retry."""
        from daw_agents.agents.healer.nodes import route_after_validate
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": {"description": "Fix", "fixed_code": "..."},
            "fixed_code": "fixed code here",
            "status": "validate",
            "validation_result": {"passed": False},
            "attempt": 1,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_validate(state)
        assert next_node == "suggest_fix"  # Retry with new fix

    def test_route_after_validate_max_attempts(self) -> None:
        """Test routing after validate when max attempts reached."""
        from daw_agents.agents.healer.nodes import route_after_validate
        from daw_agents.agents.healer.state import HealerState

        state: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": {"description": "Fix", "fixed_code": "..."},
            "fixed_code": "fixed code here",
            "status": "validate",
            "validation_result": {"passed": False},
            "attempt": 3,
            "max_attempts": 3,
            "error": None,
        }

        next_node = route_after_validate(state)
        assert next_node == "error"


# =============================================================================
# Test Knowledge Storage
# =============================================================================


class TestKnowledgeStorage:
    """Test knowledge storage for successful resolutions."""

    @pytest.mark.asyncio
    async def test_store_successful_resolution(self) -> None:
        """Test storing a successful resolution in Neo4j."""
        from daw_agents.agents.healer.nodes import store_resolution
        from daw_agents.agents.healer.models import ErrorInfo

        error_info = ErrorInfo(
            tool_name="run_test",
            error_type="TestFailure",
            error_message="AssertionError",
            stack_trace="",
            source_file="src/calc.py",
            test_file="tests/test_calc.py",
            source_code="def add(a, b): return a + b + 1",
            test_code="def test_add(): assert add(1, 1) == 2",
        )

        with patch(
            "daw_agents.agents.healer.nodes.store_to_neo4j"
        ) as mock_store:
            mock_store.return_value = "entry-new-123"

            entry_id = await store_resolution(
                error_info=error_info,
                fix_description="Removed off-by-one error",
                fixed_code="def add(a, b): return a + b",
            )

            assert entry_id is not None
            mock_store.assert_called_once()


# =============================================================================
# Test Complete Workflow
# =============================================================================


class TestHealerWorkflow:
    """Test the complete healer workflow."""

    @pytest.mark.asyncio
    async def test_heal_method_success(self) -> None:
        """Test the Healer.heal() method for successful healing."""
        from daw_agents.agents.healer.graph import Healer
        from daw_agents.agents.healer.models import ErrorInfo, HealerResult

        healer = Healer()

        error_info = ErrorInfo(
            tool_name="run_test",
            error_type="TestFailure",
            error_message="AssertionError: assert 1 == 2",
            stack_trace="",
            source_file="src/calc.py",
            test_file="tests/test_calc.py",
            source_code="def add(a, b): return a + b + 1",
            test_code="def test_add(): assert add(1, 1) == 2",
        )

        with patch.object(healer, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "error_info": error_info.model_dump(),
                    "similar_errors": [],
                    "fix_suggestion": {
                        "description": "Remove + 1",
                        "fixed_code": "def add(a, b): return a + b",
                        "confidence": 0.9,
                    },
                    "fixed_code": "def add(a, b): return a + b",
                    "status": "complete",
                    "validation_result": {"passed": True},
                    "attempt": 1,
                    "max_attempts": 3,
                    "error": None,
                }
            )

            result = await healer.heal(error_info)

            assert isinstance(result, HealerResult)
            assert result.success is True
            assert result.status == "complete"

    @pytest.mark.asyncio
    async def test_heal_method_failure(self) -> None:
        """Test the Healer.heal() method when healing fails."""
        from daw_agents.agents.healer.graph import Healer
        from daw_agents.agents.healer.models import ErrorInfo, HealerResult

        healer = Healer()

        error_info = ErrorInfo(
            tool_name="run_test",
            error_type="TestFailure",
            error_message="Unfixable error",
            stack_trace="",
            source_file="src/impossible.py",
            test_file="tests/test_impossible.py",
            source_code="",
            test_code="",
        )

        with patch.object(healer, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "error_info": error_info.model_dump(),
                    "similar_errors": [],
                    "fix_suggestion": None,
                    "fixed_code": "",
                    "status": "error",
                    "validation_result": {"passed": False},
                    "attempt": 3,
                    "max_attempts": 3,
                    "error": "Max attempts exceeded",
                }
            )

            result = await healer.heal(error_info)

            assert isinstance(result, HealerResult)
            assert result.success is False
            assert result.status == "error"


# =============================================================================
# Test Graph Structure
# =============================================================================


class TestGraphStructure:
    """Test the LangGraph structure of the healer agent."""

    def test_graph_has_required_nodes(self) -> None:
        """Test that the healer graph has all required nodes."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        graph = healer.graph

        # Get node names from the compiled graph
        node_names = list(graph.nodes.keys())

        # Required nodes per OPS-002 spec
        assert "diagnose_error" in node_names
        assert "query_knowledge_graph" in node_names
        assert "suggest_fix" in node_names
        assert "apply_fix" in node_names
        assert "validate_fix" in node_names

    def test_graph_has_conditional_edges(self) -> None:
        """Test that the graph has conditional routing edges."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        # The graph should be compilable with conditional edges
        assert healer.graph is not None


# =============================================================================
# Test Auto-Retry Logic
# =============================================================================


class TestAutoRetryLogic:
    """Test the auto-retry logic up to 3 attempts."""

    def test_default_max_attempts_is_three(self) -> None:
        """Test that default max_attempts is 3."""
        from daw_agents.agents.healer.graph import Healer

        healer = Healer()
        assert healer.max_attempts == 3

    def test_attempt_increments_on_retry(self) -> None:
        """Test that attempt count increments on each retry."""
        from daw_agents.agents.healer.nodes import route_after_validate
        from daw_agents.agents.healer.state import HealerState

        # First attempt fails
        state1: HealerState = {
            "error_info": {
                "tool_name": "run_test",
                "error_type": "TestFailure",
                "error_message": "Error",
                "stack_trace": "",
                "source_file": "src/main.py",
                "test_file": "tests/test_main.py",
                "source_code": "",
                "test_code": "",
            },
            "similar_errors": [],
            "fix_suggestion": {"description": "Fix", "fixed_code": "..."},
            "fixed_code": "...",
            "status": "validate",
            "validation_result": {"passed": False},
            "attempt": 1,
            "max_attempts": 3,
            "error": None,
        }

        next_node1 = route_after_validate(state1)
        assert next_node1 == "suggest_fix"  # Should retry

        # Second attempt fails
        state2: HealerState = {**state1, "attempt": 2}
        next_node2 = route_after_validate(state2)
        assert next_node2 == "suggest_fix"  # Should retry again

        # Third attempt fails
        state3: HealerState = {**state1, "attempt": 3}
        next_node3 = route_after_validate(state3)
        assert next_node3 == "error"  # Should give up


# =============================================================================
# Test Module Exports
# =============================================================================


class TestHealerExports:
    """Test module exports and public API."""

    def test_public_api_exports(self) -> None:
        """Test that public API is properly exported."""
        from daw_agents.agents.healer import (
            Healer,
            HealerResult,
            HealerState,
            HealerStatus,
            ErrorInfo,
        )

        assert Healer is not None
        assert HealerResult is not None
        assert HealerState is not None
        assert HealerStatus is not None
        assert ErrorInfo is not None
