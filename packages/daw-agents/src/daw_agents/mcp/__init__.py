"""MCP (Model Context Protocol) module for DAW.

This module provides:
- MCPClient: Client for interacting with MCP servers
- MCPClientManager: Manages multiple MCP server connections
- MCPGateway: OAuth 2.1 + RFC 8707 authorization gateway

Exports:
    Client:
        - MCPClient: MCP client for tool discovery and execution
        - MCPClientManager: Multi-server connection management
        - MCPTool: Tool model
        - MCPToolResult: Tool execution result

    Gateway:
        - MCPGateway: Authorization gateway
        - MCPGatewayConfig: Gateway configuration
        - AgentScope: Per-agent scope definition
        - ScopedToken: Issued token with scopes
        - ToolCallResult: Tool call validation result
        - SessionType: Session type enum
        - AGENT_SCOPES: Predefined agent scopes
        - Exception classes
"""

from daw_agents.mcp.client import (
    MCPClient,
    MCPClientManager,
    MCPTool,
    MCPToolResult,
)
from daw_agents.mcp.gateway import (
    AGENT_SCOPES,
    AgentScope,
    GatewayAuthError,
    InsufficientScopeError,
    InvalidAudienceError,
    InvalidRefreshTokenError,
    InvalidResourceError,
    InvalidTokenError,
    MCPGateway,
    MCPGatewayConfig,
    ScopedToken,
    SessionType,
    TokenExpiredError,
    TokenRevokedError,
    ToolCallResult,
    UnauthorizedAgentError,
)

__all__ = [
    # Client
    "MCPClient",
    "MCPClientManager",
    "MCPTool",
    "MCPToolResult",
    # Gateway
    "MCPGateway",
    "MCPGatewayConfig",
    "AgentScope",
    "ScopedToken",
    "ToolCallResult",
    "SessionType",
    "AGENT_SCOPES",
    # Exceptions
    "GatewayAuthError",
    "UnauthorizedAgentError",
    "InsufficientScopeError",
    "TokenExpiredError",
    "TokenRevokedError",
    "InvalidTokenError",
    "InvalidRefreshTokenError",
    "InvalidAudienceError",
    "InvalidResourceError",
]
