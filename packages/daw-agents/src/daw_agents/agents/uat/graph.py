"""UAT Agent implementation using LangGraph.

This module implements the UAT Agent (UAT-001) that uses Playwright MCP
for browser automation:

1. Setup: Initialize browser via Playwright MCP
2. Navigate: Navigate to target URL and capture accessibility snapshot
3. Interact: Execute user interactions (click, type, etc.)
4. Validate: Check expected outcomes using accessibility snapshots
5. Cleanup: Close browser and generate reports

Key Dependencies:
- VALIDATOR-001: Validator Agent (for validation patterns)
- FRONTEND-002: Agent Trace UI (for trace viewing)
- CORE-003: MCP Client (for Playwright MCP integration)

CRITICAL ARCHITECTURE DECISIONS:
- Uses accessibility snapshots for determinism (not visual screenshots)
- Supports cross-browser testing (Chromium, Firefox, WebKit)
- Executes Gherkin scenarios translated from PRD acceptance criteria

Workflow Graph:
    START -> setup_browser -> navigate -> [conditional]
                                          |-> interact -> navigate/validate
                                          |-> validate -> interact/cleanup
                                          |-> cleanup -> END
                                          |-> error -> END
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from daw_agents.agents.uat.models import UATResult
from daw_agents.agents.uat.nodes import (
    cleanup_node,
    interact_node,
    navigate_node,
    route_after_interact,
    route_after_navigate,
    route_after_setup,
    route_after_validate,
    setup_browser_node,
    validate_node,
)
from daw_agents.agents.uat.parser import GherkinParser
from daw_agents.agents.uat.state import UATState

if TYPE_CHECKING:
    from daw_agents.mcp.client import MCPClient

logger = logging.getLogger(__name__)

# Valid browser types
VALID_BROWSER_TYPES = frozenset(["chromium", "firefox", "webkit"])


class UATAgent:
    """UAT Agent for browser automation using Playwright MCP.

    The UAT Agent implements browser-based acceptance testing:
    1. Parse Gherkin scenarios (Given/When/Then)
    2. Initialize browser via Playwright MCP
    3. Navigate to target URL
    4. Execute interactions (click, type, etc.)
    5. Validate outcomes using accessibility snapshots
    6. Generate validation reports with screenshots and traces

    The agent operates on accessibility snapshots for determinism and speed,
    rather than visual screenshots for assertions.

    Attributes:
        browser_type: Browser type (chromium, firefox, webkit)
        accessibility_mode: Whether to use accessibility snapshots (always True)
        parser: GherkinParser for parsing scenarios
        graph: Compiled LangGraph workflow
        mcp_client: Optional MCP client for Playwright integration

    Example:
        agent = UATAgent(browser_type="chromium")
        result = await agent.execute(
            scenario='''
                Given I am on the login page
                When I enter "user@test.com" in the email field
                And I click the submit button
                Then I should see the dashboard
            ''',
            url="http://localhost:3000/login"
        )
        if result.success:
            print(f"All validations passed!")
    """

    def __init__(
        self,
        browser_type: str = "chromium",
        mcp_client: MCPClient | None = None,
    ) -> None:
        """Initialize the UAT Agent.

        Args:
            browser_type: Browser type (chromium, firefox, webkit)
            mcp_client: Optional MCP client for Playwright MCP calls

        Raises:
            ValueError: If browser_type is not valid
        """
        if browser_type not in VALID_BROWSER_TYPES:
            raise ValueError(
                f"Invalid browser_type '{browser_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_BROWSER_TYPES))}"
            )

        self.browser_type = browser_type
        self.accessibility_mode = True  # Always use accessibility mode
        self.parser = GherkinParser()
        self.mcp_client = mcp_client
        self.graph = self._build_graph()

        logger.info(
            "UAT Agent initialized with browser_type: %s, accessibility_mode: %s",
            self.browser_type,
            self.accessibility_mode,
        )

    def _build_graph(self) -> Any:
        """Build the LangGraph UAT workflow.

        Creates a StateGraph with the following flow:
        START -> setup_browser -> navigate -> [conditional edges]
                                               |-> interact -> [loop]
                                               |-> validate -> [loop]
                                               |-> cleanup -> END
                                               |-> error -> END

        Returns:
            Compiled LangGraph workflow
        """
        # Create the state graph
        workflow = StateGraph(UATState)

        # Add nodes for each UAT step
        workflow.add_node("setup_browser", setup_browser_node)
        workflow.add_node("navigate", navigate_node)
        workflow.add_node("interact", interact_node)
        workflow.add_node("validate", validate_node)
        workflow.add_node("cleanup", cleanup_node)

        # Entry point: Start with setup_browser
        workflow.add_edge(START, "setup_browser")

        # After setup, route based on success/error
        workflow.add_conditional_edges(
            "setup_browser",
            route_after_setup,
            {
                "navigate": "navigate",
                "error": END,
            },
        )

        # After navigate, route based on next step type
        workflow.add_conditional_edges(
            "navigate",
            route_after_navigate,
            {
                "interact": "interact",
                "validate": "validate",
                "cleanup": "cleanup",
                "navigate": "navigate",
                "error": END,
            },
        )

        # After interact, route based on next step type
        workflow.add_conditional_edges(
            "interact",
            route_after_interact,
            {
                "interact": "interact",
                "validate": "validate",
                "navigate": "navigate",
                "cleanup": "cleanup",
                "error": END,
            },
        )

        # After validate, route based on next step type
        workflow.add_conditional_edges(
            "validate",
            route_after_validate,
            {
                "validate": "validate",
                "interact": "interact",
                "navigate": "navigate",
                "cleanup": "cleanup",
                "error": END,
            },
        )

        # After cleanup, end the workflow
        workflow.add_edge("cleanup", END)

        # Compile the graph
        return workflow.compile()

    def configure_mcp(self, mcp_client: MCPClient) -> None:
        """Configure MCP client for Playwright integration.

        Args:
            mcp_client: MCPClient instance for Playwright MCP calls
        """
        self.mcp_client = mcp_client
        logger.info("MCP client configured for UAT Agent")

    async def execute(
        self,
        scenario: str,
        url: str,
    ) -> UATResult:
        """Execute a UAT scenario.

        Runs the complete UAT workflow:
        1. Parse Gherkin scenario
        2. Initialize browser
        3. Navigate to URL
        4. Execute interactions
        5. Validate outcomes
        6. Generate report

        Args:
            scenario: Gherkin scenario text (Given/When/Then)
            url: Target URL for the test

        Returns:
            UATResult with validation report, screenshots, traces
        """
        logger.info("Starting UAT workflow for URL: %s", url)

        start_time = time.time()

        # Initialize state
        initial_state: UATState = {
            "scenario": scenario,
            "url": url,
            "browser_type": self.browser_type,
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {"start_time": start_time * 1000},
        }

        # Run the workflow
        final_state = await self.graph.ainvoke(initial_state)

        # Determine success based on final status and validation results
        status = final_state.get("status", "error")
        validation_results = final_state.get("validation_results", [])

        # Calculate success: all validations must pass
        all_passed = all(v.get("passed", False) for v in validation_results)
        success = status == "complete" and all_passed

        # Build validation report
        total_steps = len(validation_results)
        passed_steps = sum(1 for v in validation_results if v.get("passed", False))
        failed_steps = total_steps - passed_steps

        validation_report = {
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "results": validation_results,
        }

        # Calculate final timing
        timing = dict(final_state.get("timing", {}))
        timing["total_ms"] = (time.time() - start_time) * 1000

        return UATResult(
            success=success,
            scenario=scenario,
            status=status,
            validation_report=validation_report,
            screenshots=final_state.get("screenshots", []),
            traces=final_state.get("traces", []),
            timing=timing,
            error=final_state.get("error"),
        )

    async def validate_scenario(
        self,
        scenario: str,
    ) -> list[dict[str, Any]]:
        """Validate a Gherkin scenario without executing it.

        Parses the scenario and validates the syntax.

        Args:
            scenario: Gherkin scenario text

        Returns:
            List of parsed steps as dictionaries
        """
        steps = self.parser.parse(scenario)
        return [step.model_dump() for step in steps]
