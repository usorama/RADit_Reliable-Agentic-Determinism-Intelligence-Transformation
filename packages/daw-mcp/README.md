# DAW MCP Servers

Custom MCP (Model Context Protocol) servers for the Deterministic Agentic Workbench.

## Overview

This package provides MCP servers that expose tools for:

- **Git operations** (`git_mcp`): Version control operations like status, commit, branch, etc.
- **Graph memory** (`graph_memory`): Neo4j-backed knowledge graph for agent memory storage

## Installation

```bash
cd packages/daw-mcp
poetry install
```

## Usage

### Git MCP Server

Start the Git MCP server:

```bash
# Using the CLI entry point
daw-git-mcp /path/to/repository

# Or via environment variable
GIT_MCP_REPO_PATH=/path/to/repo daw-git-mcp
```

Available tools:
- `git_status` - Get repository status
- `git_log` - View commit history
- `git_diff` - Show changes
- `git_commit` - Create commits
- `git_branch_list` - List branches
- `git_checkout` - Switch branches

### Graph Memory MCP Server

Start the Graph Memory MCP server:

```bash
# Set Neo4j connection via environment
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password

daw-graph-memory
```

Available tools:
- `memory_store` - Store a memory/fact
- `memory_query` - Execute Cypher queries
- `memory_search` - Search memories by content
- `memory_link` - Create relationships
- `memory_context` - Get context window for a topic
- `memory_delete` - Delete a memory

## Development

Run tests:

```bash
poetry run pytest
```

Run type checking:

```bash
poetry run mypy src/
```

Run linting:

```bash
poetry run ruff check src/
```

## Architecture

The servers use the official MCP Python SDK with FastMCP for easy tool definition:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My Server")

@mcp.tool()
def my_tool(param: str) -> dict:
    """Tool description."""
    return {"result": param}

mcp.run(transport="stdio")
```

## License

MIT
