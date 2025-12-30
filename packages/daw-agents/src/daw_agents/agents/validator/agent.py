"""Validator Agent implementation using LangGraph.

This module implements the Validator Agent as a LangGraph workflow.
The Validator Agent is DISTINCT from the Sandbox (CORE-004):
- Validator: Reviews code for correctness, security, style using LLMs
- Sandbox: Executes code in isolated E2B environment

CRITICAL ARCHITECTURE DECISION:
The Validator Agent MUST use TaskType.VALIDATION for model routing,
ensuring it uses a DIFFERENT model than the Executor (TaskType.CODING).
This enforces cross-validation and avoids model-specific blind spots.

Workflow States:
- run_tests: Execute test suite
- security_scan: Run SAST security scanning
- policy_check: Check code style/linting
- generate_report: Generate validation report
- route_decision: Decide next step (approve/retry/escalate)
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from daw_agents.agents.validator.models import ValidationResult
from daw_agents.agents.validator.nodes import (
    generate_report_node,
    policy_check_node,
    route_decision,
    run_tests_node,
    security_scan_node,
)
from daw_agents.agents.validator.state import ValidationState
from daw_agents.mcp.client import MCPClient
from daw_agents.models.router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """Validator Agent for code review and validation.

    The ValidatorAgent implements a multi-step validation workflow:
    1. Run tests and collect results
    2. Run security scanning
    3. Check code style/policy
    4. Generate validation report
    5. Route decision (approve/retry/escalate)

    The agent uses ModelRouter with TaskType.VALIDATION to ensure
    cross-validation with a different model than the Executor.

    Attributes:
        router: ModelRouter instance for LLM calls
        task_type: Always TaskType.VALIDATION for cross-validation
        max_retries: Maximum retry attempts for fixable issues
        graph: Compiled LangGraph workflow
        mcp_client: Optional MCP client for tool integration

    Example:
        agent = ValidatorAgent()
        result = await agent.validate(
            code="def hello(): return 'world'",
            requirements="Function should return 'world'"
        )
        if result.status == "approved":
            print("Code validated successfully!")
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
        max_retries: int = 3,
        mcp_client: MCPClient | None = None,
    ) -> None:
        """Initialize the ValidatorAgent.

        Args:
            router: Optional ModelRouter instance. If None, creates a new one.
            max_retries: Maximum retry attempts for fixable issues (default: 3)
            mcp_client: Optional MCP client for tool integration
        """
        self.router = router or ModelRouter()
        self.task_type = TaskType.VALIDATION
        self.max_retries = max_retries
        self.mcp_client = mcp_client
        self.graph = self._build_graph()

        logger.info(
            "ValidatorAgent initialized with model: %s",
            self.router.get_model_for_task(TaskType.VALIDATION),
        )

    def _build_graph(self) -> Any:
        """Build the LangGraph validation workflow.

        Creates a StateGraph with the following flow:
        START -> run_tests -> security_scan -> policy_check ->
        generate_report -> route_decision -> (end/retry/escalate)

        Returns:
            Compiled LangGraph workflow
        """
        # Create the state graph
        workflow = StateGraph(ValidationState)

        # Add nodes for each validation step
        workflow.add_node("run_tests", run_tests_node)
        workflow.add_node("security_scan", security_scan_node)
        workflow.add_node("policy_check", policy_check_node)
        workflow.add_node("generate_report", generate_report_node)

        # Define edges - sequential flow
        workflow.add_edge(START, "run_tests")
        workflow.add_edge("run_tests", "security_scan")
        workflow.add_edge("security_scan", "policy_check")
        workflow.add_edge("policy_check", "generate_report")

        # Add conditional edge for route decision
        workflow.add_conditional_edges(
            "generate_report",
            route_decision,
            {
                "end": END,
                "retry": END,  # In production, would route back to executor
                "escalate": END,  # In production, would route to human review
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
        logger.info("MCP client configured for ValidatorAgent")

    async def validate(
        self,
        code: str,
        requirements: str,
    ) -> ValidationResult:
        """Validate code against requirements.

        Runs the complete validation workflow:
        1. Execute tests
        2. Run security scan
        3. Check code style
        4. Generate report
        5. Make route decision

        Args:
            code: Source code to validate
            requirements: Requirements/specification to validate against

        Returns:
            ValidationResult with status, feedback, and suggestions
        """
        logger.info("Starting validation for code snippet")

        # Initialize state
        initial_state: ValidationState = {
            "code": code,
            "requirements": requirements,
            "test_results": None,
            "security_findings": None,
            "style_issues": None,
            "validation_result": None,
            "current_node": "start",
            "retry_count": 0,
            "max_retries": self.max_retries,
        }

        # Run the workflow
        result = await self.graph.ainvoke(initial_state)

        # Extract and return validation result
        validation_data = result.get("validation_result", {})

        return ValidationResult(
            status=validation_data.get("status", "rejected"),
            passed_tests=validation_data.get("passed_tests", False),
            passed_security=validation_data.get("passed_security", False),
            passed_style=validation_data.get("passed_style", False),
            feedback=validation_data.get("feedback", "Validation failed"),
            suggestions=validation_data.get("suggestions", []),
        )

    async def check_security(self, code: str) -> list[dict[str, Any]]:
        """Run security scan only.

        Convenience method to run just the security scanning step.

        Args:
            code: Source code to scan

        Returns:
            List of security findings
        """
        from daw_agents.agents.validator.nodes import run_security_scan

        result = await run_security_scan(code)
        findings: list[dict[str, Any]] = result.get("findings", [])
        return findings

    async def check_style(self, code: str) -> list[dict[str, Any]]:
        """Run style check only.

        Convenience method to run just the style checking step.

        Args:
            code: Source code to check

        Returns:
            List of style issues
        """
        from daw_agents.agents.validator.nodes import run_linter

        result = await run_linter(code)
        issues: list[dict[str, Any]] = result.get("issues", [])
        return issues
