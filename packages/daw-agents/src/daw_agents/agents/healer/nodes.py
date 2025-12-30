"""Node functions for the Healer Agent LangGraph workflow.

This module implements the node functions for the error recovery workflow:

1. diagnose_error_node: Analyze the failed tool output
2. query_knowledge_graph_node: Search Neo4j for similar errors
3. suggest_fix_node: Generate fix using LLM
4. apply_fix_node: Apply the suggested fix
5. validate_fix_node: Run tests to verify the fix

And routing functions:
- route_after_diagnose: Go to query_knowledge
- route_after_query_knowledge: Go to suggest_fix
- route_after_suggest_fix: Go to apply_fix
- route_after_apply_fix: Go to validate
- route_after_validate: Go to complete, error, or retry

Dependencies:
- DB-001: Neo4j Connector for knowledge graph queries
- CORE-003: MCP Client for tool calls
- MODEL-001: Model Router with TaskType.CODING
"""

from __future__ import annotations

import logging
from typing import Any

from daw_agents.agents.healer.models import ErrorInfo
from daw_agents.agents.healer.state import HealerState

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions (to be mocked in tests, implemented with actual logic)
# =============================================================================


async def analyze_error(
    error_info: dict[str, Any],
) -> dict[str, Any]:
    """Analyze the error to extract signature and root cause.

    This function is called by diagnose_error_node and can be mocked in tests.

    Args:
        error_info: Dictionary containing error details

    Returns:
        Dictionary with error_signature and root_cause analysis
    """
    logger.info("Analyzing error: %s", error_info.get("error_type", "unknown"))

    # Create ErrorInfo model for signature generation
    error = ErrorInfo(**error_info)
    signature = error.to_signature()

    return {
        "error_signature": signature,
        "root_cause": f"Analysis of {error_info.get('error_type', 'unknown')} error",
    }


async def query_similar_errors(
    error_signature: str,
    error_type: str,
) -> list[dict[str, Any]]:
    """Query Neo4j for similar past errors.

    This function is called by query_knowledge_graph_node and can be mocked in tests.

    Args:
        error_signature: Normalized error signature
        error_type: Type of error

    Returns:
        List of similar error resolutions from knowledge graph
    """
    logger.info("Querying knowledge graph for: %s", error_signature)

    # In production, this would query Neo4j using DB-001
    # For now, return empty list (will be mocked in tests)
    return []


async def generate_fix_suggestion(
    error_info: dict[str, Any],
    similar_errors: list[dict[str, Any]],
    previous_attempts: int,
) -> dict[str, Any]:
    """Generate a fix suggestion using LLM.

    This function is called by suggest_fix_node and can be mocked in tests.

    Args:
        error_info: Dictionary containing error details
        similar_errors: List of similar past errors with resolutions
        previous_attempts: Number of previous fix attempts

    Returns:
        Dictionary with fix suggestion details
    """
    logger.info("Generating fix suggestion, attempt: %d", previous_attempts + 1)

    # In production, this would use ModelRouter with TaskType.CODING
    # For now, return placeholder
    return {
        "description": "Placeholder fix suggestion",
        "fixed_code": error_info.get("source_code", ""),
        "confidence": 0.5,
        "based_on_past_resolution": len(similar_errors) > 0,
    }


async def apply_code_fix(
    source_code: str,
    fix_suggestion: dict[str, Any],
) -> str:
    """Apply the suggested fix to the source code.

    This function is called by apply_fix_node and can be mocked in tests.

    Args:
        source_code: Original source code
        fix_suggestion: The fix suggestion to apply

    Returns:
        Fixed code as a string
    """
    logger.info("Applying fix: %s", fix_suggestion.get("description", ""))

    # Return the fixed code from the suggestion
    fixed_code: str = fix_suggestion.get("fixed_code", source_code)
    return fixed_code


async def run_validation_tests(
    fixed_code: str,
    test_code: str,
    source_file: str,
    test_file: str,
) -> dict[str, Any]:
    """Run validation tests on the fixed code.

    This function is called by validate_fix_node and can be mocked in tests.

    Args:
        fixed_code: The fixed source code
        test_code: Test code to run
        source_file: Path to source file
        test_file: Path to test file

    Returns:
        Dictionary with validation results
    """
    logger.info("Running validation tests for: %s", test_file)

    # In production, this would use E2B sandbox (CORE-004) for test execution
    # For now, return placeholder
    return {
        "passed": False,
        "output": "No tests executed (placeholder)",
        "exit_code": 1,
        "duration_ms": 0.0,
    }


async def store_to_neo4j(
    error_signature: str,
    error_type: str,
    fix_description: str,
    fixed_code: str,
) -> str:
    """Store a successful resolution in Neo4j.

    This function is called by store_resolution and can be mocked in tests.

    Args:
        error_signature: Error signature for matching
        error_type: Type of error
        fix_description: Description of the fix
        fixed_code: The code that fixed the error

    Returns:
        ID of the created knowledge entry
    """
    logger.info("Storing resolution to Neo4j for: %s", error_type)

    # In production, this would use Neo4j connector (DB-001)
    import uuid

    return f"entry-{uuid.uuid4().hex[:8]}"


async def store_resolution(
    error_info: ErrorInfo,
    fix_description: str,
    fixed_code: str,
) -> str:
    """Store a successful error resolution in Neo4j knowledge graph.

    Args:
        error_info: The original error information
        fix_description: Description of how the error was fixed
        fixed_code: The code that fixed the error

    Returns:
        ID of the created knowledge entry
    """
    signature = error_info.to_signature()

    entry_id = await store_to_neo4j(
        error_signature=signature,
        error_type=error_info.error_type,
        fix_description=fix_description,
        fixed_code=fixed_code,
    )

    logger.info("Stored resolution with ID: %s", entry_id)
    return entry_id


# =============================================================================
# Node Functions
# =============================================================================


async def diagnose_error_node(state: HealerState) -> dict[str, Any]:
    """Analyze the failed tool output to extract error signature.

    This is the first step in the healing workflow.

    Args:
        state: Current healer state

    Returns:
        State updates with error analysis and updated status
    """
    logger.info("Executing diagnose_error_node")

    # Analyze the error
    analysis = await analyze_error(state["error_info"])

    # Update error_info with analysis results
    updated_error_info = {
        **state["error_info"],
        "error_signature": analysis.get("error_signature", ""),
        "root_cause": analysis.get("root_cause", ""),
    }

    return {
        "error_info": updated_error_info,
        "status": "query_knowledge",
    }


async def query_knowledge_graph_node(state: HealerState) -> dict[str, Any]:
    """Search Neo4j for similar past errors and their resolutions.

    Queries the knowledge graph using the error signature to find
    similar past errors that were successfully resolved.

    Args:
        state: Current healer state

    Returns:
        State updates with similar errors and updated status
    """
    logger.info("Executing query_knowledge_graph_node")

    error_info = state["error_info"]
    error_signature = error_info.get("error_signature", "")
    error_type = error_info.get("error_type", "")

    # Query for similar errors
    similar_errors = await query_similar_errors(
        error_signature=error_signature,
        error_type=error_type,
    )

    logger.info("Found %d similar errors", len(similar_errors))

    return {
        "similar_errors": similar_errors,
        "status": "suggest_fix",
    }


async def suggest_fix_node(state: HealerState) -> dict[str, Any]:
    """Generate a fix suggestion using LLM.

    Uses the error information and similar past resolutions to
    generate a fix suggestion.

    Args:
        state: Current healer state

    Returns:
        State updates with fix suggestion and updated status
    """
    logger.info("Executing suggest_fix_node, attempt: %d", state["attempt"])

    fix_suggestion = await generate_fix_suggestion(
        error_info=state["error_info"],
        similar_errors=state["similar_errors"],
        previous_attempts=state["attempt"],
    )

    return {
        "fix_suggestion": fix_suggestion,
        "status": "apply_fix",
    }


async def apply_fix_node(state: HealerState) -> dict[str, Any]:
    """Apply the suggested fix to the failing code.

    Args:
        state: Current healer state

    Returns:
        State updates with fixed code and updated status
    """
    logger.info("Executing apply_fix_node")

    source_code = state["error_info"].get("source_code", "")
    fix_suggestion = state["fix_suggestion"]

    if fix_suggestion is None:
        return {
            "fixed_code": source_code,
            "status": "validate",
            "error": "No fix suggestion available",
        }

    fixed_code = await apply_code_fix(
        source_code=source_code,
        fix_suggestion=fix_suggestion,
    )

    return {
        "fixed_code": fixed_code,
        "status": "validate",
    }


async def validate_fix_node(state: HealerState) -> dict[str, Any]:
    """Run validation tests on the fixed code.

    Args:
        state: Current healer state

    Returns:
        State updates with validation result and incremented attempt
    """
    logger.info("Executing validate_fix_node, attempt: %d", state["attempt"])

    validation_result = await run_validation_tests(
        fixed_code=state["fixed_code"],
        test_code=state["error_info"].get("test_code", ""),
        source_file=state["error_info"].get("source_file", ""),
        test_file=state["error_info"].get("test_file", ""),
    )

    return {
        "validation_result": validation_result,
        "attempt": state["attempt"] + 1,
    }


# =============================================================================
# Routing Functions
# =============================================================================


def route_after_diagnose(state: HealerState) -> str:
    """Route after diagnose_error node.

    Always proceeds to query_knowledge to find similar past errors.

    Args:
        state: Current healer state

    Returns:
        Next node name: "query_knowledge"
    """
    return "query_knowledge"


def route_after_query_knowledge(state: HealerState) -> str:
    """Route after query_knowledge_graph node.

    Always proceeds to suggest_fix to generate a fix suggestion.

    Args:
        state: Current healer state

    Returns:
        Next node name: "suggest_fix"
    """
    return "suggest_fix"


def route_after_suggest_fix(state: HealerState) -> str:
    """Route after suggest_fix node.

    Proceeds to apply_fix if a suggestion was generated.

    Args:
        state: Current healer state

    Returns:
        Next node name: "apply_fix"
    """
    return "apply_fix"


def route_after_apply_fix(state: HealerState) -> str:
    """Route after apply_fix node.

    Proceeds to validate to test the fix.

    Args:
        state: Current healer state

    Returns:
        Next node name: "validate"
    """
    return "validate"


def route_after_validate(state: HealerState) -> str:
    """Route after validate_fix node based on results.

    Decision logic:
    - If validation passes: go to "complete"
    - If max attempts exceeded: go to "error"
    - If validation fails and can retry: go to "suggest_fix"

    Args:
        state: Current healer state

    Returns:
        Next node name: "complete", "error", or "suggest_fix"
    """
    validation_result = state.get("validation_result", {})
    passed = validation_result.get("passed", False) if validation_result else False
    attempt = state["attempt"]
    max_attempts = state["max_attempts"]

    # Validation passed - success!
    if passed:
        logger.info("Validation passed - healing complete")
        return "complete"

    # Max attempts exceeded - give up
    if attempt >= max_attempts:
        logger.warning("Max attempts (%d) reached - giving up", max_attempts)
        return "error"

    # Validation failed - retry with new suggestion
    logger.info("Validation failed - retrying (attempt %d/%d)", attempt, max_attempts)
    return "suggest_fix"
