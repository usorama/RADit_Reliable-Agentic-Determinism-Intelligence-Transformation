"""UAT state definition for UAT Agent.

This module defines the TypedDict state schema for the LangGraph UAT workflow.
The UAT Agent uses Playwright MCP for browser automation:

1. Setup: Initialize browser via Playwright MCP
2. Navigate: Navigate to target URL and capture accessibility snapshot
3. Interact: Execute user interactions (click, type, etc.)
4. Validate: Check expected outcomes using accessibility snapshots
5. Cleanup: Close browser and generate reports

The state tracks:
- Gherkin scenario and URL
- Browser type (Chromium, Firefox, WebKit)
- Current workflow status
- Parsed steps and current step index
- Accessibility snapshots, screenshots, and traces
- Validation results
- Error information and timing
"""

from __future__ import annotations

from typing import Any, TypedDict


class UATState(TypedDict):
    """State schema for the UAT Agent LangGraph workflow.

    Attributes:
        scenario: The Gherkin scenario to execute (Given/When/Then)
        url: The target URL for the test
        browser_type: Browser to use (chromium, firefox, webkit)
        status: Current workflow status (setup, navigate, interact, validate, complete, error)
        current_step: Index of the current step being executed
        steps: Parsed Gherkin steps as dictionaries
        accessibility_snapshots: List of accessibility snapshots captured
        screenshots: List of screenshot file paths
        traces: List of trace file paths
        validation_results: List of validation results per step
        error: Error message if workflow fails (None if no error)
        timing: Dictionary of timing measurements
    """

    scenario: str
    url: str
    browser_type: str
    status: str
    current_step: int
    steps: list[dict[str, Any]]
    accessibility_snapshots: list[dict[str, Any]]
    screenshots: list[str]
    traces: list[str]
    validation_results: list[dict[str, Any]]
    error: str | None
    timing: dict[str, Any]
