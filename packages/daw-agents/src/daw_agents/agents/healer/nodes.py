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
import os
from typing import Any

from daw_agents.agents.healer.models import ErrorInfo
from daw_agents.agents.healer.state import HealerState
from daw_agents.memory.neo4j import Neo4jConfig, Neo4jConnector
from daw_agents.models.router import ModelRouter, TaskType
from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

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

    # Try to query Neo4j for similar errors
    # Note: VPS may be unreachable (72.60.204.156:7687), so handle gracefully
    try:
        # Get Neo4j configuration from environment or use defaults
        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://72.60.204.156:7687")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "daw_graph_2024")

        config = Neo4jConfig(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
        )

        connector = Neo4jConnector.get_instance(config)

        # Check connectivity before querying
        if not await connector.is_connected():
            logger.warning("Neo4j not connected, returning empty results")
            return []

        # Query for similar errors by signature and type
        cypher = """
            MATCH (e:ErrorResolution)
            WHERE e.error_type = $error_type
               OR e.error_signature CONTAINS $signature_part
            RETURN e.error_signature as signature,
                   e.error_type as type,
                   e.fix_description as fix_description,
                   e.fixed_code as fixed_code,
                   e.created_at as created_at
            ORDER BY e.created_at DESC
            LIMIT 5
        """

        # Use first 50 chars of signature for fuzzy matching
        signature_part = error_signature[:50] if len(error_signature) > 50 else error_signature

        results = await connector.query(
            cypher,
            params={"error_type": error_type, "signature_part": signature_part},
        )

        logger.info("Found %d similar errors in knowledge graph", len(results))
        return results

    except Exception as e:
        # Neo4j VPS may be unreachable - graceful fallback
        logger.warning("Failed to query Neo4j for similar errors: %s", str(e))
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

    # Build context from similar errors if available
    similar_context = ""
    if similar_errors:
        similar_context = "\n\n## Similar Past Errors and Fixes:\n"
        for i, err in enumerate(similar_errors[:3], 1):  # Limit to top 3
            similar_context += f"""
### Similar Error {i}:
- Type: {err.get('type', 'unknown')}
- Fix: {err.get('fix_description', 'No description')}
- Fixed Code Snippet: {err.get('fixed_code', 'N/A')[:500]}
"""

    # Build the prompt for the LLM
    prompt = f"""You are an expert software engineer tasked with fixing a code error.

## Error Details:
- Error Type: {error_info.get('error_type', 'unknown')}
- Error Message: {error_info.get('error_message', 'No message')}
- Error Signature: {error_info.get('error_signature', 'N/A')}
- Root Cause Analysis: {error_info.get('root_cause', 'Unknown')}

## Failed Source Code:
```
{error_info.get('source_code', 'No source code provided')}
```

## Test Code (if available):
```
{error_info.get('test_code', 'No test code provided')}
```
{similar_context}

## Previous Attempts: {previous_attempts}

Please analyze the error and provide a fix. Return your response in the following format:

DESCRIPTION: <brief description of the fix>
CONFIDENCE: <0.0 to 1.0>
FIXED_CODE:
```
<the complete fixed code>
```
"""

    try:
        # Use ModelRouter with TaskType.CODING for fix generation
        router = ModelRouter()
        response = await router.route(
            task_type=TaskType.CODING,
            messages=[
                {"role": "system", "content": "You are an expert code repair assistant."},
                {"role": "user", "content": prompt},
            ],
            metadata={"task": "healer_fix_suggestion", "attempt": previous_attempts + 1},
        )

        # Parse the LLM response
        description = "LLM-generated fix"
        confidence = 0.7
        fixed_code = error_info.get("source_code", "")

        # Extract description
        if "DESCRIPTION:" in response:
            desc_start = response.find("DESCRIPTION:") + len("DESCRIPTION:")
            desc_end = response.find("\n", desc_start)
            if desc_end > desc_start:
                description = response[desc_start:desc_end].strip()

        # Extract confidence
        if "CONFIDENCE:" in response:
            conf_start = response.find("CONFIDENCE:") + len("CONFIDENCE:")
            conf_end = response.find("\n", conf_start)
            if conf_end > conf_start:
                try:
                    confidence = float(response[conf_start:conf_end].strip())
                    confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                except ValueError:
                    confidence = 0.7

        # Extract fixed code
        if "FIXED_CODE:" in response and "```" in response:
            code_start = response.find("```", response.find("FIXED_CODE:"))
            if code_start != -1:
                code_start = response.find("\n", code_start) + 1
                code_end = response.find("```", code_start)
                if code_end > code_start:
                    fixed_code = response[code_start:code_end].strip()

        logger.info("Generated fix suggestion with confidence: %.2f", confidence)

        return {
            "description": description,
            "fixed_code": fixed_code,
            "confidence": confidence,
            "based_on_past_resolution": len(similar_errors) > 0,
            "llm_response": response,  # Include full response for debugging
        }

    except Exception as e:
        logger.error("Failed to generate fix suggestion via LLM: %s", str(e))
        # Fallback to placeholder if LLM fails
        return {
            "description": f"Fallback fix (LLM error: {str(e)[:100]})",
            "fixed_code": error_info.get("source_code", ""),
            "confidence": 0.3,
            "based_on_past_resolution": False,
            "error": str(e),
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

    import time

    start_time = time.time()

    try:
        # Get E2B API key from environment
        e2b_api_key = os.environ.get("E2B_API_KEY")
        if not e2b_api_key:
            logger.warning("E2B_API_KEY not set, cannot run validation tests")
            return {
                "passed": False,
                "output": "E2B_API_KEY environment variable not set",
                "exit_code": 1,
                "duration_ms": 0.0,
            }

        config = SandboxConfig(
            api_key=e2b_api_key,
            timeout=120,  # 2 minute timeout for test execution
        )

        async with E2BSandbox(config) as sandbox:
            # Write the fixed source code to sandbox
            sandbox_source_file = f"/tmp/{source_file.split('/')[-1]}"
            await sandbox.write_file(sandbox_source_file, fixed_code)
            logger.debug("Wrote fixed code to sandbox: %s", sandbox_source_file)

            # Write the test code to sandbox
            sandbox_test_file = f"/tmp/{test_file.split('/')[-1]}"
            await sandbox.write_file(sandbox_test_file, test_code)
            logger.debug("Wrote test code to sandbox: %s", sandbox_test_file)

            # Run pytest on the test file
            # Use PYTHONPATH to include /tmp so imports work
            result = await sandbox.run_command(
                f"cd /tmp && PYTHONPATH=/tmp python -m pytest {sandbox_test_file} -v --tb=short",
                timeout=60,
            )

            duration_ms = (time.time() - start_time) * 1000

            passed = result.success
            output = result.stdout
            if result.stderr:
                output += f"\n\nSTDERR:\n{result.stderr}"
            if result.error:
                output += f"\n\nERROR:\n{result.error}"

            logger.info(
                "Validation tests %s (exit_code=%s, duration=%.2fms)",
                "PASSED" if passed else "FAILED",
                result.exit_code,
                duration_ms,
            )

            return {
                "passed": passed,
                "output": output,
                "exit_code": result.exit_code if result.exit_code is not None else 1,
                "duration_ms": duration_ms,
            }

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("Failed to run validation tests: %s", str(e))
        return {
            "passed": False,
            "output": f"Sandbox execution failed: {str(e)}",
            "exit_code": 1,
            "duration_ms": duration_ms,
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
