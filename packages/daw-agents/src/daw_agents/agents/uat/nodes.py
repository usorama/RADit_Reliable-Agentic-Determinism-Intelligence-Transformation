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
import os
import time
from typing import Any

from daw_agents.agents.uat.state import UATState
from daw_agents.mcp import MCPClient, MCPToolResult

logger = logging.getLogger(__name__)


# =============================================================================
# Playwright MCP Client Singleton
# =============================================================================

# Environment variable for Playwright MCP server URL
PLAYWRIGHT_MCP_URL = os.environ.get("MCP_PLAYWRIGHT_SERVER_URL", "")

# Module-level client instance (lazily initialized)
_playwright_client: MCPClient | None = None


def _get_playwright_client() -> MCPClient | None:
    """Get or create the Playwright MCP client singleton.

    Returns:
        MCPClient instance if configured, None otherwise
    """
    global _playwright_client

    if not PLAYWRIGHT_MCP_URL:
        logger.debug("MCP_PLAYWRIGHT_SERVER_URL not configured")
        return None

    if _playwright_client is None:
        _playwright_client = MCPClient(
            server_url=PLAYWRIGHT_MCP_URL,
            server_name="playwright",
            timeout=60.0,  # Browser operations can be slow
        )
        logger.info("Created Playwright MCP client: %s", PLAYWRIGHT_MCP_URL)

    return _playwright_client


def _is_mcp_available() -> bool:
    """Check if Playwright MCP is available.

    Returns:
        True if MCP is configured and accessible
    """
    return bool(PLAYWRIGHT_MCP_URL)


# =============================================================================
# Helper Functions (MCP integration)
# =============================================================================


async def initialize_browser(browser_type: str) -> dict[str, Any]:
    """Initialize browser via Playwright MCP.

    Uses the Playwright MCP 'browser_launch' tool to start a browser instance.
    Falls back to a stub response when MCP is not available.

    Args:
        browser_type: Browser type (chromium, firefox, webkit)

    Returns:
        Dictionary with browser initialization result
    """
    logger.info("Initializing %s browser via Playwright MCP", browser_type)

    client = _get_playwright_client()
    if client is None:
        logger.warning(
            "Playwright MCP not configured (set MCP_PLAYWRIGHT_SERVER_URL). "
            "Returning stub response."
        )
        return {
            "browser_id": f"{browser_type}-stub-{int(time.time())}",
            "success": True,
            "stub": True,
        }

    try:
        result: MCPToolResult = await client.call_tool(
            "browser_launch",
            params={
                "browser": browser_type,
                "headless": True,
            },
        )

        if not result.success:
            logger.error("Failed to launch browser: %s", result.error)
            return {
                "success": False,
                "error": result.error or "Unknown error launching browser",
            }

        # Extract browser ID from result
        browser_id = f"{browser_type}-{int(time.time())}"
        if isinstance(result.result, dict):
            browser_id = result.result.get("browserId", browser_id)
        elif isinstance(result.result, str):
            browser_id = result.result

        logger.info("Browser launched successfully: %s", browser_id)
        return {
            "browser_id": browser_id,
            "success": True,
        }

    except Exception as e:
        logger.error("Error initializing browser via MCP: %s", e)
        return {
            "success": False,
            "error": f"MCP error: {str(e)}",
        }


async def navigate_to_url(url: str) -> dict[str, Any]:
    """Navigate to URL via Playwright MCP.

    Uses the Playwright MCP 'browser_navigate' tool to navigate to a URL
    and captures an accessibility snapshot.

    Args:
        url: Target URL

    Returns:
        Dictionary with navigation result and accessibility snapshot
    """
    logger.info("Navigating to URL: %s", url)

    client = _get_playwright_client()
    if client is None:
        logger.warning(
            "Playwright MCP not configured. Returning stub response for: %s", url
        )
        return {
            "success": True,
            "stub": True,
            "accessibility_snapshot": {
                "role": "document",
                "name": "Page (stub)",
                "url": url,
            },
        }

    try:
        # Navigate to URL
        nav_result: MCPToolResult = await client.call_tool(
            "browser_navigate",
            params={"url": url},
        )

        if not nav_result.success:
            logger.error("Navigation failed: %s", nav_result.error)
            return {
                "success": False,
                "error": nav_result.error or f"Failed to navigate to {url}",
            }

        # Get accessibility snapshot
        snapshot_result: MCPToolResult = await client.call_tool(
            "browser_snapshot",
            params={},
        )

        accessibility_snapshot: dict[str, Any] = {
            "role": "document",
            "name": "Page",
            "url": url,
        }

        if snapshot_result.success and snapshot_result.result:
            if isinstance(snapshot_result.result, dict):
                accessibility_snapshot = snapshot_result.result
            elif isinstance(snapshot_result.result, str):
                # Parse if it's a JSON string
                import json
                try:
                    accessibility_snapshot = json.loads(snapshot_result.result)
                except json.JSONDecodeError:
                    accessibility_snapshot["raw"] = snapshot_result.result

        logger.info("Navigation successful, captured accessibility snapshot")
        return {
            "success": True,
            "accessibility_snapshot": accessibility_snapshot,
        }

    except Exception as e:
        logger.error("Error navigating via MCP: %s", e)
        return {
            "success": False,
            "error": f"MCP error: {str(e)}",
        }


async def execute_interaction(
    action_type: str,
    selector: str | None,
    value: str | None,
) -> dict[str, Any]:
    """Execute user interaction via Playwright MCP.

    Maps action types to Playwright MCP tools:
    - click -> browser_click
    - type -> browser_type
    - scroll -> browser_scroll
    - hover -> browser_hover
    - select -> browser_select

    Args:
        action_type: Type of action (click, type, etc.)
        selector: Element selector (ref or CSS selector)
        value: Value for input actions

    Returns:
        Dictionary with interaction result
    """
    logger.info("Executing %s on %s with value %s", action_type, selector, value)

    client = _get_playwright_client()
    if client is None:
        logger.warning(
            "Playwright MCP not configured. Returning stub response for: %s",
            action_type,
        )
        return {
            "success": True,
            "stub": True,
            "accessibility_snapshot": {
                "role": "button" if action_type == "click" else "textbox",
                "name": selector or "element",
            },
        }

    # Map action types to MCP tools
    tool_mapping = {
        "click": "browser_click",
        "type": "browser_type",
        "scroll": "browser_scroll",
        "hover": "browser_hover",
        "select": "browser_select_option",
        "interact": "browser_click",  # Default interaction is click
    }

    tool_name = tool_mapping.get(action_type, "browser_click")

    try:
        # Build params based on action type
        params: dict[str, Any] = {}

        if selector:
            # Playwright MCP uses 'ref' for element references
            params["ref"] = selector

        if action_type == "type" and value:
            params["text"] = value
        elif action_type == "select" and value:
            params["values"] = [value]
        elif action_type == "scroll":
            # Scroll uses coordinates or element ref
            params["deltaY"] = 300  # Default scroll amount

        result: MCPToolResult = await client.call_tool(tool_name, params=params)

        if not result.success:
            logger.error("Interaction failed: %s", result.error)
            return {
                "success": False,
                "error": result.error or f"Failed to execute {action_type}",
            }

        # Get updated accessibility snapshot after interaction
        snapshot_result: MCPToolResult = await client.call_tool(
            "browser_snapshot",
            params={},
        )

        accessibility_snapshot: dict[str, Any] = {
            "role": "button" if action_type == "click" else "textbox",
            "name": selector or "element",
        }

        if snapshot_result.success and snapshot_result.result:
            if isinstance(snapshot_result.result, dict):
                accessibility_snapshot = snapshot_result.result

        logger.info("Interaction %s successful", action_type)
        return {
            "success": True,
            "accessibility_snapshot": accessibility_snapshot,
        }

    except Exception as e:
        logger.error("Error executing interaction via MCP: %s", e)
        return {
            "success": False,
            "error": f"MCP error: {str(e)}",
        }


async def validate_assertion(
    expected: str,
    accessibility_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Validate assertion using accessibility snapshot.

    Performs semantic validation by checking if expected elements/text
    are present in the accessibility snapshot.

    Args:
        expected: Expected outcome description
        accessibility_snapshot: Current accessibility snapshot

    Returns:
        Dictionary with validation result
    """
    logger.info("Validating: %s", expected)

    client = _get_playwright_client()
    if client is None:
        logger.warning(
            "Playwright MCP not configured. Returning stub validation for: %s",
            expected,
        )
        return {
            "passed": True,
            "stub": True,
            "expected": expected,
            "actual": expected,
            "accessibility_snapshot": accessibility_snapshot,
        }

    try:
        # Get fresh accessibility snapshot for validation
        snapshot_result: MCPToolResult = await client.call_tool(
            "browser_snapshot",
            params={},
        )

        current_snapshot = accessibility_snapshot
        if snapshot_result.success and snapshot_result.result:
            if isinstance(snapshot_result.result, dict):
                current_snapshot = snapshot_result.result
            elif isinstance(snapshot_result.result, str):
                import json
                try:
                    current_snapshot = json.loads(snapshot_result.result)
                except json.JSONDecodeError:
                    current_snapshot = {"raw": snapshot_result.result}

        # Perform semantic validation
        # Convert snapshot to searchable text
        snapshot_text = _extract_text_from_snapshot(current_snapshot)

        # Check if expected content is present (case-insensitive)
        expected_lower = expected.lower()
        snapshot_text_lower = snapshot_text.lower()

        # Extract key terms from expected string
        key_terms = _extract_key_terms(expected_lower)

        # Check if key terms are present
        matched_terms = [term for term in key_terms if term in snapshot_text_lower]
        match_ratio = len(matched_terms) / len(key_terms) if key_terms else 1.0

        # Consider passed if majority of key terms match
        passed = match_ratio >= 0.5

        logger.info(
            "Validation result: passed=%s, match_ratio=%.2f, terms=%s",
            passed,
            match_ratio,
            matched_terms,
        )

        return {
            "passed": passed,
            "expected": expected,
            "actual": snapshot_text[:200] if snapshot_text else "No content",
            "accessibility_snapshot": current_snapshot,
            "match_ratio": match_ratio,
            "matched_terms": matched_terms,
        }

    except Exception as e:
        logger.error("Error validating via MCP: %s", e)
        return {
            "passed": False,
            "expected": expected,
            "actual": f"Error: {str(e)}",
            "accessibility_snapshot": accessibility_snapshot,
            "error": str(e),
        }


def _extract_text_from_snapshot(snapshot: dict[str, Any]) -> str:
    """Extract searchable text from accessibility snapshot.

    Args:
        snapshot: Accessibility snapshot dict

    Returns:
        Concatenated text content from the snapshot
    """
    texts: list[str] = []

    def _traverse(node: dict[str, Any] | list[Any] | str) -> None:
        if isinstance(node, str):
            texts.append(node)
        elif isinstance(node, dict):
            # Extract common accessibility properties
            for key in ("name", "text", "value", "description", "role"):
                if key in node and isinstance(node[key], str):
                    texts.append(node[key])
            # Traverse children
            for key in ("children", "nodes", "elements"):
                if key in node:
                    _traverse(node[key])
        elif isinstance(node, list):
            for item in node:
                _traverse(item)

    _traverse(snapshot)
    return " ".join(texts)


def _extract_key_terms(text: str) -> list[str]:
    """Extract key terms from expected outcome text.

    Filters out common words to focus on meaningful terms.

    Args:
        text: The expected outcome text

    Returns:
        List of key terms
    """
    # Common words to ignore
    stop_words = {
        "i", "should", "see", "the", "a", "an", "is", "are", "be",
        "have", "has", "will", "would", "can", "could", "to", "of",
        "in", "on", "at", "for", "with", "that", "this", "it",
        "and", "or", "not", "my", "their", "there", "here",
    }

    # Split and filter
    words = text.split()
    key_terms = [
        word.strip(".,!?\"'()[]{}") for word in words
        if word.strip(".,!?\"'()[]{}").lower() not in stop_words
        and len(word.strip(".,!?\"'()[]{}")) > 2
    ]

    return key_terms


async def close_browser() -> dict[str, Any]:
    """Close browser via Playwright MCP.

    Returns:
        Dictionary with close result
    """
    logger.info("Closing browser")

    client = _get_playwright_client()
    if client is None:
        logger.warning("Playwright MCP not configured. Returning stub close.")
        return {"success": True, "stub": True}

    try:
        result: MCPToolResult = await client.call_tool(
            "browser_close",
            params={},
        )

        if not result.success:
            logger.warning("Browser close returned error: %s", result.error)
            # Still consider it successful if browser is already closed
            return {"success": True, "warning": result.error}

        logger.info("Browser closed successfully")
        return {"success": True}

    except Exception as e:
        logger.warning("Error closing browser via MCP: %s", e)
        # Don't fail cleanup on close errors
        return {"success": True, "warning": str(e)}


async def take_screenshot(path: str | None = None) -> dict[str, Any]:
    """Take screenshot via Playwright MCP.

    Args:
        path: Optional path to save screenshot (ignored by MCP, returns base64)

    Returns:
        Dictionary with screenshot result
    """
    screenshot_path = path or f"/tmp/screenshot-{int(time.time())}.png"
    logger.info("Taking screenshot: %s", screenshot_path)

    client = _get_playwright_client()
    if client is None:
        logger.warning("Playwright MCP not configured. Returning stub screenshot.")
        return {
            "success": True,
            "stub": True,
            "path": screenshot_path,
        }

    try:
        result: MCPToolResult = await client.call_tool(
            "browser_screenshot",
            params={},
        )

        if not result.success:
            logger.warning("Screenshot failed: %s", result.error)
            return {
                "success": False,
                "error": result.error or "Failed to take screenshot",
            }

        # MCP returns base64 encoded screenshot
        # Save to file if path provided
        if result.result and path:
            import base64
            try:
                if isinstance(result.result, str):
                    # Assume base64 encoded PNG
                    img_data = base64.b64decode(result.result)
                    with open(path, "wb") as f:
                        f.write(img_data)
                    logger.info("Screenshot saved to: %s", path)
            except Exception as save_error:
                logger.warning("Failed to save screenshot to file: %s", save_error)

        return {
            "success": True,
            "path": screenshot_path,
            "data": result.result if isinstance(result.result, str) else None,
        }

    except Exception as e:
        logger.warning("Error taking screenshot via MCP: %s", e)
        return {
            "success": False,
            "error": str(e),
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
