"""Node functions for the UAT Agent LangGraph workflow.

This module implements the node functions and routing logic for the
UAT Agent workflow:

1. setup_browser_node: Initialize browser via Playwright MCP
2. navigate_node: Navigate to target URL
3. interact_node: Execute user interactions
4. validate_node: Check expected outcomes using accessibility snapshots
5. cleanup_node: Close browser and finalize

Each node function takes the current state and returns a partial state
update. Routing functions determine the next node based on state.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from daw_agents.agents.uat.state import UATState

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions (MCP integration stubs)
# =============================================================================


async def initialize_browser(browser_type: str) -> dict[str, Any]:
    """Initialize browser via Playwright MCP.

    Args:
        browser_type: Browser type (chromium, firefox, webkit)

    Returns:
        Dictionary with browser initialization result
    """
    # This would call Playwright MCP to start browser
    # For now, return a stub response
    logger.info("Initializing %s browser via Playwright MCP", browser_type)
    return {
        "browser_id": f"{browser_type}-{int(time.time())}",
        "success": True,
    }


async def navigate_to_url(url: str) -> dict[str, Any]:
    """Navigate to URL via Playwright MCP.

    Args:
        url: Target URL

    Returns:
        Dictionary with navigation result and accessibility snapshot
    """
    logger.info("Navigating to URL: %s", url)
    return {
        "success": True,
        "accessibility_snapshot": {
            "role": "document",
            "name": "Page",
            "url": url,
        },
    }


async def execute_interaction(
    action_type: str,
    selector: str | None,
    value: str | None,
) -> dict[str, Any]:
    """Execute user interaction via Playwright MCP.

    Args:
        action_type: Type of action (click, type, etc.)
        selector: Element selector
        value: Value for input actions

    Returns:
        Dictionary with interaction result
    """
    logger.info("Executing %s on %s with value %s", action_type, selector, value)
    return {
        "success": True,
        "accessibility_snapshot": {
            "role": "button" if action_type == "click" else "textbox",
            "name": selector or "element",
        },
    }


async def validate_assertion(
    expected: str,
    accessibility_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Validate assertion using accessibility snapshot.

    Args:
        expected: Expected outcome description
        accessibility_snapshot: Current accessibility snapshot

    Returns:
        Dictionary with validation result
    """
    logger.info("Validating: %s", expected)
    return {
        "passed": True,
        "expected": expected,
        "actual": expected,
        "accessibility_snapshot": accessibility_snapshot,
    }


async def close_browser() -> dict[str, Any]:
    """Close browser via Playwright MCP.

    Returns:
        Dictionary with close result
    """
    logger.info("Closing browser")
    return {"success": True}


async def take_screenshot(path: str | None = None) -> dict[str, Any]:
    """Take screenshot via Playwright MCP.

    Args:
        path: Optional path to save screenshot

    Returns:
        Dictionary with screenshot result
    """
    screenshot_path = path or f"/tmp/screenshot-{int(time.time())}.png"
    logger.info("Taking screenshot: %s", screenshot_path)
    return {
        "success": True,
        "path": screenshot_path,
    }


# =============================================================================
# Node Functions
# =============================================================================


async def setup_browser_node(state: UATState) -> dict[str, Any]:
    """Initialize browser for UAT.

    Sets up the browser via Playwright MCP and parses the Gherkin scenario.

    Args:
        state: Current UAT state

    Returns:
        Partial state update with browser info and parsed steps
    """
    from daw_agents.agents.uat.parser import GherkinParser

    start_time = time.time()

    try:
        # Initialize browser
        browser_result = await initialize_browser(state["browser_type"])

        if not browser_result.get("success"):
            return {
                "status": "error",
                "error": "Failed to initialize browser",
            }

        # Parse the Gherkin scenario
        parser = GherkinParser()
        steps = parser.parse(state["scenario"])

        # Convert steps to dictionaries for state
        step_dicts = [step.model_dump() for step in steps]

        setup_time = (time.time() - start_time) * 1000
        timing = dict(state.get("timing", {}))
        timing["setup_ms"] = setup_time

        return {
            "status": "navigate",
            "steps": step_dicts,
            "current_step": 0,
            "timing": timing,
        }

    except Exception as e:
        logger.error("Browser setup failed: %s", e)
        return {
            "status": "error",
            "error": f"Browser setup failed: {str(e)}",
        }


async def navigate_node(state: UATState) -> dict[str, Any]:
    """Navigate to target URL.

    Navigates to the URL and captures the initial accessibility snapshot.

    Args:
        state: Current UAT state

    Returns:
        Partial state update with navigation result
    """
    start_time = time.time()

    try:
        # Navigate to URL
        nav_result = await navigate_to_url(state["url"])

        if not nav_result.get("success"):
            return {
                "status": "error",
                "error": f"Navigation failed: {state['url']}",
            }

        # Capture accessibility snapshot
        snapshots = list(state.get("accessibility_snapshots", []))
        if nav_result.get("accessibility_snapshot"):
            snapshots.append(nav_result["accessibility_snapshot"])

        nav_time = (time.time() - start_time) * 1000
        timing = dict(state.get("timing", {}))
        timing["navigation_ms"] = nav_time

        # Determine next status based on steps
        steps = state.get("steps", [])
        current_step = state.get("current_step", 0)

        if current_step < len(steps):
            step = steps[current_step]
            action_type = step.get("action_type", "unknown")

            if action_type in ("click", "type", "interact", "scroll", "hover", "select"):
                next_status = "interact"
            elif action_type == "assert":
                next_status = "validate"
            else:
                next_status = "interact"
        else:
            next_status = "complete"

        return {
            "accessibility_snapshots": snapshots,
            "status": next_status,
            "current_step": current_step + 1 if steps else 0,
            "timing": timing,
        }

    except Exception as e:
        logger.error("Navigation failed: %s", e)
        return {
            "status": "error",
            "error": f"Navigation failed: {str(e)}",
        }


async def interact_node(state: UATState) -> dict[str, Any]:
    """Execute user interaction.

    Executes the current interaction step (click, type, etc.).

    Args:
        state: Current UAT state

    Returns:
        Partial state update with interaction result
    """
    try:
        steps = state.get("steps", [])
        current_step = state.get("current_step", 0)

        if current_step >= len(steps):
            return {"status": "complete"}

        step = steps[current_step]
        action_type = step.get("action_type", "unknown")
        selector = step.get("selector")
        value = step.get("value")

        # Execute the interaction
        result = await execute_interaction(action_type, selector, value)

        if not result.get("success"):
            return {
                "status": "error",
                "error": f"Interaction failed: {step.get('text', '')}",
            }

        # Update snapshots
        snapshots = list(state.get("accessibility_snapshots", []))
        if result.get("accessibility_snapshot"):
            snapshots.append(result["accessibility_snapshot"])

        # Determine next status
        next_step = current_step + 1
        if next_step < len(steps):
            next_step_data = steps[next_step]
            next_action = next_step_data.get("action_type", "unknown")

            if next_action == "assert":
                next_status = "validate"
            elif next_action in ("click", "type", "interact", "scroll", "hover", "select"):
                next_status = "interact"
            elif next_action == "navigate":
                next_status = "navigate"
            else:
                next_status = "interact"
        else:
            next_status = "cleanup"

        return {
            "accessibility_snapshots": snapshots,
            "status": next_status,
            "current_step": next_step,
        }

    except Exception as e:
        logger.error("Interaction failed: %s", e)
        return {
            "status": "error",
            "error": f"Interaction failed: {str(e)}",
        }


async def validate_node(state: UATState) -> dict[str, Any]:
    """Validate expected outcome.

    Uses accessibility snapshots to validate assertions.

    Args:
        state: Current UAT state

    Returns:
        Partial state update with validation result
    """
    try:
        steps = state.get("steps", [])
        current_step = state.get("current_step", 0)
        snapshots = state.get("accessibility_snapshots", [])

        if current_step >= len(steps):
            return {"status": "cleanup"}

        step = steps[current_step]
        expected = step.get("text", "")

        # Get latest accessibility snapshot
        latest_snapshot = snapshots[-1] if snapshots else {}

        # Validate using accessibility snapshot
        result = await validate_assertion(expected, latest_snapshot)

        # Store validation result
        validation_results = list(state.get("validation_results", []))
        validation_results.append({
            "step_index": current_step,
            "passed": result.get("passed", False),
            "expected": result.get("expected", ""),
            "actual": result.get("actual", ""),
            "accessibility_snapshot": result.get("accessibility_snapshot"),
        })

        # Check if validation failed
        if not result.get("passed"):
            return {
                "validation_results": validation_results,
                "status": "error",
                "error": f"Validation failed: expected '{expected}'",
            }

        # Determine next status
        next_step = current_step + 1
        if next_step < len(steps):
            next_step_data = steps[next_step]
            next_action = next_step_data.get("action_type", "unknown")

            if next_action == "assert":
                next_status = "validate"
            elif next_action in ("click", "type", "interact", "scroll", "hover", "select"):
                next_status = "interact"
            elif next_action == "navigate":
                next_status = "navigate"
            else:
                next_status = "validate"
        else:
            next_status = "cleanup"

        return {
            "validation_results": validation_results,
            "status": next_status,
            "current_step": next_step,
        }

    except Exception as e:
        logger.error("Validation failed: %s", e)
        return {
            "status": "error",
            "error": f"Validation failed: {str(e)}",
        }


async def cleanup_node(state: UATState) -> dict[str, Any]:
    """Cleanup browser and finalize.

    Closes the browser and generates final timing.

    Args:
        state: Current UAT state

    Returns:
        Partial state update with final timing
    """
    try:
        # Close browser
        await close_browser()

        # Take final screenshot if possible
        screenshot_result = await take_screenshot()
        screenshots = list(state.get("screenshots", []))
        if screenshot_result.get("success"):
            screenshots.append(screenshot_result["path"])

        # Calculate total time
        timing = dict(state.get("timing", {}))
        if "start_time" in timing:
            timing["total_ms"] = (time.time() * 1000) - timing["start_time"]

        return {
            "status": "complete",
            "screenshots": screenshots,
            "timing": timing,
        }

    except Exception as e:
        logger.error("Cleanup failed: %s", e)
        # Still mark as complete even if cleanup fails
        return {
            "status": "complete",
            "error": f"Cleanup warning: {str(e)}",
        }


# =============================================================================
# Routing Functions
# =============================================================================


def route_after_setup(state: UATState) -> str:
    """Route after setup node.

    Args:
        state: Current UAT state

    Returns:
        Next node name
    """
    if state.get("error"):
        return "error"

    return "navigate"


def route_after_navigate(state: UATState) -> str:
    """Route after navigate node.

    Determines next step based on the NEXT step's action type.

    Args:
        state: Current UAT state

    Returns:
        Next node name
    """
    if state.get("error"):
        return "error"

    steps = state.get("steps", [])
    current_step = state.get("current_step", 0)
    next_step_idx = current_step + 1

    if next_step_idx >= len(steps):
        return "cleanup"

    step = steps[next_step_idx]
    action_type = step.get("action_type", "unknown")

    if action_type == "assert":
        return "validate"
    elif action_type == "navigate":
        return "navigate"
    else:
        return "interact"


def route_after_interact(state: UATState) -> str:
    """Route after interact node.

    Determines next step based on the NEXT step's action type.

    Args:
        state: Current UAT state

    Returns:
        Next node name
    """
    if state.get("error"):
        return "error"

    steps = state.get("steps", [])
    current_step = state.get("current_step", 0)
    next_step_idx = current_step + 1

    if next_step_idx >= len(steps):
        return "cleanup"

    step = steps[next_step_idx]
    action_type = step.get("action_type", "unknown")

    if action_type == "assert":
        return "validate"
    elif action_type == "navigate":
        return "navigate"
    else:
        return "interact"


def route_after_validate(state: UATState) -> str:
    """Route after validate node.

    Determines next step based on the NEXT step's action type.

    Args:
        state: Current UAT state

    Returns:
        Next node name
    """
    if state.get("error"):
        return "error"

    steps = state.get("steps", [])
    current_step = state.get("current_step", 0)
    next_step_idx = current_step + 1

    if next_step_idx >= len(steps):
        return "cleanup"

    step = steps[next_step_idx]
    action_type = step.get("action_type", "unknown")

    if action_type == "assert":
        return "validate"
    elif action_type in ("click", "type", "interact", "scroll", "hover", "select"):
        return "interact"
    elif action_type == "navigate":
        return "navigate"
    else:
        return "cleanup"
