"""Git MCP Server module.

This module provides an MCP server that exposes Git operations as tools:
- git_status: Get repository status
- git_log: View commit history
- git_diff: Show changes between commits
- git_commit: Create a new commit
- git_branch: List or create branches
- git_checkout: Switch branches

The server uses GitPython for Git operations and follows MCP protocol
for tool discovery and execution.
"""

from daw_mcp.git_mcp.server import create_server, main

__all__ = ["create_server", "main"]
