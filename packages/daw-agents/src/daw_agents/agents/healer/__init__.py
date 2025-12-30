"""Healer Agent package for error recovery and self-healing.

This package provides the Healer Agent (OPS-002) which implements
error recovery workflow:

1. Diagnose failed tool outputs
2. Query Neo4j for similar past errors
3. Generate fixes using LLM + RAG
4. Apply and validate fixes
5. Store successful resolutions for future use

Key Components:
- Healer: Main agent class with LangGraph workflow
- HealerState: TypedDict state for workflow
- HealerStatus: Enum for workflow states
- ErrorInfo: Model for error information
- HealerResult: Model for workflow results

Dependencies:
- EXECUTOR-001: Developer Agent (produces failed outputs)
- DB-001: Neo4j Connector (knowledge graph)
- CORE-003: MCP Client (tool calls)
- MODEL-001: Model Router (fix generation)

Example:
    from daw_agents.agents.healer import Healer, ErrorInfo

    healer = Healer()
    error = ErrorInfo(
        tool_name="run_test",
        error_type="TestFailure",
        error_message="AssertionError",
        source_file="src/calc.py",
        test_file="tests/test_calc.py",
        source_code="def add(a, b): return a + b + 1",
        test_code="def test_add(): assert add(1, 1) == 2"
    )
    result = await healer.heal(error)
"""

from daw_agents.agents.healer.graph import Healer
from daw_agents.agents.healer.models import (
    ErrorInfo,
    FixSuggestion,
    HealerResult,
    HealerStatus,
    KnowledgeEntry,
    ValidationResult,
)
from daw_agents.agents.healer.state import HealerState

__all__ = [
    "Healer",
    "HealerState",
    "HealerStatus",
    "HealerResult",
    "ErrorInfo",
    "FixSuggestion",
    "KnowledgeEntry",
    "ValidationResult",
]
