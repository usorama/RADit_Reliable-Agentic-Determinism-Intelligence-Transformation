"""
Tests for the UAT Agent (UAT-001).

These tests verify the UAT Agent implementation:
1. UATState TypedDict structure
2. UATStatus enum (SETUP, NAVIGATE, INTERACT, VALIDATE, COMPLETE, ERROR)
3. UATResult Pydantic model with validation_report, screenshots, traces
4. UATAgent class with LangGraph workflow
5. Workflow nodes: setup_browser, navigate, interact, validate, cleanup
6. GherkinParser for Given/When/Then scenarios
7. Accessibility snapshot mode (not visual screenshots for assertions)
8. Cross-browser support via browser_type parameter

The UAT Agent uses Playwright MCP for browser automation:
- Operates on accessibility snapshots for determinism and speed
- Supports cross-browser testing (Chromium, Firefox, WebKit)
- Executes Gherkin scenarios translated from PRD acceptance criteria
- Generates validation reports with screenshots, traces, and timing
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Test UATState TypedDict
# =============================================================================


class TestUATState:
    """Test the UATState TypedDict structure."""

    def test_uat_state_import(self) -> None:
        """Test that UATState can be imported."""
        from daw_agents.agents.uat.state import UATState

        assert UATState is not None

    def test_uat_state_has_required_fields(self) -> None:
        """Test that UATState has all required fields."""
        from daw_agents.agents.uat.state import UATState

        # Create a state instance to verify fields
        state: UATState = {
            "scenario": "Given I am on the login page...",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        assert "scenario" in state
        assert "url" in state
        assert "browser_type" in state
        assert "status" in state
        assert "current_step" in state
        assert "steps" in state
        assert "accessibility_snapshots" in state
        assert "screenshots" in state
        assert "traces" in state
        assert "validation_results" in state
        assert "error" in state
        assert "timing" in state

    def test_uat_state_default_browser_type(self) -> None:
        """Test that UATState works with different browser types."""
        from daw_agents.agents.uat.state import UATState

        # Test chromium
        state_chromium: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }
        assert state_chromium["browser_type"] == "chromium"

        # Test firefox
        state_firefox: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "firefox",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }
        assert state_firefox["browser_type"] == "firefox"


# =============================================================================
# Test UATStatus Enum
# =============================================================================


class TestUATStatus:
    """Test the UATStatus enum."""

    def test_uat_status_import(self) -> None:
        """Test that UATStatus can be imported."""
        from daw_agents.agents.uat.models import UATStatus

        assert UATStatus is not None

    def test_uat_status_has_required_values(self) -> None:
        """Test that UATStatus has all workflow states."""
        from daw_agents.agents.uat.models import UATStatus

        # Required states for UAT workflow
        assert hasattr(UATStatus, "SETUP")
        assert hasattr(UATStatus, "NAVIGATE")
        assert hasattr(UATStatus, "INTERACT")
        assert hasattr(UATStatus, "VALIDATE")
        assert hasattr(UATStatus, "COMPLETE")
        assert hasattr(UATStatus, "ERROR")

    def test_uat_status_values(self) -> None:
        """Test UATStatus enum values are strings."""
        from daw_agents.agents.uat.models import UATStatus

        assert UATStatus.SETUP.value == "setup"
        assert UATStatus.NAVIGATE.value == "navigate"
        assert UATStatus.INTERACT.value == "interact"
        assert UATStatus.VALIDATE.value == "validate"
        assert UATStatus.COMPLETE.value == "complete"
        assert UATStatus.ERROR.value == "error"


# =============================================================================
# Test UATResult Model
# =============================================================================


class TestUATResult:
    """Test the UATResult Pydantic model."""

    def test_uat_result_import(self) -> None:
        """Test that UATResult can be imported."""
        from daw_agents.agents.uat.models import UATResult

        assert UATResult is not None

    def test_uat_result_creation_success(self) -> None:
        """Test creating a successful UATResult."""
        from daw_agents.agents.uat.models import UATResult

        result = UATResult(
            success=True,
            scenario="Given I am on the login page...",
            status="complete",
            validation_report={
                "total_steps": 3,
                "passed_steps": 3,
                "failed_steps": 0,
            },
            screenshots=["/tmp/screenshot1.png"],
            traces=["/tmp/trace1.json"],
            timing={"total_ms": 1500.0, "navigation_ms": 500.0},
        )

        assert result.success is True
        assert result.status == "complete"
        assert result.validation_report["total_steps"] == 3
        assert len(result.screenshots) == 1
        assert len(result.traces) == 1

    def test_uat_result_creation_failure(self) -> None:
        """Test creating a failed UATResult."""
        from daw_agents.agents.uat.models import UATResult

        result = UATResult(
            success=False,
            scenario="Given I am on the login page...",
            status="error",
            validation_report={
                "total_steps": 3,
                "passed_steps": 1,
                "failed_steps": 2,
            },
            screenshots=[],
            traces=[],
            timing={},
            error="Element not found: button#submit",
        )

        assert result.success is False
        assert result.status == "error"
        assert result.error is not None


# =============================================================================
# Test GherkinStep Model
# =============================================================================


class TestGherkinStep:
    """Test the GherkinStep Pydantic model."""

    def test_gherkin_step_import(self) -> None:
        """Test that GherkinStep can be imported."""
        from daw_agents.agents.uat.models import GherkinStep

        assert GherkinStep is not None

    def test_gherkin_step_creation(self) -> None:
        """Test creating a GherkinStep."""
        from daw_agents.agents.uat.models import GherkinStep

        step = GherkinStep(
            keyword="Given",
            text="I am on the login page",
            action_type="navigate",
            selector=None,
            value="http://localhost:3000/login",
        )

        assert step.keyword == "Given"
        assert step.action_type == "navigate"


class TestValidationResult:
    """Test the ValidationResult Pydantic model."""

    def test_validation_result_import(self) -> None:
        """Test that ValidationResult can be imported."""
        from daw_agents.agents.uat.models import ValidationResult

        assert ValidationResult is not None

    def test_validation_result_creation(self) -> None:
        """Test creating a ValidationResult."""
        from daw_agents.agents.uat.models import ValidationResult

        result = ValidationResult(
            step_index=0,
            passed=True,
            expected="Welcome message visible",
            actual="Welcome message visible",
            accessibility_snapshot={"role": "heading", "name": "Welcome"},
        )

        assert result.passed is True
        assert result.step_index == 0


# =============================================================================
# Test GherkinParser
# =============================================================================


class TestGherkinParser:
    """Test the GherkinParser for parsing Gherkin scenarios."""

    def test_gherkin_parser_import(self) -> None:
        """Test that GherkinParser can be imported."""
        from daw_agents.agents.uat.parser import GherkinParser

        assert GherkinParser is not None

    def test_parse_simple_scenario(self) -> None:
        """Test parsing a simple Gherkin scenario."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = """
        Given I am on the login page
        When I enter "user@example.com" in the email field
        And I enter "password123" in the password field
        And I click the submit button
        Then I should see the dashboard
        """

        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 5
        assert steps[0].keyword == "Given"
        assert steps[1].keyword == "When"
        assert steps[2].keyword == "And"
        assert steps[3].keyword == "And"
        assert steps[4].keyword == "Then"

    def test_parse_given_step(self) -> None:
        """Test parsing a Given step."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = "Given I am on the login page"
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 1
        assert steps[0].keyword == "Given"
        assert steps[0].text == "I am on the login page"

    def test_parse_when_step_with_value(self) -> None:
        """Test parsing a When step with a value."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = 'When I enter "test@example.com" in the email field'
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 1
        assert steps[0].keyword == "When"
        assert "test@example.com" in steps[0].text

    def test_parse_then_step(self) -> None:
        """Test parsing a Then step."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = "Then I should see the welcome message"
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 1
        assert steps[0].keyword == "Then"
        assert "welcome message" in steps[0].text

    def test_parse_and_step(self) -> None:
        """Test parsing And step (continues previous keyword)."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = """
        When I click the login button
        And I wait for 2 seconds
        """
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 2
        assert steps[0].keyword == "When"
        assert steps[1].keyword == "And"


# =============================================================================
# Test UATAgent Class
# =============================================================================


class TestUATAgent:
    """Test the UATAgent class."""

    def test_uat_agent_import(self) -> None:
        """Test that UATAgent class can be imported."""
        from daw_agents.agents.uat.graph import UATAgent

        assert UATAgent is not None

    def test_uat_agent_initialization(self) -> None:
        """Test UATAgent initialization."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        assert agent is not None

    def test_uat_agent_initialization_with_custom_browser(self) -> None:
        """Test UATAgent initialization with custom browser type."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent(browser_type="firefox")
        assert agent.browser_type == "firefox"

    def test_uat_agent_initialization_with_webkit(self) -> None:
        """Test UATAgent initialization with WebKit browser."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent(browser_type="webkit")
        assert agent.browser_type == "webkit"

    def test_uat_agent_has_mcp_client_access(self) -> None:
        """Test that UATAgent can use MCP client for Playwright."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        assert hasattr(agent, "mcp_client") or hasattr(agent, "configure_mcp")

    def test_uat_agent_has_graph(self) -> None:
        """Test that UATAgent has a compiled LangGraph."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        assert agent.graph is not None

    def test_uat_agent_has_parser(self) -> None:
        """Test that UATAgent has a GherkinParser."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        assert agent.parser is not None


# =============================================================================
# Test UATAgent Node Functions
# =============================================================================


class TestUATNodes:
    """Test individual UAT node functions."""

    @pytest.mark.asyncio
    async def test_setup_browser_node(self) -> None:
        """Test the setup_browser node function."""
        from daw_agents.agents.uat.nodes import setup_browser_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Given I am on the login page",
            "url": "http://localhost:3000/login",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.initialize_browser"
        ) as mock_init:
            mock_init.return_value = {"browser_id": "test-browser-123"}

            result = await setup_browser_node(state)

            assert "status" in result
            # Should move to navigate or error

    @pytest.mark.asyncio
    async def test_navigate_node(self) -> None:
        """Test the navigate node function."""
        from daw_agents.agents.uat.nodes import navigate_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Given I am on the login page",
            "url": "http://localhost:3000/login",
            "browser_type": "chromium",
            "status": "navigate",
            "current_step": 0,
            "steps": [{"keyword": "Given", "text": "I am on the login page", "action_type": "navigate"}],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.navigate_to_url"
        ) as mock_navigate:
            mock_navigate.return_value = {
                "success": True,
                "accessibility_snapshot": {"role": "document", "name": "Login"},
            }

            result = await navigate_node(state)

            assert "accessibility_snapshots" in result or "status" in result

    @pytest.mark.asyncio
    async def test_interact_node(self) -> None:
        """Test the interact node function."""
        from daw_agents.agents.uat.nodes import interact_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "When I click the submit button",
            "url": "http://localhost:3000/login",
            "browser_type": "chromium",
            "status": "interact",
            "current_step": 1,
            "steps": [
                {"keyword": "Given", "text": "I am on the login page", "action_type": "navigate"},
                {"keyword": "When", "text": "I click the submit button", "action_type": "click"},
            ],
            "accessibility_snapshots": [{"role": "document", "name": "Login"}],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.execute_interaction"
        ) as mock_interact:
            mock_interact.return_value = {
                "success": True,
                "accessibility_snapshot": {"role": "button", "name": "Submit"},
            }

            result = await interact_node(state)

            assert "current_step" in result or "status" in result

    @pytest.mark.asyncio
    async def test_validate_node(self) -> None:
        """Test the validate node function."""
        from daw_agents.agents.uat.nodes import validate_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Then I should see the dashboard",
            "url": "http://localhost:3000/dashboard",
            "browser_type": "chromium",
            "status": "validate",
            "current_step": 2,
            "steps": [
                {"keyword": "Given", "text": "I am on the login page", "action_type": "navigate"},
                {"keyword": "When", "text": "I click submit", "action_type": "click"},
                {"keyword": "Then", "text": "I should see the dashboard", "action_type": "assert"},
            ],
            "accessibility_snapshots": [{"role": "document", "name": "Dashboard"}],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.validate_assertion"
        ) as mock_validate:
            mock_validate.return_value = {
                "passed": True,
                "expected": "dashboard visible",
                "actual": "dashboard visible",
            }

            result = await validate_node(state)

            assert "validation_results" in result or "status" in result

    @pytest.mark.asyncio
    async def test_cleanup_node(self) -> None:
        """Test the cleanup node function."""
        from daw_agents.agents.uat.nodes import cleanup_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "complete",
            "current_step": 3,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [{"passed": True}],
            "error": None,
            "timing": {"start_time": 1000.0},
        }

        with patch(
            "daw_agents.agents.uat.nodes.close_browser"
        ) as mock_close:
            mock_close.return_value = {"success": True}

            result = await cleanup_node(state)

            assert "timing" in result or "status" in result


# =============================================================================
# Test Route Decision Logic
# =============================================================================


class TestRouteDecision:
    """Test the routing decision logic."""

    def test_route_after_setup(self) -> None:
        """Test routing after setup goes to navigate."""
        from daw_agents.agents.uat.nodes import route_after_setup
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [{"keyword": "Given", "action_type": "navigate"}],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        next_node = route_after_setup(state)
        assert next_node == "navigate"

    def test_route_after_setup_with_error(self) -> None:
        """Test routing after setup with error goes to error."""
        from daw_agents.agents.uat.nodes import route_after_setup
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": "Failed to start browser",
            "timing": {},
        }

        next_node = route_after_setup(state)
        assert next_node == "error"

    def test_route_after_navigate(self) -> None:
        """Test routing after navigate based on next step type."""
        from daw_agents.agents.uat.nodes import route_after_navigate
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "navigate",
            "current_step": 0,
            "steps": [
                {"keyword": "Given", "action_type": "navigate"},
                {"keyword": "When", "action_type": "click"},
            ],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        next_node = route_after_navigate(state)
        assert next_node == "interact"

    def test_route_after_interact_to_validate(self) -> None:
        """Test routing after interact goes to validate when Then step."""
        from daw_agents.agents.uat.nodes import route_after_interact
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "interact",
            "current_step": 1,
            "steps": [
                {"keyword": "Given", "action_type": "navigate"},
                {"keyword": "When", "action_type": "click"},
                {"keyword": "Then", "action_type": "assert"},
            ],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        next_node = route_after_interact(state)
        assert next_node == "validate"

    def test_route_after_validate_complete(self) -> None:
        """Test routing after validate when all steps complete."""
        from daw_agents.agents.uat.nodes import route_after_validate
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "validate",
            "current_step": 2,
            "steps": [
                {"keyword": "Given", "action_type": "navigate"},
                {"keyword": "When", "action_type": "click"},
                {"keyword": "Then", "action_type": "assert"},
            ],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [{"passed": True}],
            "error": None,
            "timing": {},
        }

        next_node = route_after_validate(state)
        assert next_node == "cleanup"


# =============================================================================
# Test Complete Workflow
# =============================================================================


class TestUATWorkflow:
    """Test the complete UAT workflow."""

    @pytest.mark.asyncio
    async def test_execute_method(self) -> None:
        """Test the UATAgent.execute() method."""
        from daw_agents.agents.uat.graph import UATAgent
        from daw_agents.agents.uat.models import UATResult

        agent = UATAgent()

        with patch.object(agent, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "scenario": "Test scenario",
                    "url": "http://localhost:3000",
                    "browser_type": "chromium",
                    "status": "complete",
                    "current_step": 3,
                    "steps": [],
                    "accessibility_snapshots": [],
                    "screenshots": ["/tmp/screenshot.png"],
                    "traces": ["/tmp/trace.json"],
                    "validation_results": [{"passed": True}],
                    "error": None,
                    "timing": {"total_ms": 1500.0},
                }
            )

            result = await agent.execute(
                scenario="Given I am on the login page\nThen I should see the title",
                url="http://localhost:3000",
            )

            assert isinstance(result, UATResult)
            assert result.success is True
            assert result.status == "complete"

    @pytest.mark.asyncio
    async def test_execute_with_error(self) -> None:
        """Test the UATAgent.execute() method when it fails."""
        from daw_agents.agents.uat.graph import UATAgent
        from daw_agents.agents.uat.models import UATResult

        agent = UATAgent()

        with patch.object(agent, "graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={
                    "scenario": "Test scenario",
                    "url": "http://localhost:3000",
                    "browser_type": "chromium",
                    "status": "error",
                    "current_step": 1,
                    "steps": [],
                    "accessibility_snapshots": [],
                    "screenshots": [],
                    "traces": [],
                    "validation_results": [],
                    "error": "Element not found",
                    "timing": {},
                }
            )

            result = await agent.execute(
                scenario="Given I am on the nonexistent page",
                url="http://localhost:3000/nonexistent",
            )

            assert isinstance(result, UATResult)
            assert result.success is False
            assert result.status == "error"


# =============================================================================
# Test Accessibility Snapshot Mode
# =============================================================================


class TestAccessibilitySnapshotMode:
    """Test that UAT uses accessibility snapshots instead of visual screenshots."""

    def test_uat_agent_uses_accessibility_mode(self) -> None:
        """Test that UATAgent is configured for accessibility mode."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        assert agent.accessibility_mode is True

    @pytest.mark.asyncio
    async def test_validate_uses_accessibility_snapshot(self) -> None:
        """Test that validation uses accessibility snapshots."""
        from daw_agents.agents.uat.nodes import validate_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Then I should see the heading",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "validate",
            "current_step": 0,
            "steps": [{"keyword": "Then", "text": "I should see the heading", "action_type": "assert"}],
            "accessibility_snapshots": [
                {"role": "heading", "name": "Welcome", "level": 1}
            ],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.validate_assertion"
        ) as mock_validate:
            mock_validate.return_value = {
                "passed": True,
                "expected": "heading visible",
                "actual": "heading visible",
                "accessibility_snapshot": {"role": "heading", "name": "Welcome"},
            }

            result = await validate_node(state)

            # Should use accessibility snapshot for validation
            mock_validate.assert_called_once()


# =============================================================================
# Test Cross-Browser Support
# =============================================================================


class TestCrossBrowserSupport:
    """Test cross-browser support (Chromium, Firefox, WebKit)."""

    def test_chromium_browser_type(self) -> None:
        """Test UATAgent with Chromium browser."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent(browser_type="chromium")
        assert agent.browser_type == "chromium"

    def test_firefox_browser_type(self) -> None:
        """Test UATAgent with Firefox browser."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent(browser_type="firefox")
        assert agent.browser_type == "firefox"

    def test_webkit_browser_type(self) -> None:
        """Test UATAgent with WebKit browser."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent(browser_type="webkit")
        assert agent.browser_type == "webkit"

    def test_invalid_browser_type_raises_error(self) -> None:
        """Test that invalid browser type raises ValueError."""
        from daw_agents.agents.uat.graph import UATAgent

        with pytest.raises(ValueError) as exc_info:
            UATAgent(browser_type="invalid")

        assert "browser_type" in str(exc_info.value).lower()


# =============================================================================
# Test Graph Structure
# =============================================================================


class TestGraphStructure:
    """Test the LangGraph structure of the UAT agent."""

    def test_graph_has_required_nodes(self) -> None:
        """Test that the UAT graph has all required nodes."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        graph = agent.graph

        # Get node names from the compiled graph
        node_names = list(graph.nodes.keys())

        # Required nodes per UAT-001 spec
        assert "setup_browser" in node_names
        assert "navigate" in node_names
        assert "interact" in node_names
        assert "validate" in node_names
        assert "cleanup" in node_names

    def test_graph_has_conditional_edges(self) -> None:
        """Test that the graph has conditional routing edges."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        # The graph should be compilable with conditional edges
        assert agent.graph is not None


# =============================================================================
# Test MCP Integration
# =============================================================================


class TestMCPIntegration:
    """Test integration with MCP Client for Playwright."""

    def test_uat_agent_can_use_mcp_client(self) -> None:
        """Test that UATAgent can use MCP client for Playwright commands."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        assert hasattr(agent, "mcp_client") or hasattr(agent, "configure_mcp")

    def test_configure_mcp(self) -> None:
        """Test configuring MCP client."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        mock_client = MagicMock()

        agent.configure_mcp(mock_client)
        assert agent.mcp_client == mock_client


# =============================================================================
# Test Module Exports
# =============================================================================


class TestUATExports:
    """Test module exports and public API."""

    def test_public_api_exports(self) -> None:
        """Test that public API is properly exported."""
        from daw_agents.agents.uat import (
            GherkinParser,
            GherkinStep,
            UATAgent,
            UATResult,
            UATState,
            UATStatus,
            ValidationResult,
        )

        assert UATAgent is not None
        assert UATResult is not None
        assert UATState is not None
        assert UATStatus is not None
        assert GherkinParser is not None
        assert GherkinStep is not None
        assert ValidationResult is not None


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper functions for increased coverage."""

    @pytest.mark.asyncio
    async def test_initialize_browser(self) -> None:
        """Test the initialize_browser helper function."""
        from daw_agents.agents.uat.nodes import initialize_browser

        result = await initialize_browser("chromium")
        assert result["success"] is True
        assert "browser_id" in result

    @pytest.mark.asyncio
    async def test_navigate_to_url(self) -> None:
        """Test the navigate_to_url helper function."""
        from daw_agents.agents.uat.nodes import navigate_to_url

        result = await navigate_to_url("http://localhost:3000")
        assert result["success"] is True
        assert "accessibility_snapshot" in result

    @pytest.mark.asyncio
    async def test_execute_interaction(self) -> None:
        """Test the execute_interaction helper function."""
        from daw_agents.agents.uat.nodes import execute_interaction

        result = await execute_interaction("click", "submit-button", None)
        assert result["success"] is True
        assert "accessibility_snapshot" in result

    @pytest.mark.asyncio
    async def test_validate_assertion(self) -> None:
        """Test the validate_assertion helper function."""
        from daw_agents.agents.uat.nodes import validate_assertion

        result = await validate_assertion(
            "should see welcome",
            {"role": "heading", "name": "Welcome"},
        )
        assert result["passed"] is True
        assert "expected" in result

    @pytest.mark.asyncio
    async def test_close_browser(self) -> None:
        """Test the close_browser helper function."""
        from daw_agents.agents.uat.nodes import close_browser

        result = await close_browser()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_take_screenshot(self) -> None:
        """Test the take_screenshot helper function."""
        from daw_agents.agents.uat.nodes import take_screenshot

        result = await take_screenshot()
        assert result["success"] is True
        assert "path" in result


class TestParserEdgeCases:
    """Test parser edge cases for increased coverage."""

    def test_parse_empty_scenario(self) -> None:
        """Test parsing empty scenario."""
        from daw_agents.agents.uat.parser import GherkinParser

        parser = GherkinParser()
        steps = parser.parse("")
        assert len(steps) == 0

    def test_parse_but_step(self) -> None:
        """Test parsing But step."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = """
        Given I am on the page
        But I should not see the error
        """
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 2
        assert steps[1].keyword == "But"

    def test_parse_scroll_action(self) -> None:
        """Test parsing scroll action."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = "When I scroll to the footer"
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 1
        assert steps[0].action_type == "scroll"

    def test_parse_hover_action(self) -> None:
        """Test parsing hover action."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = "When I hover over the menu"
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 1
        assert steps[0].action_type == "hover"

    def test_parse_wait_action(self) -> None:
        """Test parsing wait action."""
        from daw_agents.agents.uat.parser import GherkinParser

        scenario = "When I wait for 2 seconds"
        parser = GherkinParser()
        steps = parser.parse(scenario)

        assert len(steps) == 1
        assert steps[0].action_type == "wait"


class TestValidateScenarioMethod:
    """Test the validate_scenario method."""

    @pytest.mark.asyncio
    async def test_validate_scenario(self) -> None:
        """Test validating a scenario without execution."""
        from daw_agents.agents.uat.graph import UATAgent

        agent = UATAgent()
        steps = await agent.validate_scenario(
            "Given I am on the login page\nThen I should see the title"
        )

        assert len(steps) == 2
        assert steps[0]["keyword"] == "Given"
        assert steps[1]["keyword"] == "Then"


class TestNodeErrorHandling:
    """Test error handling in node functions."""

    @pytest.mark.asyncio
    async def test_setup_browser_node_error(self) -> None:
        """Test setup_browser_node with error."""
        from daw_agents.agents.uat.nodes import setup_browser_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.initialize_browser"
        ) as mock_init:
            mock_init.return_value = {"success": False}

            result = await setup_browser_node(state)
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_navigate_node_error(self) -> None:
        """Test navigate_node with navigation error."""
        from daw_agents.agents.uat.nodes import navigate_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "navigate",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.navigate_to_url"
        ) as mock_nav:
            mock_nav.return_value = {"success": False}

            result = await navigate_node(state)
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_interact_node_error(self) -> None:
        """Test interact_node with interaction error."""
        from daw_agents.agents.uat.nodes import interact_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "interact",
            "current_step": 0,
            "steps": [{"keyword": "When", "text": "click button", "action_type": "click"}],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.execute_interaction"
        ) as mock_interact:
            mock_interact.return_value = {"success": False}

            result = await interact_node(state)
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_validate_node_failure(self) -> None:
        """Test validate_node with validation failure."""
        from daw_agents.agents.uat.nodes import validate_node
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "validate",
            "current_step": 0,
            "steps": [{"keyword": "Then", "text": "should see element", "action_type": "assert"}],
            "accessibility_snapshots": [{"role": "document"}],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        with patch(
            "daw_agents.agents.uat.nodes.validate_assertion"
        ) as mock_validate:
            mock_validate.return_value = {"passed": False}

            result = await validate_node(state)
            assert result["status"] == "error"


class TestRouteDecisionEdgeCases:
    """Test routing edge cases."""

    def test_route_after_navigate_with_error(self) -> None:
        """Test routing after navigate with error."""
        from daw_agents.agents.uat.nodes import route_after_navigate
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "navigate",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": "Navigation failed",
            "timing": {},
        }

        next_node = route_after_navigate(state)
        assert next_node == "error"

    def test_route_after_interact_with_error(self) -> None:
        """Test routing after interact with error."""
        from daw_agents.agents.uat.nodes import route_after_interact
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "interact",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": "Interaction failed",
            "timing": {},
        }

        next_node = route_after_interact(state)
        assert next_node == "error"

    def test_route_after_validate_with_error(self) -> None:
        """Test routing after validate with error."""
        from daw_agents.agents.uat.nodes import route_after_validate
        from daw_agents.agents.uat.state import UATState

        state: UATState = {
            "scenario": "Test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "validate",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": "Validation failed",
            "timing": {},
        }

        next_node = route_after_validate(state)
        assert next_node == "error"
