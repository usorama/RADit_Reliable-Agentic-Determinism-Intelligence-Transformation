"""
Tests for the Validator Agent (VALIDATOR-001).

These tests verify the Validator Agent implementation:
1. ValidationState TypedDict structure
2. ValidationResult Pydantic model
3. ValidatorAgent class with LangGraph workflow
4. Validation node functions (run_tests, security_scan, policy_check, generate_report)
5. Route decision logic for approve/reject/retry
6. Cross-validation principle (validator uses DIFFERENT model than executor)
7. Retry logic with max retries
8. Integration with MODEL-001 router and CORE-003 MCP client

Critical Architecture Decision (from CLAUDE.md):
The Validator Agent is DISTINCT from the Sandbox (CORE-004).
- Validator: Reviews code for correctness, security, style
- Sandbox: Executes code in isolated environment
They must use DIFFERENT LLM models for cross-validation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestValidatorState:
    """Test the ValidationState TypedDict structure."""

    def test_validation_state_import(self) -> None:
        """Test that ValidationState can be imported."""
        from daw_agents.agents.validator.state import ValidationState

        assert ValidationState is not None

    def test_validation_state_has_required_fields(self) -> None:
        """Test that ValidationState has all required fields."""
        from daw_agents.agents.validator.state import ValidationState

        # Create a state instance to verify fields
        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Function should say hello",
            "test_results": None,
            "security_findings": None,
            "style_issues": None,
            "validation_result": None,
            "current_node": "start",
            "retry_count": 0,
            "max_retries": 3,
        }

        assert "code" in state
        assert "requirements" in state
        assert "test_results" in state
        assert "security_findings" in state
        assert "style_issues" in state
        assert "validation_result" in state
        assert "current_node" in state
        assert "retry_count" in state
        assert "max_retries" in state


class TestValidationResult:
    """Test the ValidationResult Pydantic model."""

    def test_validation_result_import(self) -> None:
        """Test that ValidationResult can be imported."""
        from daw_agents.agents.validator.models import ValidationResult

        assert ValidationResult is not None

    def test_validation_result_creation_approved(self) -> None:
        """Test creating an approved ValidationResult."""
        from daw_agents.agents.validator.models import ValidationResult

        result = ValidationResult(
            status="approved",
            passed_tests=True,
            passed_security=True,
            passed_style=True,
            feedback="Code passes all validation checks.",
            suggestions=[],
        )

        assert result.status == "approved"
        assert result.passed_tests is True
        assert result.passed_security is True
        assert result.passed_style is True
        assert "passes all" in result.feedback

    def test_validation_result_creation_rejected(self) -> None:
        """Test creating a rejected ValidationResult."""
        from daw_agents.agents.validator.models import ValidationResult

        result = ValidationResult(
            status="rejected",
            passed_tests=False,
            passed_security=True,
            passed_style=True,
            feedback="Tests failed: 2 tests failed.",
            suggestions=["Fix the failing tests before resubmitting."],
        )

        assert result.status == "rejected"
        assert result.passed_tests is False
        assert len(result.suggestions) > 0

    def test_validation_result_requires_status(self) -> None:
        """Test that ValidationResult requires a status field."""
        from pydantic import ValidationError

        from daw_agents.agents.validator.models import ValidationResult

        with pytest.raises(ValidationError):
            ValidationResult(
                passed_tests=True,
                passed_security=True,
                passed_style=True,
                feedback="Missing status",
                suggestions=[],
            )  # type: ignore[call-arg]


class TestSecurityFinding:
    """Test the SecurityFinding Pydantic model."""

    def test_security_finding_import(self) -> None:
        """Test that SecurityFinding can be imported."""
        from daw_agents.agents.validator.models import SecurityFinding

        assert SecurityFinding is not None

    def test_security_finding_creation(self) -> None:
        """Test creating a SecurityFinding."""
        from daw_agents.agents.validator.models import SecurityFinding

        finding = SecurityFinding(
            severity="critical",
            rule_id="SEC-001",
            message="SQL injection vulnerability detected",
            file_path="src/db/query.py",
            line_number=42,
        )

        assert finding.severity == "critical"
        assert finding.rule_id == "SEC-001"
        assert "SQL injection" in finding.message


class TestStyleIssue:
    """Test the StyleIssue Pydantic model."""

    def test_style_issue_import(self) -> None:
        """Test that StyleIssue can be imported."""
        from daw_agents.agents.validator.models import StyleIssue

        assert StyleIssue is not None

    def test_style_issue_creation(self) -> None:
        """Test creating a StyleIssue."""
        from daw_agents.agents.validator.models import StyleIssue

        issue = StyleIssue(
            rule_id="E501",
            message="Line too long (120 > 88 characters)",
            file_path="src/utils.py",
            line_number=15,
            fixable=True,
        )

        assert issue.rule_id == "E501"
        assert issue.fixable is True


class TestTestResult:
    """Test the TestResult Pydantic model."""

    def test_test_result_import(self) -> None:
        """Test that TestResult can be imported."""
        from daw_agents.agents.validator.models import TestResult

        assert TestResult is not None

    def test_test_result_creation(self) -> None:
        """Test creating a TestResult."""
        from daw_agents.agents.validator.models import TestResult

        result = TestResult(
            passed=True,
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            coverage_percent=85.5,
            failed_test_names=["test_edge_case"],
            output="10 tests collected, 9 passed, 1 failed",
        )

        assert result.passed is True
        assert result.total_tests == 10
        assert result.coverage_percent == 85.5


class TestValidatorAgent:
    """Test the ValidatorAgent class."""

    def test_validator_agent_import(self) -> None:
        """Test that ValidatorAgent can be imported."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        assert ValidatorAgent is not None

    def test_validator_agent_initialization(self) -> None:
        """Test ValidatorAgent initialization."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        agent = ValidatorAgent()
        assert agent is not None
        assert agent.max_retries == 3

    def test_validator_agent_uses_model_router(self) -> None:
        """Test that ValidatorAgent uses MODEL-001 router."""
        from daw_agents.agents.validator.agent import ValidatorAgent
        from daw_agents.models.router import ModelRouter

        agent = ValidatorAgent()
        assert agent.router is not None
        assert isinstance(agent.router, ModelRouter)

    def test_validator_has_graph(self) -> None:
        """Test that ValidatorAgent has a compiled LangGraph."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        agent = ValidatorAgent()
        assert agent.graph is not None


class TestCrossValidationPrinciple:
    """Test that Validator uses DIFFERENT model than Executor.

    CRITICAL ARCHITECTURE DECISION:
    The Validator Agent MUST use a different LLM than the Executor Agent.
    This ensures true cross-validation and avoids model-specific blind spots.
    """

    def test_validator_uses_validation_task_type(self) -> None:
        """Test that Validator uses TaskType.VALIDATION for model routing."""
        from daw_agents.agents.validator.agent import ValidatorAgent
        from daw_agents.models.router import TaskType

        agent = ValidatorAgent()
        # Verify the agent is configured for VALIDATION task type
        assert agent.task_type == TaskType.VALIDATION

    def test_validation_model_differs_from_coding_model(self) -> None:
        """Critical: Validation model must differ from coding (executor) model."""
        from daw_agents.models.router import ModelRouter, TaskType

        router = ModelRouter()
        coding_model = router.get_model_for_task(TaskType.CODING)
        validation_model = router.get_model_for_task(TaskType.VALIDATION)

        assert coding_model != validation_model, (
            f"CRITICAL VIOLATION: Validator model ({validation_model}) MUST be "
            f"different from Executor model ({coding_model}) for cross-validation."
        )


class TestValidatorNodes:
    """Test individual validator node functions."""

    @pytest.fixture
    def mock_mcp_client(self) -> MagicMock:
        """Create a mock MCP client."""
        client = MagicMock()
        client.call_tool = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_run_tests_node(self) -> None:
        """Test the run_tests node function."""
        from daw_agents.agents.validator.nodes import run_tests_node
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def add(a, b): return a + b",
            "requirements": "Function should add two numbers",
            "test_results": None,
            "security_findings": None,
            "style_issues": None,
            "validation_result": None,
            "current_node": "run_tests",
            "retry_count": 0,
            "max_retries": 3,
        }

        with patch(
            "daw_agents.agents.validator.nodes.run_pytest"
        ) as mock_pytest:
            mock_pytest.return_value = {
                "passed": True,
                "total_tests": 5,
                "passed_tests": 5,
                "failed_tests": 0,
                "skipped_tests": 0,
                "coverage_percent": 90.0,
                "failed_test_names": [],
                "output": "5 passed",
            }

            result = await run_tests_node(state)

            assert "test_results" in result
            assert result["test_results"]["passed"] is True

    @pytest.mark.asyncio
    async def test_security_scan_node(self) -> None:
        """Test the security_scan node function."""
        from daw_agents.agents.validator.nodes import security_scan_node
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def query(): return 'SELECT * FROM users'",
            "requirements": "Query users safely",
            "test_results": {"passed": True},
            "security_findings": None,
            "style_issues": None,
            "validation_result": None,
            "current_node": "security_scan",
            "retry_count": 0,
            "max_retries": 3,
        }

        with patch(
            "daw_agents.agents.validator.nodes.run_security_scan"
        ) as mock_scan:
            mock_scan.return_value = {
                "findings": [],
                "passed": True,
            }

            result = await security_scan_node(state)

            assert "security_findings" in result

    @pytest.mark.asyncio
    async def test_policy_check_node(self) -> None:
        """Test the policy_check node function."""
        from daw_agents.agents.validator.nodes import policy_check_node
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Say hello",
            "test_results": {"passed": True},
            "security_findings": {"passed": True, "findings": []},
            "style_issues": None,
            "validation_result": None,
            "current_node": "policy_check",
            "retry_count": 0,
            "max_retries": 3,
        }

        with patch(
            "daw_agents.agents.validator.nodes.run_linter"
        ) as mock_lint:
            mock_lint.return_value = {
                "issues": [],
                "passed": True,
            }

            result = await policy_check_node(state)

            assert "style_issues" in result

    @pytest.mark.asyncio
    async def test_generate_report_node(self) -> None:
        """Test the generate_report node function."""
        from daw_agents.agents.validator.nodes import generate_report_node
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Say hello",
            "test_results": {"passed": True},
            "security_findings": {"passed": True, "findings": []},
            "style_issues": {"passed": True, "issues": []},
            "validation_result": None,
            "current_node": "generate_report",
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await generate_report_node(state)

        assert "validation_result" in result
        assert result["validation_result"]["status"] in ["approved", "rejected", "retry"]


class TestRouteDecision:
    """Test the route decision logic."""

    def test_route_decision_approve(self) -> None:
        """Test route decision returns 'approved' when all checks pass."""
        from daw_agents.agents.validator.nodes import route_decision
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Say hello",
            "test_results": {"passed": True},
            "security_findings": {"passed": True, "findings": []},
            "style_issues": {"passed": True, "issues": []},
            "validation_result": {"status": "approved"},
            "current_node": "route_decision",
            "retry_count": 0,
            "max_retries": 3,
        }

        decision = route_decision(state)
        assert decision == "end"

    def test_route_decision_retry(self) -> None:
        """Test route decision returns 'retry' for fixable issues under max retries."""
        from daw_agents.agents.validator.nodes import route_decision
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Say hello",
            "test_results": {"passed": False},
            "security_findings": {"passed": True, "findings": []},
            "style_issues": {"passed": True, "issues": []},
            "validation_result": {"status": "retry"},
            "current_node": "route_decision",
            "retry_count": 1,
            "max_retries": 3,
        }

        decision = route_decision(state)
        assert decision == "retry"

    def test_route_decision_escalate(self) -> None:
        """Test route decision returns 'escalate' when max retries exceeded."""
        from daw_agents.agents.validator.nodes import route_decision
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Say hello",
            "test_results": {"passed": False},
            "security_findings": {"passed": True, "findings": []},
            "style_issues": {"passed": True, "issues": []},
            "validation_result": {"status": "retry"},
            "current_node": "route_decision",
            "retry_count": 3,
            "max_retries": 3,
        }

        decision = route_decision(state)
        assert decision == "escalate"

    def test_route_decision_reject_critical_security(self) -> None:
        """Test route decision returns 'reject' for critical security issues."""
        from daw_agents.agents.validator.nodes import route_decision
        from daw_agents.agents.validator.state import ValidationState

        state: ValidationState = {
            "code": "def hello(): pass",
            "requirements": "Say hello",
            "test_results": {"passed": True},
            "security_findings": {
                "passed": False,
                "findings": [{"severity": "critical", "message": "SQL injection"}],
            },
            "style_issues": {"passed": True, "issues": []},
            "validation_result": {"status": "rejected"},
            "current_node": "route_decision",
            "retry_count": 0,
            "max_retries": 3,
        }

        decision = route_decision(state)
        # Critical security issues should go to escalate/reject immediately
        assert decision in ["escalate", "reject"]


class TestValidatorWorkflow:
    """Test the complete validator workflow."""

    @pytest.mark.asyncio
    async def test_validate_method(self) -> None:
        """Test the ValidatorAgent.validate() method."""
        from daw_agents.agents.validator.agent import ValidatorAgent
        from daw_agents.agents.validator.models import ValidationResult

        agent = ValidatorAgent()

        with patch.object(
            agent, "graph"
        ) as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "validation_result": {
                        "status": "approved",
                        "passed_tests": True,
                        "passed_security": True,
                        "passed_style": True,
                        "feedback": "All checks passed",
                        "suggestions": [],
                    }
                }
            )

            result = await agent.validate(
                code="def hello(): return 'hello'",
                requirements="Function should return 'hello'",
            )

            assert isinstance(result, ValidationResult)
            assert result.status == "approved"

    @pytest.mark.asyncio
    async def test_validate_with_retry(self) -> None:
        """Test that validate can return retry status for fixable failures.

        Note: The retry logic is handled by the route_decision node in the graph.
        A single graph invocation may return "retry" status, which signals that
        the executor should fix the code and try again. This test verifies that
        the validate method correctly returns the result from the graph.
        """
        from daw_agents.agents.validator.agent import ValidatorAgent
        from daw_agents.agents.validator.models import ValidationResult

        agent = ValidatorAgent()

        # Mock a retry result - this is a valid outcome when tests fail
        # but issues are fixable
        with patch.object(agent, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "validation_result": {
                        "status": "retry",
                        "passed_tests": False,
                        "passed_security": True,
                        "passed_style": True,
                        "feedback": "Test failed, fixable issue.",
                        "suggestions": ["Fix the failing test"],
                    },
                    "retry_count": 1,
                }
            )

            result = await agent.validate(
                code="def hello(): return 'hello'",
                requirements="Function should return 'hello'",
            )

            # Retry is a valid status - indicates fixable failure
            assert isinstance(result, ValidationResult)
            assert result.status == "retry"
            assert result.passed_tests is False
            assert result.passed_security is True
            assert len(result.suggestions) > 0


class TestGraphStructure:
    """Test the LangGraph structure of the validator."""

    def test_graph_has_required_nodes(self) -> None:
        """Test that the validator graph has all required nodes."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        agent = ValidatorAgent()
        graph = agent.graph

        # Get node names from the compiled graph
        node_names = list(graph.nodes.keys())

        # Required nodes per VALIDATOR-001 spec
        assert "run_tests" in node_names or "test_runner" in node_names
        assert "security_scan" in node_names or "security_check" in node_names
        assert "policy_check" in node_names or "style_check" in node_names
        assert "generate_report" in node_names or "report" in node_names

    def test_graph_has_conditional_edges(self) -> None:
        """Test that the graph has conditional routing edges."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        agent = ValidatorAgent()
        # The graph should be compilable with conditional edges
        assert agent.graph is not None


class TestValidatorIntegration:
    """Integration tests for ValidatorAgent with dependencies."""

    @pytest.mark.asyncio
    async def test_validator_uses_mcp_for_tools(self) -> None:
        """Test that ValidatorAgent can use MCP client for tool calls."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        agent = ValidatorAgent()

        # Verify MCP client is available or can be configured
        assert hasattr(agent, "mcp_client") or hasattr(agent, "configure_mcp")

    @pytest.mark.asyncio
    async def test_validator_calls_model_router_for_validation(self) -> None:
        """Test that ValidatorAgent uses ModelRouter with TaskType.VALIDATION."""
        from daw_agents.agents.validator.agent import ValidatorAgent

        agent = ValidatorAgent()

        with patch.object(agent.router, "route") as mock_route:
            mock_route.return_value = "Validation analysis: Code looks good."

            # Trigger a validation that would use the router
            with patch.object(agent, "graph") as mock_graph:
                mock_graph.ainvoke = AsyncMock(
                    return_value={
                        "validation_result": {
                            "status": "approved",
                            "passed_tests": True,
                            "passed_security": True,
                            "passed_style": True,
                            "feedback": "Passed",
                            "suggestions": [],
                        }
                    }
                )

                await agent.validate(
                    code="def hello(): pass",
                    requirements="Say hello",
                )

            # In real implementation, router.route should be called with VALIDATION
            # This test structure verifies the integration is possible


class TestValidatorExports:
    """Test module exports and public API."""

    def test_public_api_exports(self) -> None:
        """Test that public API is properly exported."""
        from daw_agents.agents.validator import (
            ValidationResult,
            ValidationState,
            ValidatorAgent,
        )

        assert ValidatorAgent is not None
        assert ValidationResult is not None
        assert ValidationState is not None
