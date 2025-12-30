"""Comprehensive tests for MCP Gateway Authorization (OAuth 2.1 + RFC 8707).

This module tests the MCP Gateway Authorization implementation following
OAuth 2.1 specification and RFC 8707 Resource Indicators.

Tests cover:
1. MCPGatewayConfig - Gateway configuration
2. AgentScope - Per-agent scope definitions
3. ScopedToken - Token with scopes, TTL, refresh capability
4. MCPGateway - Main gateway class with authorization methods
5. Token lifecycle (issue, validate, refresh, revoke)
6. Scope enforcement on tool calls
7. RFC 8707 Resource Indicators support

References:
    - OAuth 2.1: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13
    - RFC 8707: https://www.rfc-editor.org/rfc/rfc8707.html
    - MCP Authorization: https://modelcontextprotocol.io/specification/draft/basic/authorization
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Test: MCPGatewayConfig Model
# -----------------------------------------------------------------------------


class TestMCPGatewayConfig:
    """Tests for the MCPGatewayConfig Pydantic model."""

    def test_gateway_config_creation(self) -> None:
        """MCPGatewayConfig should be creatable with required fields."""
        from daw_agents.mcp.gateway import MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-for-signing",
        )

        assert config.issuer == "https://daw.example.com"
        assert config.audience == "https://mcp.daw.example.com"
        assert config.secret_key == "super-secret-key-for-signing"

    def test_gateway_config_default_ttls(self) -> None:
        """MCPGatewayConfig should have default TTLs per session type."""
        from daw_agents.mcp.gateway import MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="secret",
        )

        # Per PRD: 15 min for automated, 1 hour for interactive
        assert config.automated_ttl_minutes == 15
        assert config.interactive_ttl_minutes == 60

    def test_gateway_config_custom_ttls(self) -> None:
        """MCPGatewayConfig should allow custom TTL configuration."""
        from daw_agents.mcp.gateway import MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="secret",
            automated_ttl_minutes=10,
            interactive_ttl_minutes=120,
        )

        assert config.automated_ttl_minutes == 10
        assert config.interactive_ttl_minutes == 120

    def test_gateway_config_with_resource_uri(self) -> None:
        """MCPGatewayConfig should support RFC 8707 resource URI."""
        from daw_agents.mcp.gateway import MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="secret",
            resource_uri="https://mcp.daw.example.com/api",
        )

        assert config.resource_uri == "https://mcp.daw.example.com/api"

    def test_gateway_config_algorithm(self) -> None:
        """MCPGatewayConfig should use HS256 by default with option for RS256."""
        from daw_agents.mcp.gateway import MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="secret",
        )

        assert config.algorithm == "HS256"


# -----------------------------------------------------------------------------
# Test: AgentScope Model
# -----------------------------------------------------------------------------


class TestAgentScope:
    """Tests for the AgentScope model defining per-agent permissions."""

    def test_agent_scope_creation(self) -> None:
        """AgentScope should be creatable with agent ID and scopes."""
        from daw_agents.mcp.gateway import AgentScope

        scope = AgentScope(
            agent_id="planner",
            scopes=["search", "read_file", "query_db:SELECT"],
        )

        assert scope.agent_id == "planner"
        assert "search" in scope.scopes
        assert "read_file" in scope.scopes
        assert "query_db:SELECT" in scope.scopes

    def test_agent_scope_predefined_planner(self) -> None:
        """AgentScope should have predefined planner scopes."""
        from daw_agents.mcp.gateway import AGENT_SCOPES

        assert "planner" in AGENT_SCOPES
        planner_scopes = AGENT_SCOPES["planner"]
        assert "search" in planner_scopes
        assert "read_file" in planner_scopes
        assert "query_db:SELECT" in planner_scopes

    def test_agent_scope_predefined_executor(self) -> None:
        """AgentScope should have predefined executor scopes."""
        from daw_agents.mcp.gateway import AGENT_SCOPES

        assert "executor" in AGENT_SCOPES
        executor_scopes = AGENT_SCOPES["executor"]
        assert "read_file" in executor_scopes
        assert "write_file" in executor_scopes
        assert "git_commit" in executor_scopes

    def test_agent_scope_predefined_validator(self) -> None:
        """AgentScope should have predefined validator scopes."""
        from daw_agents.mcp.gateway import AGENT_SCOPES

        assert "validator" in AGENT_SCOPES
        validator_scopes = AGENT_SCOPES["validator"]
        assert "run_tests" in validator_scopes
        assert "security_scan" in validator_scopes
        assert "lint" in validator_scopes

    def test_agent_scope_predefined_healer(self) -> None:
        """AgentScope should have predefined healer scopes."""
        from daw_agents.mcp.gateway import AGENT_SCOPES

        assert "healer" in AGENT_SCOPES
        healer_scopes = AGENT_SCOPES["healer"]
        assert "read_file" in healer_scopes
        assert "write_file:patches" in healer_scopes

    def test_agent_scope_has_scope(self) -> None:
        """AgentScope.has_scope should check if scope is permitted."""
        from daw_agents.mcp.gateway import AgentScope

        scope = AgentScope(
            agent_id="planner",
            scopes=["search", "read_file", "query_db:SELECT"],
        )

        assert scope.has_scope("search") is True
        assert scope.has_scope("read_file") is True
        assert scope.has_scope("write_file") is False
        assert scope.has_scope("git_commit") is False

    def test_agent_scope_parametric_check(self) -> None:
        """AgentScope should handle parametric scopes like query_db:SELECT."""
        from daw_agents.mcp.gateway import AgentScope

        scope = AgentScope(
            agent_id="planner",
            scopes=["query_db:SELECT"],
        )

        # Exact match
        assert scope.has_scope("query_db:SELECT") is True
        # DDL not allowed
        assert scope.has_scope("query_db:DROP") is False
        # Full access not allowed
        assert scope.has_scope("query_db") is False


# -----------------------------------------------------------------------------
# Test: ScopedToken Model
# -----------------------------------------------------------------------------


class TestScopedToken:
    """Tests for the ScopedToken model representing an issued token."""

    def test_scoped_token_creation(self) -> None:
        """ScopedToken should be creatable with all required fields."""
        from daw_agents.mcp.gateway import ScopedToken

        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(minutes=15)

        token = ScopedToken(
            token_id="token_123",
            agent_id="planner",
            scopes=["search", "read_file"],
            issued_at=now,
            expires_at=expires_at,
            token_string="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        )

        assert token.token_id == "token_123"
        assert token.agent_id == "planner"
        assert "search" in token.scopes
        assert token.issued_at == now
        assert token.expires_at == expires_at
        assert token.token_string.startswith("eyJ")

    def test_scoped_token_is_expired(self) -> None:
        """ScopedToken.is_expired should correctly check expiration."""
        from daw_agents.mcp.gateway import ScopedToken

        now = datetime.now(tz=UTC)

        # Active token
        active_token = ScopedToken(
            token_id="token_active",
            agent_id="planner",
            scopes=["search"],
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            token_string="active_token",
        )
        assert active_token.is_expired() is False

        # Expired token
        expired_token = ScopedToken(
            token_id="token_expired",
            agent_id="planner",
            scopes=["search"],
            issued_at=now - timedelta(minutes=30),
            expires_at=now - timedelta(minutes=15),
            token_string="expired_token",
        )
        assert expired_token.is_expired() is True

    def test_scoped_token_resource_indicator(self) -> None:
        """ScopedToken should support RFC 8707 resource indicator."""
        from daw_agents.mcp.gateway import ScopedToken

        now = datetime.now(tz=UTC)

        token = ScopedToken(
            token_id="token_with_resource",
            agent_id="executor",
            scopes=["write_file"],
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            token_string="token_string",
            resource="https://mcp.daw.example.com",
        )

        assert token.resource == "https://mcp.daw.example.com"

    def test_scoped_token_refresh_capability(self) -> None:
        """ScopedToken should have refresh_token field when refreshable."""
        from daw_agents.mcp.gateway import ScopedToken

        now = datetime.now(tz=UTC)

        token = ScopedToken(
            token_id="token_refreshable",
            agent_id="planner",
            scopes=["search"],
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            token_string="access_token",
            refresh_token="refresh_token_123",
        )

        assert token.refresh_token == "refresh_token_123"

    def test_scoped_token_session_type(self) -> None:
        """ScopedToken should track session type (automated/interactive)."""
        from daw_agents.mcp.gateway import ScopedToken, SessionType

        now = datetime.now(tz=UTC)

        automated_token = ScopedToken(
            token_id="token_automated",
            agent_id="executor",
            scopes=["write_file"],
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            token_string="auto_token",
            session_type=SessionType.AUTOMATED,
        )

        interactive_token = ScopedToken(
            token_id="token_interactive",
            agent_id="planner",
            scopes=["search"],
            issued_at=now,
            expires_at=now + timedelta(hours=1),
            token_string="interactive_token",
            session_type=SessionType.INTERACTIVE,
        )

        assert automated_token.session_type == SessionType.AUTOMATED
        assert interactive_token.session_type == SessionType.INTERACTIVE


# -----------------------------------------------------------------------------
# Test: MCPGateway Class
# -----------------------------------------------------------------------------


class TestMCPGatewayInitialization:
    """Tests for MCPGateway class initialization."""

    def test_gateway_initialization(self) -> None:
        """MCPGateway should initialize with config."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="secret",
        )

        gateway = MCPGateway(config=config)

        assert gateway.config == config

    def test_gateway_initialization_with_custom_scopes(self) -> None:
        """MCPGateway should accept custom agent scopes."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="secret",
        )

        custom_scopes = {
            "custom_agent": ["custom_tool", "another_tool"],
        }

        gateway = MCPGateway(config=config, agent_scopes=custom_scopes)

        assert "custom_agent" in gateway.agent_scopes


# -----------------------------------------------------------------------------
# Test: Token Authorization (authorize_agent)
# -----------------------------------------------------------------------------


class TestAuthorizeAgent:
    """Tests for MCPGateway.authorize_agent method."""

    @pytest.mark.asyncio
    async def test_authorize_agent_basic(self) -> None:
        """authorize_agent should issue a scoped token for valid agent."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig, ScopedToken

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search", "read_file"],
        )

        assert isinstance(token, ScopedToken)
        assert token.agent_id == "planner"
        assert "search" in token.scopes
        assert "read_file" in token.scopes
        assert token.token_string is not None

    @pytest.mark.asyncio
    async def test_authorize_agent_restricts_to_allowed_scopes(self) -> None:
        """authorize_agent should only grant scopes the agent is allowed."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Planner requests write_file scope which they don't have
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search", "read_file", "write_file"],
        )

        assert "search" in token.scopes
        assert "read_file" in token.scopes
        assert "write_file" not in token.scopes  # Not allowed for planner

    @pytest.mark.asyncio
    async def test_authorize_agent_automated_ttl(self) -> None:
        """authorize_agent should use 15-minute TTL for automated sessions."""
        from daw_agents.mcp.gateway import (
            MCPGateway,
            MCPGatewayConfig,
            SessionType,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="executor",
            requested_scopes=["write_file"],
            session_type=SessionType.AUTOMATED,
        )

        # 15 minute TTL
        expected_ttl = timedelta(minutes=15)
        actual_ttl = token.expires_at - token.issued_at

        assert abs((actual_ttl - expected_ttl).total_seconds()) < 5  # Within 5 seconds

    @pytest.mark.asyncio
    async def test_authorize_agent_interactive_ttl(self) -> None:
        """authorize_agent should use 1-hour TTL for interactive sessions."""
        from daw_agents.mcp.gateway import (
            MCPGateway,
            MCPGatewayConfig,
            SessionType,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
            session_type=SessionType.INTERACTIVE,
        )

        # 1 hour TTL
        expected_ttl = timedelta(hours=1)
        actual_ttl = token.expires_at - token.issued_at

        assert abs((actual_ttl - expected_ttl).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_authorize_agent_unknown_agent(self) -> None:
        """authorize_agent should reject unknown agents."""
        from daw_agents.mcp.gateway import (
            MCPGateway,
            MCPGatewayConfig,
            UnauthorizedAgentError,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        with pytest.raises(UnauthorizedAgentError):
            await gateway.authorize_agent(
                agent_id="unknown_agent",
                requested_scopes=["some_scope"],
            )

    @pytest.mark.asyncio
    async def test_authorize_agent_includes_resource_indicator(self) -> None:
        """authorize_agent should include RFC 8707 resource indicator."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
            resource_uri="https://mcp.daw.example.com",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        assert token.resource == "https://mcp.daw.example.com"

    @pytest.mark.asyncio
    async def test_authorize_agent_generates_refresh_token(self) -> None:
        """authorize_agent should generate refresh token when requested."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
            with_refresh_token=True,
        )

        assert token.refresh_token is not None
        assert len(token.refresh_token) > 20


# -----------------------------------------------------------------------------
# Test: Token Validation (validate_token)
# -----------------------------------------------------------------------------


class TestValidateToken:
    """Tests for MCPGateway.validate_token method."""

    @pytest.mark.asyncio
    async def test_validate_token_success(self) -> None:
        """validate_token should validate a valid token."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Issue a token
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Validate it
        validated = await gateway.validate_token(token.token_string)

        assert validated is not None
        assert validated.agent_id == "planner"
        assert "search" in validated.scopes

    @pytest.mark.asyncio
    async def test_validate_token_expired(self) -> None:
        """validate_token should reject expired tokens."""
        from daw_agents.mcp.gateway import (
            MCPGateway,
            MCPGatewayConfig,
            TokenExpiredError,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
            automated_ttl_minutes=0,  # Immediate expiration for testing
        )

        gateway = MCPGateway(config=config)

        # Issue a token with 0 TTL
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Wait a bit and validate - should fail
        import asyncio

        await asyncio.sleep(0.1)

        with pytest.raises(TokenExpiredError):
            await gateway.validate_token(token.token_string)

    @pytest.mark.asyncio
    async def test_validate_token_invalid_signature(self) -> None:
        """validate_token should reject tokens with invalid signatures."""
        from daw_agents.mcp.gateway import (
            InvalidTokenError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Create a token and modify it
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Tamper with the token
        tampered_token = token.token_string + "tampered"

        with pytest.raises(InvalidTokenError):
            await gateway.validate_token(tampered_token)

    @pytest.mark.asyncio
    async def test_validate_token_wrong_audience(self) -> None:
        """validate_token should reject tokens with wrong audience."""
        from daw_agents.mcp.gateway import (
            InvalidAudienceError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config1 = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp1.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        config2 = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp2.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway1 = MCPGateway(config=config1)
        gateway2 = MCPGateway(config=config2)

        # Issue token for gateway1
        token = await gateway1.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Try to validate on gateway2 (different audience)
        with pytest.raises(InvalidAudienceError):
            await gateway2.validate_token(token.token_string)

    @pytest.mark.asyncio
    async def test_validate_token_revoked(self) -> None:
        """validate_token should reject revoked tokens."""
        from daw_agents.mcp.gateway import (
            MCPGateway,
            MCPGatewayConfig,
            TokenRevokedError,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Issue and revoke a token
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        await gateway.revoke_token(token.token_string)

        # Validate should fail
        with pytest.raises(TokenRevokedError):
            await gateway.validate_token(token.token_string)


# -----------------------------------------------------------------------------
# Test: Tool Call Validation (validate_tool_call)
# -----------------------------------------------------------------------------


class TestValidateToolCall:
    """Tests for MCPGateway.validate_tool_call method."""

    @pytest.mark.asyncio
    async def test_validate_tool_call_allowed(self) -> None:
        """validate_tool_call should allow authorized tool calls."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search", "read_file"],
        )

        # Should be allowed
        result = await gateway.validate_tool_call(
            token=token.token_string,
            tool_name="search",
            params={"query": "test"},
        )

        assert result.allowed is True
        assert result.scope_match == "search"

    @pytest.mark.asyncio
    async def test_validate_tool_call_denied(self) -> None:
        """validate_tool_call should deny unauthorized tool calls."""
        from daw_agents.mcp.gateway import (
            InsufficientScopeError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Planner token with limited scopes
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Try to use write_file which planner doesn't have
        with pytest.raises(InsufficientScopeError) as exc_info:
            await gateway.validate_tool_call(
                token=token.token_string,
                tool_name="write_file",
                params={"path": "/tmp/test.txt", "content": "hello"},
            )

        assert "write_file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_tool_call_parametric_scope(self) -> None:
        """validate_tool_call should handle parametric scopes correctly."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["query_db:SELECT"],
        )

        # SELECT should be allowed
        result = await gateway.validate_tool_call(
            token=token.token_string,
            tool_name="query_db",
            params={"query": "SELECT * FROM users"},
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_validate_tool_call_parametric_scope_denied(self) -> None:
        """validate_tool_call should deny operations outside parametric scope."""
        from daw_agents.mcp.gateway import (
            InsufficientScopeError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Planner only has SELECT permission
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["query_db:SELECT"],
        )

        # DROP should be denied
        with pytest.raises(InsufficientScopeError):
            await gateway.validate_tool_call(
                token=token.token_string,
                tool_name="query_db",
                params={"query": "DROP TABLE users"},
            )

    @pytest.mark.asyncio
    async def test_validate_tool_call_expired_token(self) -> None:
        """validate_tool_call should reject expired tokens."""
        from daw_agents.mcp.gateway import (
            MCPGateway,
            MCPGatewayConfig,
            TokenExpiredError,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
            automated_ttl_minutes=0,
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        import asyncio

        await asyncio.sleep(0.1)

        with pytest.raises(TokenExpiredError):
            await gateway.validate_tool_call(
                token=token.token_string,
                tool_name="search",
                params={"query": "test"},
            )


# -----------------------------------------------------------------------------
# Test: Token Refresh (refresh_token)
# -----------------------------------------------------------------------------


class TestRefreshToken:
    """Tests for MCPGateway.refresh_token method."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self) -> None:
        """refresh_token should issue a new token with same scopes."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        # Issue token with refresh capability
        original = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search", "read_file"],
            with_refresh_token=True,
        )

        # Refresh it
        new_token = await gateway.refresh_token(original.refresh_token)

        assert new_token.agent_id == original.agent_id
        assert set(new_token.scopes) == set(original.scopes)
        assert new_token.token_string != original.token_string
        assert new_token.expires_at > original.expires_at

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self) -> None:
        """refresh_token should reject invalid refresh tokens."""
        from daw_agents.mcp.gateway import (
            InvalidRefreshTokenError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        with pytest.raises(InvalidRefreshTokenError):
            await gateway.refresh_token("invalid_refresh_token")

    @pytest.mark.asyncio
    async def test_refresh_token_revoked(self) -> None:
        """refresh_token should reject revoked refresh tokens."""
        from daw_agents.mcp.gateway import (
            InvalidRefreshTokenError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        original = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
            with_refresh_token=True,
        )

        # Revoke the access token (should also invalidate refresh token)
        await gateway.revoke_token(original.token_string)

        with pytest.raises(InvalidRefreshTokenError):
            await gateway.refresh_token(original.refresh_token)


# -----------------------------------------------------------------------------
# Test: Token Revocation (revoke_token)
# -----------------------------------------------------------------------------


class TestRevokeToken:
    """Tests for MCPGateway.revoke_token method."""

    @pytest.mark.asyncio
    async def test_revoke_token_success(self) -> None:
        """revoke_token should invalidate a token."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Token should be valid initially
        validated = await gateway.validate_token(token.token_string)
        assert validated is not None

        # Revoke it
        result = await gateway.revoke_token(token.token_string)
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_token_idempotent(self) -> None:
        """revoke_token should be idempotent (safe to call multiple times)."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Revoke multiple times - should not raise
        await gateway.revoke_token(token.token_string)
        await gateway.revoke_token(token.token_string)
        await gateway.revoke_token(token.token_string)


# -----------------------------------------------------------------------------
# Test: RFC 8707 Resource Indicators
# -----------------------------------------------------------------------------


class TestRFC8707ResourceIndicators:
    """Tests for RFC 8707 Resource Indicators compliance."""

    @pytest.mark.asyncio
    async def test_resource_indicator_in_token(self) -> None:
        """Tokens should include resource indicator when configured."""
        import jwt

        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
            resource_uri="https://mcp.daw.example.com",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Decode and check resource claim
        decoded = jwt.decode(
            token.token_string,
            options={"verify_signature": False},
        )

        # Per RFC 8707, resource should be in 'aud' claim or separate claim
        assert (
            decoded.get("resource") == "https://mcp.daw.example.com"
            or "https://mcp.daw.example.com" in decoded.get("aud", [])
        )

    @pytest.mark.asyncio
    async def test_resource_indicator_validation(self) -> None:
        """validate_token should check resource indicator matches."""
        from daw_agents.mcp.gateway import (
            InvalidResourceError,
            MCPGateway,
            MCPGatewayConfig,
        )

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
            resource_uri="https://mcp.daw.example.com",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        # Validate with correct resource
        validated = await gateway.validate_token(
            token.token_string,
            expected_resource="https://mcp.daw.example.com",
        )
        assert validated is not None

        # Validate with wrong resource should fail
        with pytest.raises(InvalidResourceError):
            await gateway.validate_token(
                token.token_string,
                expected_resource="https://wrong-mcp.daw.example.com",
            )


# -----------------------------------------------------------------------------
# Test: OAuth 2.1 Compliance
# -----------------------------------------------------------------------------


class TestOAuth21Compliance:
    """Tests for OAuth 2.1 specification compliance."""

    @pytest.mark.asyncio
    async def test_token_contains_required_claims(self) -> None:
        """Tokens should contain all required JWT claims."""
        import jwt

        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        decoded = jwt.decode(
            token.token_string,
            options={"verify_signature": False},
        )

        # Required claims per OAuth 2.1 / JWT
        assert "iss" in decoded  # Issuer
        assert "sub" in decoded  # Subject (agent_id)
        assert "aud" in decoded  # Audience
        assert "exp" in decoded  # Expiration
        assert "iat" in decoded  # Issued At
        assert "jti" in decoded  # JWT ID (for revocation tracking)

    @pytest.mark.asyncio
    async def test_token_contains_scope_claim(self) -> None:
        """Tokens should contain scope claim per OAuth 2.1."""
        import jwt

        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search", "read_file"],
        )

        decoded = jwt.decode(
            token.token_string,
            options={"verify_signature": False},
        )

        # Scope claim should be space-separated string per OAuth 2.1
        assert "scope" in decoded
        scopes = decoded["scope"].split(" ")
        assert "search" in scopes
        assert "read_file" in scopes

    @pytest.mark.asyncio
    async def test_issuer_claim_matches_config(self) -> None:
        """Token issuer claim should match gateway config."""
        import jwt

        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        gateway = MCPGateway(config=config)

        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search"],
        )

        decoded = jwt.decode(
            token.token_string,
            options={"verify_signature": False},
        )

        assert decoded["iss"] == "https://daw.example.com"


# -----------------------------------------------------------------------------
# Test: Exception Classes
# -----------------------------------------------------------------------------


class TestGatewayExceptions:
    """Tests for gateway exception classes."""

    def test_unauthorized_agent_error(self) -> None:
        """UnauthorizedAgentError should be properly defined."""
        from daw_agents.mcp.gateway import UnauthorizedAgentError

        error = UnauthorizedAgentError("unknown_agent")
        assert "unknown_agent" in str(error)

    def test_insufficient_scope_error(self) -> None:
        """InsufficientScopeError should be properly defined."""
        from daw_agents.mcp.gateway import InsufficientScopeError

        error = InsufficientScopeError("write_file", required_scope="write_file")
        assert "write_file" in str(error)

    def test_token_expired_error(self) -> None:
        """TokenExpiredError should be properly defined."""
        from daw_agents.mcp.gateway import TokenExpiredError

        error = TokenExpiredError()
        assert error is not None

    def test_token_revoked_error(self) -> None:
        """TokenRevokedError should be properly defined."""
        from daw_agents.mcp.gateway import TokenRevokedError

        error = TokenRevokedError("token_id_123")
        assert "token_id_123" in str(error)

    def test_invalid_token_error(self) -> None:
        """InvalidTokenError should be properly defined."""
        from daw_agents.mcp.gateway import InvalidTokenError

        error = InvalidTokenError("Invalid signature")
        assert "Invalid signature" in str(error)

    def test_invalid_refresh_token_error(self) -> None:
        """InvalidRefreshTokenError should be properly defined."""
        from daw_agents.mcp.gateway import InvalidRefreshTokenError

        error = InvalidRefreshTokenError("Refresh token not found")
        assert "Refresh token not found" in str(error)

    def test_invalid_audience_error(self) -> None:
        """InvalidAudienceError should be properly defined."""
        from daw_agents.mcp.gateway import InvalidAudienceError

        error = InvalidAudienceError("https://wrong.example.com")
        assert "wrong.example.com" in str(error)

    def test_invalid_resource_error(self) -> None:
        """InvalidResourceError should be properly defined."""
        from daw_agents.mcp.gateway import InvalidResourceError

        error = InvalidResourceError("https://wrong-resource.example.com")
        assert "wrong-resource.example.com" in str(error)


# -----------------------------------------------------------------------------
# Test: ToolCallResult Model
# -----------------------------------------------------------------------------


class TestToolCallResult:
    """Tests for the ToolCallResult model from validate_tool_call."""

    def test_tool_call_result_allowed(self) -> None:
        """ToolCallResult should represent allowed tool call."""
        from daw_agents.mcp.gateway import ToolCallResult

        result = ToolCallResult(
            allowed=True,
            tool_name="search",
            scope_match="search",
            agent_id="planner",
        )

        assert result.allowed is True
        assert result.tool_name == "search"
        assert result.scope_match == "search"

    def test_tool_call_result_denied(self) -> None:
        """ToolCallResult should represent denied tool call."""
        from daw_agents.mcp.gateway import ToolCallResult

        result = ToolCallResult(
            allowed=False,
            tool_name="write_file",
            scope_match=None,
            agent_id="planner",
            error="Insufficient scope for write_file",
        )

        assert result.allowed is False
        assert result.error is not None
        assert "Insufficient scope" in result.error
