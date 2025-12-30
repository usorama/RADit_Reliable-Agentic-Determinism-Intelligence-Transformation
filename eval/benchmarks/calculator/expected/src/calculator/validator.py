"""Input validation for the calculator.

This module provides validation functions for user input.
"""

from typing import Final

VALID_OPERATIONS: Final[frozenset[str]] = frozenset({"+", "-", "*", "/"})


class ValidationError(Exception):
    """Raised when input validation fails.

    Attributes:
        message: Description of the validation error
    """

    def __init__(self, message: str) -> None:
        """Initialize ValidationError with a message.

        Args:
            message: Human-readable error description
        """
        self.message = message
        super().__init__(self.message)


def validate_number(value: str) -> float:
    """Validate and convert string to number.

    Args:
        value: String representation of a number

    Returns:
        The numeric value as a float

    Raises:
        ValidationError: If value is empty, whitespace-only, or not a valid number

    Examples:
        >>> validate_number("42")
        42.0
        >>> validate_number("3.14")
        3.14
        >>> validate_number("-5")
        -5.0
    """
    if not value or not value.strip():
        raise ValidationError("Input cannot be empty or whitespace-only")

    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        raise ValidationError(f"Invalid number: '{value}'") from None


def validate_operation(op: str) -> str:
    """Validate operation is supported.

    Args:
        op: Operation symbol (+, -, *, /)

    Returns:
        The validated operation symbol

    Raises:
        ValidationError: If operation is not one of +, -, *, /

    Examples:
        >>> validate_operation("+")
        '+'
        >>> validate_operation("*")
        '*'
    """
    if not op:
        raise ValidationError("Operation cannot be empty")

    if op not in VALID_OPERATIONS:
        raise ValidationError(
            f"Invalid operation: '{op}'. Must be one of: {', '.join(sorted(VALID_OPERATIONS))}"
        )

    return op
