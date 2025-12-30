"""Gherkin parser for UAT Agent.

This module provides the GherkinParser class for parsing Gherkin scenarios
(Given/When/Then format) into executable steps.

The parser supports:
- Given steps: Setup/navigation actions
- When steps: User interaction actions
- Then steps: Validation/assertion actions
- And/But steps: Continue previous step type

Example:
    parser = GherkinParser()
    steps = parser.parse('''
        Given I am on the login page
        When I enter "user@example.com" in the email field
        And I click the submit button
        Then I should see the dashboard
    ''')
"""

from __future__ import annotations

import re
from typing import ClassVar

from daw_agents.agents.uat.models import GherkinStep


class GherkinParser:
    """Parser for Gherkin scenarios.

    Parses Given/When/Then scenarios into executable GherkinStep objects.
    Supports And/But keywords which inherit the action type from the
    previous step.

    Attributes:
        action_patterns: Dictionary mapping patterns to action types
        keyword_pattern: Regex pattern for matching Gherkin keywords

    Example:
        parser = GherkinParser()
        steps = parser.parse("Given I am on the login page")
        assert steps[0].keyword == "Given"
        assert steps[0].action_type == "navigate"
    """

    # Class-level patterns for action type inference
    ACTION_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "navigate": [
            r"(?:am on|go to|visit|navigate to|open)\s+(?:the\s+)?(.+?)(?:\s+page)?$",
            r"(?:the\s+)?(?:url|page)\s+is\s+(.+)$",
        ],
        "click": [
            r"(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?(.+?)(?:\s+button|\s+link)?$",
            r"(?:click|press|tap)\s+(?:on\s+)?(.+)$",
        ],
        "type": [
            r"(?:enter|type|input|fill(?:\s+in)?)\s+\"?([^\"]+)\"?\s+(?:in(?:to)?|into)\s+(?:the\s+)?(.+)$",
            r"(?:enter|type|input)\s+\"?([^\"]+)\"?$",
        ],
        "wait": [
            r"(?:wait|pause)\s+(?:for\s+)?(\d+)\s+(?:second|millisecond|ms|s)s?$",
            r"(?:wait\s+for|until)\s+(.+)$",
        ],
        "assert": [
            r"(?:should\s+)?see\s+(?:the\s+)?(.+)$",
            r"(?:should\s+)?(?:be\s+)?(?:on|at)\s+(?:the\s+)?(.+)$",
            r"(?:the\s+)?(.+)\s+(?:should|must)\s+(?:be\s+)?(.+)$",
            r"(?:should\s+)?(?:not\s+)?(?:contain|have|include)\s+(.+)$",
        ],
        "select": [
            r"(?:select|choose)\s+\"?([^\"]+)\"?\s+(?:from|in)\s+(?:the\s+)?(.+)$",
        ],
        "scroll": [
            r"(?:scroll)\s+(?:to\s+)?(?:the\s+)?(.+)$",
        ],
        "hover": [
            r"(?:hover\s+over|mouse\s+over)\s+(?:the\s+)?(.+)$",
        ],
    }

    # Keywords with their default action types
    KEYWORD_DEFAULTS: ClassVar[dict[str, str]] = {
        "Given": "navigate",
        "When": "interact",
        "Then": "assert",
        "And": "continue",  # Inherits from previous
        "But": "continue",  # Inherits from previous
    }

    def __init__(self) -> None:
        """Initialize the Gherkin parser."""
        self.keyword_pattern = re.compile(
            r"^\s*(Given|When|Then|And|But)\s+(.+)$",
            re.IGNORECASE,
        )

    def parse(self, scenario: str) -> list[GherkinStep]:
        """Parse a Gherkin scenario into executable steps.

        Args:
            scenario: Gherkin scenario text with Given/When/Then steps

        Returns:
            List of GherkinStep objects

        Example:
            steps = parser.parse('''
                Given I am on the login page
                When I click the submit button
                Then I should see the dashboard
            ''')
        """
        steps: list[GherkinStep] = []
        previous_keyword = "Given"  # Default for And/But inheritance

        for line in scenario.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            match = self.keyword_pattern.match(line)
            if not match:
                continue

            keyword = match.group(1).capitalize()
            text = match.group(2).strip()

            # Determine action type
            action_type = self._infer_action_type(keyword, text, previous_keyword)

            # Extract selector and value if present
            selector, value = self._extract_selector_value(text, action_type)

            step = GherkinStep(
                keyword=keyword,
                text=text,
                action_type=action_type,
                selector=selector,
                value=value,
            )
            steps.append(step)

            # Update previous keyword for And/But inheritance
            if keyword not in ("And", "But"):
                previous_keyword = keyword

        return steps

    def _infer_action_type(
        self,
        keyword: str,
        text: str,
        previous_keyword: str,
    ) -> str:
        """Infer the action type from keyword and step text.

        Args:
            keyword: The Gherkin keyword
            text: The step text
            previous_keyword: Previous non-And/But keyword

        Returns:
            Inferred action type string
        """
        # For And/But, inherit from previous keyword
        effective_keyword = keyword
        if keyword in ("And", "But"):
            effective_keyword = previous_keyword

        # Try to match against action patterns
        text_lower = text.lower()
        for action_type, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return action_type

        # Fall back to keyword defaults
        if effective_keyword == "Given":
            return "navigate"
        elif effective_keyword == "When":
            return "interact"
        elif effective_keyword == "Then":
            return "assert"

        return "unknown"

    def _extract_selector_value(
        self,
        text: str,
        action_type: str,
    ) -> tuple[str | None, str | None]:
        """Extract selector and value from step text.

        Args:
            text: The step text
            action_type: The inferred action type

        Returns:
            Tuple of (selector, value)
        """
        selector = None
        value = None

        # Extract quoted values
        quoted_match = re.search(r'"([^"]+)"', text)
        if quoted_match:
            value = quoted_match.group(1)

        # Extract common selector patterns
        if action_type == "click":
            # "click the submit button" -> selector = "submit button"
            click_match = re.search(
                r"(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?(.+?)(?:\s+button|\s+link)?$",
                text.lower(),
            )
            if click_match:
                selector = click_match.group(1).strip()

        elif action_type == "type":
            # "enter 'email' in the email field" -> selector = "email field"
            type_match = re.search(
                r"(?:in(?:to)?|into)\s+(?:the\s+)?(.+)$",
                text.lower(),
            )
            if type_match:
                selector = type_match.group(1).strip()

        elif action_type == "navigate":
            # For navigate, the value might be a URL
            if not value:
                # Extract URL-like patterns
                url_match = re.search(r"https?://[^\s]+", text)
                if url_match:
                    value = url_match.group(0)

        return selector, value
