"""DAW Custom MCP Servers.

This package provides custom MCP (Model Context Protocol) servers for the
Deterministic Agentic Workbench:

- git_mcp: Git operations MCP server for version control operations
- graph_memory: Neo4j-backed MCP server for knowledge graph memory operations

Each server implements the MCP protocol and can be used with any MCP-compatible
client.

Example usage:
    # Start the Git MCP server
    $ daw-git-mcp

    # Start the Graph Memory MCP server
    $ daw-graph-memory

The servers expose tools that can be discovered and called by MCP clients.
"""

__version__ = "0.1.0"
