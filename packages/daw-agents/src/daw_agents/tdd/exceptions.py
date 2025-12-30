"""
TDD Guard Exceptions.

Custom exceptions for TDD workflow violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from daw_agents.tdd.guard import TestResult


@dataclass
class TDDViolationError(Exception):
    """
    Exception raised when TDD workflow rules are violated.

    This exception is raised when:
    - Attempting to write source code without a test file
    - Attempting to write source code when test already passes (skipping RED phase)
    - Attempting to mark GREEN phase complete when tests still fail
    """

    message: str
    phase: str
    test_file: str
    source_file: str | None = None
    test_result: TestResult | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize the exception with the message."""
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return a string representation of the violation."""
        parts = [self.message]
        if self.source_file:
            parts.append(f"Source: {self.source_file}")
        parts.append(f"Test: {self.test_file}")
        parts.append(f"Phase: {self.phase}")
        return " | ".join(parts)


# Alias for backward compatibility
TDDViolation = TDDViolationError
