"""Graph Memory MCP Server implementation.

This module implements an MCP server that exposes Neo4j graph memory operations
as tools. It provides long-term memory storage for agents using a knowledge graph.

The server exposes the following tools:
- memory_store: Store a memory/fact with optional metadata
- memory_query: Execute a Cypher query
- memory_search: Search memories by content
- memory_link: Create relationships between memories
- memory_context: Get context window for a topic

Example usage:
    # Run as standalone server
    $ daw-graph-memory

    # Or programmatically
    from daw_mcp.graph_memory.server import create_server
    server = create_server(neo4j_uri="bolt://localhost:7687")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MemoryNode(BaseModel):
    """Represents a memory node in the graph."""

    id: str
    content: str
    memory_type: str
    created_at: str
    metadata: dict[str, Any] = {}


class Neo4jConnection:
    """Manages Neo4j database connection."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        """Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Database username
            password: Database password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_constraints()

    def _ensure_constraints(self) -> None:
        """Ensure database constraints and indexes exist."""
        with self.driver.session() as session:
            # Create unique constraint on Memory.id
            session.run(
                """
                CREATE CONSTRAINT memory_id IF NOT EXISTS
                FOR (m:Memory) REQUIRE m.id IS UNIQUE
                """
            )
            # Create index on Memory.content for text search
            session.run(
                """
                CREATE INDEX memory_content IF NOT EXISTS
                FOR (m:Memory) ON (m.content)
                """
            )

    def close(self) -> None:
        """Close the database connection."""
        self.driver.close()

    def execute(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query.

        Args:
            query: Cypher query string
            params: Query parameters

        Returns:
            List of result records as dictionaries.
        """
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]


def create_server(
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
) -> FastMCP:
    """Create and configure the Graph Memory MCP server.

    Args:
        neo4j_uri: Neo4j connection URI. Defaults to env var NEO4J_URI.
        neo4j_user: Neo4j username. Defaults to env var NEO4J_USER.
        neo4j_password: Neo4j password. Defaults to env var NEO4J_PASSWORD.

    Returns:
        Configured FastMCP server instance.
    """
    mcp = FastMCP("DAW Graph Memory MCP Server", json_response=True)

    # Get connection details from env or parameters
    uri = neo4j_uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = neo4j_user or os.environ.get("NEO4J_USER", "neo4j")
    password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "password")

    # Connection will be established lazily on first use
    _connection: Neo4jConnection | None = None

    def get_connection() -> Neo4jConnection:
        """Get or create the Neo4j connection."""
        nonlocal _connection
        if _connection is None:
            _connection = Neo4jConnection(uri, user, password)
        return _connection

    @mcp.tool()
    def memory_store(
        content: str,
        memory_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a memory/fact in the knowledge graph.

        Args:
            content: The content of the memory to store.
            memory_type: Type of memory (fact, experience, skill, insight).
            metadata: Optional metadata dictionary.

        Returns:
            Dictionary with the created memory node information.
        """
        conn = get_connection()

        memory_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        query = """
        CREATE (m:Memory {
            id: $id,
            content: $content,
            type: $type,
            created_at: $created_at,
            metadata: $metadata
        })
        RETURN m
        """

        result = conn.execute(
            query,
            {
                "id": memory_id,
                "content": content,
                "type": memory_type,
                "created_at": created_at,
                "metadata": metadata or {},
            },
        )

        if result:
            # Result confirms node was created
            return {
                "success": True,
                "id": memory_id,
                "content": content,
                "type": memory_type,
                "created_at": created_at,
            }
        else:
            return {"success": False, "error": "Failed to create memory"}

    @mcp.tool()
    def memory_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query on the memory graph.

        Args:
            cypher: Cypher query string.
            params: Optional query parameters.

        Returns:
            List of query results.

        Note:
            For security, avoid using this with untrusted input.
            Prefer using the specialized memory tools when possible.
        """
        conn = get_connection()

        try:
            results = conn.execute(cypher, params)
            # Convert Neo4j types to JSON-serializable types
            serializable_results = []
            for record in results:
                serializable_record = {}
                for key, value in record.items():
                    if hasattr(value, "__dict__"):
                        # Convert Neo4j node/relationship to dict
                        serializable_record[key] = dict(value)
                    else:
                        serializable_record[key] = value
                serializable_results.append(serializable_record)
            return serializable_results
        except Exception as e:
            logger.error(f"Query error: {e}")
            return [{"error": str(e)}]

    @mcp.tool()
    def memory_search(
        query: str,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search memories by content.

        Args:
            query: Search query string (substring match).
            memory_type: Optional filter by memory type.
            limit: Maximum number of results (default: 10).

        Returns:
            List of matching memory nodes.
        """
        conn = get_connection()

        if memory_type:
            cypher = """
            MATCH (m:Memory)
            WHERE m.content CONTAINS $query AND m.type = $type
            RETURN m
            ORDER BY m.created_at DESC
            LIMIT $limit
            """
            params = {"query": query, "type": memory_type, "limit": limit}
        else:
            cypher = """
            MATCH (m:Memory)
            WHERE m.content CONTAINS $query
            RETURN m
            ORDER BY m.created_at DESC
            LIMIT $limit
            """
            params = {"query": query, "limit": limit}

        results = conn.execute(cypher, params)

        memories = []
        for record in results:
            node = record["m"]
            memories.append(
                {
                    "id": node.get("id"),
                    "content": node.get("content"),
                    "type": node.get("type"),
                    "created_at": node.get("created_at"),
                    "metadata": node.get("metadata", {}),
                }
            )

        return memories

    @mcp.tool()
    def memory_link(
        source_id: str,
        target_id: str,
        relationship: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a relationship between two memory nodes.

        Args:
            source_id: ID of the source memory node.
            target_id: ID of the target memory node.
            relationship: Type of relationship (e.g., RELATES_TO, DEPENDS_ON).
            properties: Optional properties for the relationship.

        Returns:
            Dictionary with relationship creation result.
        """
        conn = get_connection()

        # Sanitize relationship name (only allow alphanumeric and underscore)
        safe_rel = "".join(c if c.isalnum() or c == "_" else "_" for c in relationship.upper())

        query = f"""
        MATCH (source:Memory {{id: $source_id}})
        MATCH (target:Memory {{id: $target_id}})
        CREATE (source)-[r:{safe_rel} $props]->(target)
        RETURN source.id as source, target.id as target, type(r) as relationship
        """

        try:
            results = conn.execute(
                query,
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "props": properties or {},
                },
            )

            if results:
                return {
                    "success": True,
                    "source": source_id,
                    "target": target_id,
                    "relationship": safe_rel,
                }
            else:
                return {
                    "success": False,
                    "error": "Could not find source or target memory",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def memory_context(
        topic: str,
        depth: int = 2,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get context window for a topic - related memories within N hops.

        Args:
            topic: Topic to search for (substring match on content).
            depth: How many relationship hops to traverse (default: 2).
            limit: Maximum total nodes to return (default: 20).

        Returns:
            Dictionary with central nodes and their connections.
        """
        conn = get_connection()

        # Find central nodes matching the topic
        central_query = """
        MATCH (m:Memory)
        WHERE m.content CONTAINS $topic
        RETURN m
        LIMIT 5
        """

        central_results = conn.execute(central_query, {"topic": topic})

        if not central_results:
            return {"central": [], "related": [], "relationships": []}

        # Get IDs of central nodes
        central_ids = [r["m"].get("id") for r in central_results]

        # Find related nodes within depth
        related_query = """
        MATCH (central:Memory)
        WHERE central.id IN $central_ids
        CALL {
            WITH central
            MATCH path = (central)-[*1..$depth]-(related:Memory)
            RETURN DISTINCT related, relationships(path) as rels
            LIMIT $limit
        }
        RETURN DISTINCT related, rels
        """

        try:
            related_results = conn.execute(
                related_query,
                {"central_ids": central_ids, "depth": depth, "limit": limit},
            )
        except Exception:
            # Fallback for older Neo4j versions
            related_results = []

        # Build response
        central_nodes = []
        for r in central_results:
            node = r["m"]
            central_nodes.append(
                {
                    "id": node.get("id"),
                    "content": node.get("content"),
                    "type": node.get("type"),
                }
            )

        related_nodes = []
        relationships = []
        seen_ids = set(central_ids)

        for r in related_results:
            node = r.get("related")
            if node and node.get("id") not in seen_ids:
                seen_ids.add(node.get("id"))
                related_nodes.append(
                    {
                        "id": node.get("id"),
                        "content": node.get("content"),
                        "type": node.get("type"),
                    }
                )

            rels = r.get("rels", [])
            for rel in rels:
                if hasattr(rel, "type"):
                    relationships.append(
                        {
                            "type": rel.type,
                            "start": rel.start_node.get("id") if hasattr(rel, "start_node") else None,
                            "end": rel.end_node.get("id") if hasattr(rel, "end_node") else None,
                        }
                    )

        return {
            "central": central_nodes,
            "related": related_nodes,
            "relationships": relationships,
        }

    @mcp.tool()
    def memory_delete(memory_id: str) -> dict[str, Any]:
        """Delete a memory node and its relationships.

        Args:
            memory_id: ID of the memory to delete.

        Returns:
            Dictionary with deletion result.
        """
        conn = get_connection()

        query = """
        MATCH (m:Memory {id: $id})
        DETACH DELETE m
        RETURN count(*) as deleted
        """

        result = conn.execute(query, {"id": memory_id})

        if result and result[0].get("deleted", 0) > 0:
            return {"success": True, "deleted_id": memory_id}
        else:
            return {"success": False, "error": f"Memory {memory_id} not found"}

    return mcp


def main() -> None:
    """Run the Graph Memory MCP server."""
    # Get connection details from environment
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "password")

    logger.info(f"Starting Graph Memory MCP server with Neo4j at {neo4j_uri}")

    server = create_server(neo4j_uri, neo4j_user, neo4j_password)

    # Run with stdio transport (default for CLI tools)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
