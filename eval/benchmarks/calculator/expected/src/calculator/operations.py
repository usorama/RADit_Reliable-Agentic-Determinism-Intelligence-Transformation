"""Core arithmetic operations for the calculator.

This module provides basic arithmetic functions: add, subtract, multiply, divide.
All functions accept both integers and floating-point numbers.
"""


def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: First number (addend)
        b: Second number (addend)

    Returns:
        Sum of a and b

    Examples:
        >>> add(2, 3)
        5.0
        >>> add(-2, 3)
        1.0
        >>> add(2.5, 3.5)
        6.0
    """
    return float(a + b)


def subtract(a: float, b: float) -> float:
    """Subtract b from a.

    Args:
        a: Minuend (number to subtract from)
        b: Subtrahend (number to subtract)

    Returns:
        Difference (a - b)

    Examples:
        >>> subtract(5, 3)
        2.0
        >>> subtract(3, 5)
        -2.0
        >>> subtract(-2, -3)
        1.0
    """
    return float(a - b)


def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a: First factor
        b: Second factor

    Returns:
        Product of a and b

    Examples:
        >>> multiply(4, 3)
        12.0
        >>> multiply(5, 0)
        0.0
        >>> multiply(-2, 3)
        -6.0
    """
    return float(a * b)


def divide(a: float, b: float) -> float:
    """Divide a by b.

    Args:
        a: Dividend (number to be divided)
        b: Divisor (number to divide by)

    Returns:
        Quotient (a / b)

    Raises:
        ZeroDivisionError: If b is zero

    Examples:
        >>> divide(10, 2)
        5.0
        >>> divide(5, 2)
        2.5
        >>> divide(-6, 3)
        -2.0
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return float(a / b)
