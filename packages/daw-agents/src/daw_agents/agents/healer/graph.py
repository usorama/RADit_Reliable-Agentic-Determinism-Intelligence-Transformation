"""Healer Agent implementation using LangGraph.

This module implements the Healer Agent (OPS-002) that performs error recovery:

1. DiagnoseError: Analyze the failed tool output to extract error signature
2. QueryKnowledgeGraph: Search Neo4j for similar past errors and their resolutions
3. SuggestFix: Use LLM to generate fix based on error and past resolutions
4. ApplyFix: Apply the suggested fix to the failing code
5. ValidateFix: Run tests to verify the fix worked

Key Dependencies:
- EXECUTOR-001: Developer Agent (produces failed tool outputs)
- DB-001: Neo4j Connector (for knowledge graph queries)
- CORE-003: MCP Client for tool calls (git, filesystem)
- MODEL-001: Model Router with TaskType.CODING

CRITICAL ARCHITECTURE DECISION:
The Healer Agent uses TaskType.CODING for model routing to generate fixes.
It integrates with Neo4j for RAG-based error resolution retrieval.
Auto-retry logic allows up to 3 attempts before escalating.

Workflow Graph:
    START -> diagnose_error -> query_knowledge_graph -> suggest_fix
          -> apply_fix -> validate_fix -> [conditional]
                                           |-> complete (END) - fix worked
                                           |-> suggest_fix (retry loop)
                                           |-> error (END) - max attempts
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from daw_agents.agents.healer.models import ErrorInfo, HealerResult
from daw_agents.agents.healer.nodes import (
    apply_fix_node,
    diagnose_error_node,
    query_knowledge_graph_node,
    route_after_apply_fix,
    route_after_diagnose,
    route_after_query_knowledge,
    route_after_suggest_fix,
    route_after_validate,
    store_resolution,
    suggest_fix_node,
    validate_fix_node,
)
from daw_agents.agents.healer.state import HealerState
from daw_agents.models.router import ModelRouter, TaskType

if TYPE_CHECKING:
    from daw_agents.mcp.client import MCPClient
    from daw_agents.memory.neo4j import Neo4jConnector

logger = logging.getLogger(__name__)


class Healer:
    """Healer Agent for error recovery and self-healing.

    The Healer Agent implements an error recovery workflow:
    1. Diagnose error from failed tool output
    2. Query Neo4j knowledge graph for similar past errors
    3. Generate fix suggestion using LLM + RAG
    4. Apply fix to failing code
    5. Validate fix by running tests
    6. Store successful resolutions for future RAG

    The agent uses ModelRouter with TaskType.CODING for fix generation
    and Neo4j for storing and retrieving past error resolutions.

    Attributes:
        router: ModelRouter instance for LLM calls
        task_type: Always TaskType.CODING for fix generation
        max_attempts: Maximum healing attempts to prevent infinite loops (default: 3)
        graph: Compiled LangGraph workflow
        neo4j_connector: Optional Neo4j connector for knowledge graph
        mcp_client: Optional MCP client for tool integration

    Example:
        healer = Healer()
        error_info = ErrorInfo(
            tool_name="run_test",
            error_type="TestFailure",
            error_message="AssertionError: assert 1 + 1 == 3",
            source_file="src/calc.py",
            test_file="tests/test_calc.py",
            source_code="def add(a, b): return a + b + 1",
            test_code="def test_add(): assert add(1, 1) == 2"
        )
        result = await healer.heal(error_info)
        if result.success:
            print(f"Fixed code:\\n{result.fixed_code}")
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
        max_attempts: int = 3,
        neo4j_connector: Neo4jConnector | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        """Initialize the Healer Agent.

        Args:
            router: Optional ModelRouter instance. If None, creates a new one.
            max_attempts: Maximum healing attempts to prevent infinite loops (default: 3)
            neo4j_connector: Optional Neo4j connector for knowledge graph queries
            mcp_client: Optional MCP client for tool calls
        """
        self.router = router or ModelRouter()
        self.task_type = TaskType.CODING
        self.max_attempts = max_attempts
        self.neo4j_connector = neo4j_connector
        self.mcp_client = mcp_client
        self.graph = self._build_graph()

        logger.info(
            "Healer Agent initialized with model: %s, max_attempts: %d",
            self.router.get_model_for_task(TaskType.CODING),
            self.max_attempts,
        )

    def _build_graph(self) -> Any:
        """Build the LangGraph error recovery workflow.

        Creates a StateGraph with the following flow:
        START -> diagnose_error -> query_knowledge_graph -> suggest_fix
              -> apply_fix -> validate_fix -> [conditional edges]
                                               |-> complete (END)
                                               |-> suggest_fix (retry)
                                               |-> error (END)

        Returns:
            Compiled LangGraph workflow
        """
        # Create the state graph
        workflow = StateGraph(HealerState)

        # Add nodes for each healing step
        workflow.add_node("diagnose_error", diagnose_error_node)
        workflow.add_node("query_knowledge_graph", query_knowledge_graph_node)
        workflow.add_node("suggest_fix", suggest_fix_node)
        workflow.add_node("apply_fix", apply_fix_node)
        workflow.add_node("validate_fix", validate_fix_node)

        # Entry point: Start with diagnose_error
        workflow.add_edge(START, "diagnose_error")

        # After diagnose, query knowledge graph
        workflow.add_conditional_edges(
            "diagnose_error",
            route_after_diagnose,
            {
                "query_knowledge": "query_knowledge_graph",
            },
        )

        # After query_knowledge, suggest fix
        workflow.add_conditional_edges(
            "query_knowledge_graph",
            route_after_query_knowledge,
            {
                "suggest_fix": "suggest_fix",
            },
        )

        # After suggest_fix, apply the fix
        workflow.add_conditional_edges(
            "suggest_fix",
            route_after_suggest_fix,
            {
                "apply_fix": "apply_fix",
            },
        )

        # After apply_fix, validate
        workflow.add_conditional_edges(
            "apply_fix",
            route_after_apply_fix,
            {
                "validate": "validate_fix",
            },
        )

        # After validate, decide based on results
        workflow.add_conditional_edges(
            "validate_fix",
            route_after_validate,
            {
                "complete": END,
                "error": END,
                "suggest_fix": "suggest_fix",
            },
        )

        # Compile the graph
        return workflow.compile()

    def configure_neo4j(self, neo4j_connector: Neo4jConnector) -> None:
        """Configure Neo4j connector for knowledge graph queries.

        Args:
            neo4j_connector: Neo4jConnector instance for knowledge graph
        """
        self.neo4j_connector = neo4j_connector
        logger.info("Neo4j connector configured for Healer Agent")

    def configure_mcp(self, mcp_client: MCPClient) -> None:
        """Configure MCP client for tool integration.

        Args:
            mcp_client: MCPClient instance for tool calls
        """
        self.mcp_client = mcp_client
        logger.info("MCP client configured for Healer Agent")

    async def heal(
        self,
        error_info: ErrorInfo,
    ) -> HealerResult:
        """Execute the healing workflow for a given error.

        Runs the complete healing cycle:
        1. Diagnose error
        2. Query knowledge graph for similar errors
        3. Generate fix suggestion
        4. Apply fix
        5. Validate fix
        6. Retry or complete

        Args:
            error_info: ErrorInfo describing the error to heal

        Returns:
            HealerResult with the fixed code and status
        """
        logger.info(
            "Starting Healer workflow for error: %s", error_info.error_type
        )

        # Initialize state
        initial_state: HealerState = {
            "error_info": error_info.model_dump(),
            "similar_errors": [],
            "fix_suggestion": None,
            "fixed_code": "",
            "status": "diagnose",
            "validation_result": None,
            "attempt": 0,
            "max_attempts": self.max_attempts,
            "error": None,
        }

        # Run the workflow
        final_state = await self.graph.ainvoke(initial_state)

        # Determine success based on final status
        status = final_state.get("status", "error")
        success = status == "complete"

        # If successful, store the resolution for future RAG
        knowledge_entry_id = None
        fix_description = ""

        if success:
            fix_suggestion = final_state.get("fix_suggestion", {})
            fix_description = (
                fix_suggestion.get("description", "")
                if fix_suggestion
                else ""
            )

            # Store successful resolution
            try:
                knowledge_entry_id = await store_resolution(
                    error_info=error_info,
                    fix_description=fix_description,
                    fixed_code=final_state.get("fixed_code", ""),
                )
                logger.info("Stored resolution with ID: %s", knowledge_entry_id)
            except Exception as e:
                logger.warning("Failed to store resolution: %s", e)

        # If error status, set error message
        error_msg = final_state.get("error")
        if status == "error" and not error_msg:
            if final_state.get("attempt", 0) >= self.max_attempts:
                error_msg = f"Max attempts ({self.max_attempts}) exceeded"
            else:
                error_msg = "Unknown error occurred"

        return HealerResult(
            success=success,
            fixed_code=final_state.get("fixed_code", ""),
            fix_description=fix_description,
            attempts=final_state.get("attempt", 0),
            status=status,
            knowledge_entry_id=knowledge_entry_id,
            error=error_msg,
        )

    async def diagnose(
        self,
        error_info: ErrorInfo,
    ) -> dict[str, Any]:
        """Diagnose an error without running the full healing workflow.

        Convenience method to just diagnose the error and query
        for similar past errors.

        Args:
            error_info: ErrorInfo describing the error

        Returns:
            Dictionary with diagnosis results
        """
        from daw_agents.agents.healer.nodes import analyze_error, query_similar_errors

        # Analyze the error
        analysis = await analyze_error(error_info.model_dump())

        # Query for similar errors
        similar_errors = await query_similar_errors(
            error_signature=analysis.get("error_signature", ""),
            error_type=error_info.error_type,
        )

        return {
            "analysis": analysis,
            "similar_errors": similar_errors,
        }
