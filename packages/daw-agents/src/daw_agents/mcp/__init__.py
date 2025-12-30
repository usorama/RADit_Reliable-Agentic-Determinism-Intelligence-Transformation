"""MCP (Model Context Protocol) module for DAW.

This module provides:
- MCPClient: Client for interacting with MCP servers
- MCPClientManager: Manages multiple MCP server connections
- MCPGateway: OAuth 2.1 + RFC 8707 authorization gateway
- ContentShield: AI Prompt Shields for content injection prevention
- RBACPolicy: Role-Based Access Control for MCP tools
- AuditLogger: SOC 2/ISO 27001 compliant audit logging with hash-chaining

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

    Shields:
        - ContentShield: Content injection prevention
        - ShieldConfig: Shield configuration
        - ShieldedGateway: Gateway with content shields
        - DangerousPattern: Pattern categories
        - ValidationResult: Validation result model
        - Exception classes

    RBAC:
        - Role: Agent role enum (PLANNER, EXECUTOR, VALIDATOR, HEALER)
        - Permission: Tool permission model
        - PermissionContext: Context for permission checks
        - PermissionResult: Result of permission check
        - RolePolicy: Policy for a single role
        - RBACPolicy: Main RBAC policy manager
        - get_default_policy_path: Get default policies.yaml path
        - Exception classes

    Audit:
        - AuditConfig: Audit logging configuration
        - AuditEntry: Audit log entry model
        - AuditLogger: Main audit logging class
        - ResultStatus: Result status enum
        - compute_entry_hash: Hash computation for tamper resistance
        - verify_chain_integrity: Chain integrity verification
"""

from daw_agents.mcp.audit import (
    AuditConfig,
    AuditEntry,
    AuditLogger,
    ResultStatus,
    compute_entry_hash,
    verify_chain_integrity,
)
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
from daw_agents.mcp.rbac import (
    Permission,
    PermissionContext,
    PermissionDeniedError,
    PermissionResult,
    PolicyParseError,
    RBACError,
    RBACPolicy,
    Role,
    RoleNotFoundError,
    RolePolicy,
    get_default_policy_path,
)
from daw_agents.mcp.shields import (
    ContentBlockedError,
    ContentShield,
    DangerousPattern,
    SchemaValidationError,
    ShieldConfig,
    ShieldedGateway,
    ShieldError,
    ValidationResult,
    get_pattern_regex,
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
    # Gateway Exceptions
    "GatewayAuthError",
    "UnauthorizedAgentError",
    "InsufficientScopeError",
    "TokenExpiredError",
    "TokenRevokedError",
    "InvalidTokenError",
    "InvalidRefreshTokenError",
    "InvalidAudienceError",
    "InvalidResourceError",
    # Shields
    "ContentShield",
    "ShieldConfig",
    "ShieldedGateway",
    "DangerousPattern",
    "ValidationResult",
    "get_pattern_regex",
    # Shield Exceptions
    "ShieldError",
    "ContentBlockedError",
    "SchemaValidationError",
    # RBAC
    "Role",
    "Permission",
    "PermissionContext",
    "PermissionResult",
    "RolePolicy",
    "RBACPolicy",
    "get_default_policy_path",
    # RBAC Exceptions
    "RBACError",
    "PolicyParseError",
    "PermissionDeniedError",
    "RoleNotFoundError",
    # Audit
    "AuditConfig",
    "AuditEntry",
    "AuditLogger",
    "ResultStatus",
    "compute_entry_hash",
    "verify_chain_integrity",
]
