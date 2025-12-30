"""Graph Memory MCP Server module.

This module provides an MCP server that exposes Neo4j graph operations as tools:
- memory_store: Store a memory/fact in the knowledge graph
- memory_query: Query memories using Cypher
- memory_search: Semantic search through memories
- memory_link: Create relationships between memories
- memory_context: Get context window for a topic

The server connects to Neo4j and follows MCP protocol for tool discovery
and execution. Designed for long-term agent memory storage.
"""

from daw_mcp.graph_memory.server import create_server, main

__all__ = ["create_server", "main"]
