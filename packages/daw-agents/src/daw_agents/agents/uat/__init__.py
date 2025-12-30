"""UAT Agent package for browser automation using Playwright MCP.

This package implements the UAT Agent (UAT-001) which performs browser-based
acceptance testing using Playwright MCP for automation.

Features:
- Operates on accessibility snapshots (not screenshots) for determinism
- Supports cross-browser testing (Chromium, Firefox, WebKit)
- Executes Gherkin scenarios (Given/When/Then)
- Generates validation reports with screenshots, traces, and timing

Exports:
    UATAgent: Main agent class with LangGraph workflow
    UATState: TypedDict state schema for the workflow
    UATStatus: Enum for workflow states
    UATResult: Pydantic model for workflow results
    GherkinParser: Parser for Gherkin scenarios
    GherkinStep: Pydantic model for parsed steps
    ValidationResult: Pydantic model for validation results

Dependencies:
    - VALIDATOR-001: Validator Agent (for validation patterns)
    - FRONTEND-002: Agent Trace UI (for trace viewing)
    - CORE-003: MCP Client (for Playwright MCP integration)

Example:
    from daw_agents.agents.uat import UATAgent, UATResult

    agent = UATAgent(browser_type="chromium")
    result = await agent.execute(
        scenario='''
            Given I am on the login page
            When I click the submit button
            Then I should see the dashboard
        ''',
        url="http://localhost:3000/login"
    )
    if result.success:
        print("All validations passed!")
"""

from daw_agents.agents.uat.graph import UATAgent
from daw_agents.agents.uat.models import (
    GherkinStep,
    UATResult,
    UATStatus,
    ValidationResult,
)
from daw_agents.agents.uat.parser import GherkinParser
from daw_agents.agents.uat.state import UATState

__all__ = [
    "GherkinParser",
    "GherkinStep",
    "UATAgent",
    "UATResult",
    "UATState",
    "UATStatus",
    "ValidationResult",
]
