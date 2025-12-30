"""MCP Gateway Authorization with OAuth 2.1 and RFC 8707 Resource Indicators.

This module implements MCP Gateway Authorization following OAuth 2.1 specification
and RFC 8707 Resource Indicators for secure agent-to-tool communication.

Key Features:
- Per-agent scoped tokens (e.g., database agent: SELECT only, no DDL)
- Token TTL: 15 minutes for automated sessions, 1 hour for interactive
- Token refresh and revocation mechanisms
- RFC 8707 Resource Indicators support
- Validates all tool calls against agent's granted scopes

References:
    - OAuth 2.1: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13
    - RFC 8707: https://www.rfc-editor.org/rfc/rfc8707.html
    - MCP Authorization: https://modelcontextprotocol.io/specification/draft/basic/authorization
    - PRD FR-01.3.1: MCP Gateway Authorization requirements

Example usage:
    config = MCPGatewayConfig(
        issuer="https://daw.example.com",
        audience="https://mcp.daw.example.com",
        secret_key="your-secret-key",
    )

    gateway = MCPGateway(config=config)

    # Issue a token for an agent
    token = await gateway.authorize_agent(
        agent_id="planner",
        requested_scopes=["search", "read_file"],
    )

    # Validate a tool call
    result = await gateway.validate_tool_call(
        token=token.token_string,
        tool_name="search",
        params={"query": "test"},
    )
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import jwt
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class SessionType(str, Enum):
    """Session type determines token TTL.

    AUTOMATED: 15-minute TTL for agent-to-agent automated workflows
    INTERACTIVE: 1-hour TTL for human-interactive sessions
    """

    AUTOMATED = "automated"
    INTERACTIVE = "interactive"


# -----------------------------------------------------------------------------
# Exception Classes
# -----------------------------------------------------------------------------


class GatewayAuthError(Exception):
    """Base exception for gateway authorization errors."""

    pass


class UnauthorizedAgentError(GatewayAuthError):
    """Raised when an unknown agent attempts to authorize."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Unauthorized agent: {agent_id}")


class InsufficientScopeError(GatewayAuthError):
    """Raised when a tool call requires a scope the token doesn't have."""

    def __init__(self, tool_name: str, required_scope: str | None = None) -> None:
        self.tool_name = tool_name
        self.required_scope = required_scope
        msg = f"Insufficient scope for tool: {tool_name}"
        if required_scope:
            msg += f" (requires: {required_scope})"
        super().__init__(msg)


class TokenExpiredError(GatewayAuthError):
    """Raised when a token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)


class TokenRevokedError(GatewayAuthError):
    """Raised when a token has been revoked."""

    def __init__(self, token_id: str) -> None:
        self.token_id = token_id
        super().__init__(f"Token has been revoked: {token_id}")


class InvalidTokenError(GatewayAuthError):
    """Raised when a token is invalid (malformed, bad signature, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidRefreshTokenError(GatewayAuthError):
    """Raised when a refresh token is invalid or not found."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidAudienceError(GatewayAuthError):
    """Raised when token audience doesn't match expected audience."""

    def __init__(self, audience: str) -> None:
        self.audience = audience
        super().__init__(f"Invalid audience: {audience}")


class InvalidResourceError(GatewayAuthError):
    """Raised when token resource indicator doesn't match expected resource."""

    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"Invalid resource: {resource}")


# -----------------------------------------------------------------------------
# Predefined Agent Scopes
# -----------------------------------------------------------------------------

# Per PRD FR-01.3.1: Per-agent scoped tokens
AGENT_SCOPES: dict[str, list[str]] = {
    "planner": ["search", "read_file", "query_db:SELECT"],
    "executor": ["read_file", "write_file", "git_commit"],
    "validator": ["run_tests", "security_scan", "lint"],
    "healer": ["read_file", "write_file:patches"],
}


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------


class MCPGatewayConfig(BaseModel):
    """Configuration for MCP Gateway Authorization.

    Attributes:
        issuer: The issuer identifier (iss claim in JWT)
        audience: The intended audience (aud claim in JWT)
        secret_key: Secret key for signing tokens (HS256)
        algorithm: JWT algorithm (default HS256)
        automated_ttl_minutes: TTL for automated sessions (default 15)
        interactive_ttl_minutes: TTL for interactive sessions (default 60)
        resource_uri: RFC 8707 resource URI (optional)
    """

    issuer: str
    audience: str
    secret_key: str
    algorithm: str = Field(default="HS256")
    automated_ttl_minutes: int = Field(default=15)
    interactive_ttl_minutes: int = Field(default=60)
    resource_uri: str | None = Field(default=None)


class AgentScope(BaseModel):
    """Per-agent scope definition.

    Attributes:
        agent_id: Unique identifier for the agent
        scopes: List of allowed scopes (may include parametric scopes like query_db:SELECT)
    """

    agent_id: str
    scopes: list[str]

    def has_scope(self, scope: str) -> bool:
        """Check if this agent has the specified scope.

        Args:
            scope: The scope to check (e.g., "search", "query_db:SELECT")

        Returns:
            True if the scope is allowed, False otherwise

        Note:
            Parametric scopes must match exactly. For example:
            - "query_db:SELECT" matches "query_db:SELECT"
            - "query_db:SELECT" does NOT match "query_db" or "query_db:DROP"
        """
        return scope in self.scopes


class ScopedToken(BaseModel):
    """Represents an issued scoped token.

    Attributes:
        token_id: Unique identifier for this token (jti claim)
        agent_id: The agent this token was issued to
        scopes: List of granted scopes
        issued_at: When the token was issued
        expires_at: When the token expires
        token_string: The actual JWT string
        refresh_token: Optional refresh token for token renewal
        resource: RFC 8707 resource indicator (optional)
        session_type: Type of session (automated/interactive)
    """

    token_id: str
    agent_id: str
    scopes: list[str]
    issued_at: datetime
    expires_at: datetime
    token_string: str
    refresh_token: str | None = Field(default=None)
    resource: str | None = Field(default=None)
    session_type: SessionType = Field(default=SessionType.AUTOMATED)

    def is_expired(self) -> bool:
        """Check if this token has expired.

        Returns:
            True if the token has expired, False otherwise
        """
        return datetime.now(tz=UTC) > self.expires_at


class ToolCallResult(BaseModel):
    """Result of a tool call validation.

    Attributes:
        allowed: Whether the tool call is allowed
        tool_name: Name of the tool being called
        scope_match: The scope that matched (if allowed)
        agent_id: The agent attempting the call
        error: Error message (if not allowed)
    """

    allowed: bool
    tool_name: str
    scope_match: str | None = Field(default=None)
    agent_id: str
    error: str | None = Field(default=None)


# -----------------------------------------------------------------------------
# MCP Gateway
# -----------------------------------------------------------------------------


class MCPGateway:
    """MCP Gateway for OAuth 2.1 + RFC 8707 authorization.

    This gateway handles:
    - Agent authorization with scoped tokens
    - Token validation
    - Tool call authorization
    - Token refresh and revocation

    Attributes:
        config: Gateway configuration
        agent_scopes: Mapping of agent IDs to allowed scopes
    """

    def __init__(
        self,
        config: MCPGatewayConfig,
        agent_scopes: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the MCP Gateway.

        Args:
            config: Gateway configuration
            agent_scopes: Optional custom agent scopes (defaults to AGENT_SCOPES)
        """
        self.config = config
        self.agent_scopes = {**AGENT_SCOPES}
        if agent_scopes:
            self.agent_scopes.update(agent_scopes)

        # Token revocation tracking (in production, use Redis/database)
        self._revoked_tokens: set[str] = set()
        self._revoked_refresh_tokens: set[str] = set()

        # Refresh token to token info mapping (in production, use database)
        self._refresh_token_map: dict[str, dict[str, Any]] = {}

        logger.debug("Initialized MCP Gateway with issuer: %s", config.issuer)

    async def authorize_agent(
        self,
        agent_id: str,
        requested_scopes: list[str],
        session_type: SessionType = SessionType.AUTOMATED,
        with_refresh_token: bool = False,
    ) -> ScopedToken:
        """Issue a scoped token for an agent.

        Args:
            agent_id: The agent requesting authorization
            requested_scopes: List of scopes the agent is requesting
            session_type: Type of session (affects TTL)
            with_refresh_token: Whether to include a refresh token

        Returns:
            ScopedToken with the issued JWT

        Raises:
            UnauthorizedAgentError: If the agent is not recognized
        """
        # Check if agent is known
        if agent_id not in self.agent_scopes:
            logger.warning("Unauthorized agent attempted authorization: %s", agent_id)
            raise UnauthorizedAgentError(agent_id)

        # Filter requested scopes to only allowed ones
        allowed_scopes = self.agent_scopes[agent_id]
        granted_scopes = [s for s in requested_scopes if s in allowed_scopes]

        # Calculate expiration based on session type
        now = datetime.now(tz=UTC)
        if session_type == SessionType.AUTOMATED:
            ttl_minutes = self.config.automated_ttl_minutes
        else:
            ttl_minutes = self.config.interactive_ttl_minutes

        expires_at = now + timedelta(minutes=ttl_minutes)

        # Generate unique token ID
        token_id = f"tok_{uuid.uuid4().hex}"

        # Build JWT claims
        claims: dict[str, Any] = {
            "iss": self.config.issuer,
            "sub": agent_id,
            "aud": self.config.audience,
            "exp": expires_at,
            "iat": now,
            "jti": token_id,
            "scope": " ".join(granted_scopes),  # Space-separated per OAuth 2.1
        }

        # Add RFC 8707 resource indicator if configured
        if self.config.resource_uri:
            claims["resource"] = self.config.resource_uri

        # Encode the JWT
        token_string = jwt.encode(
            claims,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

        # Generate refresh token if requested
        refresh_token: str | None = None
        if with_refresh_token:
            refresh_token = f"ref_{secrets.token_urlsafe(32)}"
            # Store refresh token mapping
            self._refresh_token_map[refresh_token] = {
                "token_id": token_id,
                "agent_id": agent_id,
                "scopes": granted_scopes,
                "session_type": session_type,
            }

        logger.info(
            "Issued token for agent %s with scopes: %s (TTL: %d min)",
            agent_id,
            granted_scopes,
            ttl_minutes,
        )

        return ScopedToken(
            token_id=token_id,
            agent_id=agent_id,
            scopes=granted_scopes,
            issued_at=now,
            expires_at=expires_at,
            token_string=token_string,
            refresh_token=refresh_token,
            resource=self.config.resource_uri,
            session_type=session_type,
        )

    async def validate_token(
        self,
        token_string: str,
        expected_resource: str | None = None,
    ) -> ScopedToken:
        """Validate a token and return its information.

        Args:
            token_string: The JWT token string
            expected_resource: Optional RFC 8707 resource to validate against

        Returns:
            ScopedToken with validated token information

        Raises:
            TokenExpiredError: If the token has expired
            InvalidTokenError: If the token is malformed or has invalid signature
            InvalidAudienceError: If the audience doesn't match
            InvalidResourceError: If the resource doesn't match expected
            TokenRevokedError: If the token has been revoked
        """
        try:
            # Decode and verify the token
            payload = jwt.decode(
                token_string,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["exp", "iat", "sub", "jti", "aud", "iss"],
                },
            )

            token_id = payload["jti"]

            # Check if token is revoked
            if token_id in self._revoked_tokens:
                raise TokenRevokedError(token_id)

            # Parse scopes from space-separated string
            scope_string = payload.get("scope", "")
            scopes = scope_string.split() if scope_string else []

            # Validate resource indicator if expected
            if expected_resource:
                token_resource = payload.get("resource")
                if token_resource != expected_resource:
                    raise InvalidResourceError(expected_resource)

            # Reconstruct ScopedToken
            issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
            expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

            return ScopedToken(
                token_id=token_id,
                agent_id=payload["sub"],
                scopes=scopes,
                issued_at=issued_at,
                expires_at=expires_at,
                token_string=token_string,
                resource=payload.get("resource"),
            )

        except jwt.ExpiredSignatureError as e:
            logger.warning("Token validation failed: expired")
            raise TokenExpiredError("Token has expired") from e
        except jwt.InvalidAudienceError as e:
            logger.warning("Token validation failed: invalid audience")
            raise InvalidAudienceError(str(e)) from e
        except jwt.InvalidSignatureError as e:
            logger.warning("Token validation failed: invalid signature")
            raise InvalidTokenError("Invalid token signature") from e
        except jwt.DecodeError as e:
            logger.warning("Token validation failed: decode error")
            raise InvalidTokenError(f"Failed to decode token: {e}") from e
        except jwt.InvalidTokenError as e:
            logger.warning("Token validation failed: %s", str(e))
            raise InvalidTokenError(str(e)) from e

    async def validate_tool_call(
        self,
        token: str,
        tool_name: str,
        params: dict[str, Any],
    ) -> ToolCallResult:
        """Validate a tool call against the token's scopes.

        Args:
            token: The JWT token string
            tool_name: Name of the tool being called
            params: Parameters being passed to the tool

        Returns:
            ToolCallResult indicating whether the call is allowed

        Raises:
            TokenExpiredError: If the token has expired
            InvalidTokenError: If the token is invalid
            InsufficientScopeError: If the token lacks required scope
        """
        # First validate the token
        validated_token = await self.validate_token(token)

        # Check if tool_name matches any granted scope
        scope_match = self._find_matching_scope(
            tool_name, params, validated_token.scopes
        )

        if scope_match:
            return ToolCallResult(
                allowed=True,
                tool_name=tool_name,
                scope_match=scope_match,
                agent_id=validated_token.agent_id,
            )

        # No matching scope found
        logger.warning(
            "Tool call denied: agent=%s, tool=%s, scopes=%s",
            validated_token.agent_id,
            tool_name,
            validated_token.scopes,
        )
        raise InsufficientScopeError(tool_name)

    def _find_matching_scope(
        self,
        tool_name: str,
        params: dict[str, Any],
        scopes: list[str],
    ) -> str | None:
        """Find a scope that matches the tool call.

        Handles both simple scopes (e.g., "search") and parametric scopes
        (e.g., "query_db:SELECT").

        Args:
            tool_name: Name of the tool being called
            params: Parameters being passed to the tool
            scopes: List of granted scopes

        Returns:
            The matching scope, or None if no match found
        """
        # Check for exact tool name match
        if tool_name in scopes:
            return tool_name

        # Check for parametric scopes
        for scope in scopes:
            if ":" in scope:
                scope_tool, scope_param = scope.split(":", 1)
                if scope_tool == tool_name:
                    # Check if the operation matches the scope parameter
                    if self._operation_matches_scope(params, scope_param):
                        return scope

        return None

    def _operation_matches_scope(
        self,
        params: dict[str, Any],
        scope_param: str,
    ) -> bool:
        """Check if an operation matches a parametric scope.

        For query_db scopes, checks if the query operation matches.
        For write_file scopes, checks file path restrictions.

        Args:
            params: Tool call parameters
            scope_param: The scope parameter (e.g., "SELECT", "patches")

        Returns:
            True if the operation is allowed by the scope
        """
        # Handle query_db:SELECT type scopes
        if "query" in params:
            query = str(params["query"]).strip().upper()
            # Check if the query starts with the allowed operation
            if query.startswith(scope_param.upper()):
                return True
            # Also check for prohibited operations
            prohibited_ops = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE"]
            for op in prohibited_ops:
                if query.startswith(op) and scope_param.upper() != op:
                    return False
            return False

        # Handle write_file:patches type scopes
        if "path" in params and scope_param == "patches":
            path = str(params.get("path", ""))
            # Only allow patch-related paths
            if "/patches/" in path or path.endswith(".patch"):
                return True
            return False

        # Default: allow if no specific checks apply
        return True

    async def refresh_token(self, refresh_token_string: str) -> ScopedToken:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token_string: The refresh token string

        Returns:
            New ScopedToken with extended lifetime

        Raises:
            InvalidRefreshTokenError: If the refresh token is invalid or revoked
        """
        # Check if refresh token exists and is valid
        if refresh_token_string not in self._refresh_token_map:
            raise InvalidRefreshTokenError("Refresh token not found")

        if refresh_token_string in self._revoked_refresh_tokens:
            raise InvalidRefreshTokenError("Refresh token has been revoked")

        # Get stored token info
        token_info = self._refresh_token_map[refresh_token_string]

        # Check if the original token was revoked
        token_id = token_info["token_id"]
        if token_id in self._revoked_tokens:
            raise InvalidRefreshTokenError("Original token has been revoked")

        # Issue a new token with the same scopes
        new_token = await self.authorize_agent(
            agent_id=token_info["agent_id"],
            requested_scopes=token_info["scopes"],
            session_type=token_info["session_type"],
            with_refresh_token=True,
        )

        # Invalidate the old refresh token
        del self._refresh_token_map[refresh_token_string]

        logger.info(
            "Refreshed token for agent %s",
            token_info["agent_id"],
        )

        return new_token

    async def revoke_token(self, token_string: str) -> bool:
        """Revoke a token, making it immediately invalid.

        Args:
            token_string: The JWT token string to revoke

        Returns:
            True if revocation was successful
        """
        try:
            # Decode without verification to get the token ID
            payload = jwt.decode(
                token_string,
                options={"verify_signature": False},
            )
            token_id = payload.get("jti")

            if token_id:
                self._revoked_tokens.add(token_id)
                logger.info("Revoked token: %s", token_id)

                # Also revoke any associated refresh tokens
                for refresh_token, info in list(self._refresh_token_map.items()):
                    if info.get("token_id") == token_id:
                        self._revoked_refresh_tokens.add(refresh_token)
                        del self._refresh_token_map[refresh_token]

            return True

        except jwt.DecodeError:
            logger.warning("Failed to decode token for revocation")
            return True  # Idempotent - treat as already revoked
