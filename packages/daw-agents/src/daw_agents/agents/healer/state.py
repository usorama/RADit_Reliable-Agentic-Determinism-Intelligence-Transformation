"""Healer state definition for Healer Agent.

This module defines the TypedDict state schema for the LangGraph Healer workflow.
The Healer Agent implements error recovery workflow:

1. DiagnoseError: Analyze the failed tool output to extract error signature
2. QueryKnowledgeGraph: Search Neo4j for similar past errors and their resolutions
3. SuggestFix: Use LLM to generate fix based on error and past resolutions
4. ApplyFix: Apply the suggested fix to the failing code
5. ValidateFix: Run tests to verify the fix worked
6. Complete/Error: End states based on fix success/failure

The state tracks:
- Error information from failed tool output
- Similar errors found in knowledge graph
- Fix suggestion and applied fix code
- Validation results
- Attempt count and limits
- Error information for failures
"""

from __future__ import annotations

from typing import Any, TypedDict


class HealerState(TypedDict):
    """State schema for the Healer Agent LangGraph workflow.

    Attributes:
        error_info: Information about the failed tool output to heal
        similar_errors: List of similar errors found in Neo4j knowledge graph
        fix_suggestion: Suggested fix from LLM (None if not yet generated)
        fixed_code: The code after applying the fix
        status: Current workflow status (diagnose, query_knowledge, suggest_fix,
                apply_fix, validate, complete, error)
        validation_result: Result from running validation tests (None if not yet run)
        attempt: Current attempt count (starts at 0)
        max_attempts: Maximum allowed attempts (default 3)
        error: Error message if workflow fails (None if no error)
    """

    error_info: dict[str, Any]
    similar_errors: list[dict[str, Any]]
    fix_suggestion: dict[str, Any] | None
    fixed_code: str
    status: str
    validation_result: dict[str, Any] | None
    attempt: int
    max_attempts: int
    error: str | None
