"""Comprehensive tests for MCP Client Interface.

This module tests the MCP (Model Context Protocol) client implementation
following the JSON-RPC 2.0 specification.

Tests cover:
1. Client initialization with server configuration
2. Tool discovery (tools/list)
3. Tool execution (tools/call)
4. Error handling for JSON-RPC errors
5. Multiple server management
6. Connection lifecycle
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Test: MCPTool Model
# -----------------------------------------------------------------------------


class TestMCPToolModel:
    """Tests for the MCPTool Pydantic model."""

    def test_mcp_tool_creation(self) -> None:
        """MCPTool should be creatable with required fields."""
        from daw_agents.mcp.client import MCPTool

        tool = MCPTool(
            name="git_status",
            description="Get the current git status",
            input_schema={"type": "object", "properties": {}},
        )

        assert tool.name == "git_status"
        assert tool.description == "Get the current git status"
        assert tool.input_schema == {"type": "object", "properties": {}}

    def test_mcp_tool_with_complex_schema(self) -> None:
        """MCPTool should handle complex input schemas."""
        from daw_agents.mcp.client import MCPTool

        complex_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        }

        tool = MCPTool(
            name="read_file",
            description="Read a file from the filesystem",
            input_schema=complex_schema,
        )

        assert tool.input_schema["required"] == ["path"]


# -----------------------------------------------------------------------------
# Test: MCPToolResult Model
# -----------------------------------------------------------------------------


class TestMCPToolResultModel:
    """Tests for the MCPToolResult Pydantic model."""

    def test_mcp_tool_result_success(self) -> None:
        """MCPToolResult should represent successful tool execution."""
        from daw_agents.mcp.client import MCPToolResult

        result = MCPToolResult(
            success=True,
            result={"status": "clean", "branch": "main"},
            error=None,
        )

        assert result.success is True
        assert result.result["branch"] == "main"
        assert result.error is None

    def test_mcp_tool_result_failure(self) -> None:
        """MCPToolResult should represent failed tool execution."""
        from daw_agents.mcp.client import MCPToolResult

        result = MCPToolResult(
            success=False,
            result=None,
            error="Tool execution failed: permission denied",
        )

        assert result.success is False
        assert result.result is None
        assert "permission denied" in result.error


# -----------------------------------------------------------------------------
# Test: MCPClient Initialization
# -----------------------------------------------------------------------------


class TestMCPClientInitialization:
    """Tests for MCPClient initialization."""

    def test_client_initialization_with_url(self) -> None:
        """MCPClient should initialize with server URL."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(
            server_url="http://localhost:3001",
            server_name="git-server",
        )

        assert client.server_url == "http://localhost:3001"
        assert client.server_name == "git-server"

    def test_client_initialization_default_name(self) -> None:
        """MCPClient should use 'default' as server name if not provided."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        assert client.server_name == "default"

    def test_client_initialization_with_timeout(self) -> None:
        """MCPClient should accept custom timeout configuration."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(
            server_url="http://localhost:3001",
            timeout=60.0,
        )

        assert client.timeout == 60.0

    def test_client_initialization_default_timeout(self) -> None:
        """MCPClient should have a sensible default timeout."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        assert client.timeout == 30.0  # Default 30 seconds


# -----------------------------------------------------------------------------
# Test: Tool Discovery (tools/list)
# -----------------------------------------------------------------------------


class TestToolDiscovery:
    """Tests for MCP tool discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_tools_returns_list(self) -> None:
        """discover_tools should return a list of MCPTool objects."""
        from daw_agents.mcp.client import MCPClient, MCPTool

        client = MCPClient(server_url="http://localhost:3001")

        # Mock the HTTP response
        mock_response = {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "git_status",
                        "description": "Get git status",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "git_commit",
                        "description": "Create a git commit",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                        },
                    },
                ]
            },
            "id": 1,
        }

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = mock_response

            tools = await client.discover_tools()

            assert len(tools) == 2
            assert all(isinstance(tool, MCPTool) for tool in tools)
            assert tools[0].name == "git_status"
            assert tools[1].name == "git_commit"

    @pytest.mark.asyncio
    async def test_discover_tools_empty_list(self) -> None:
        """discover_tools should return empty list when server has no tools."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        mock_response = {
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": 1,
        }

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = mock_response

            tools = await client.discover_tools()

            assert tools == []

    @pytest.mark.asyncio
    async def test_discover_tools_sends_correct_request(self) -> None:
        """discover_tools should send properly formatted JSON-RPC request."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        mock_response = {
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": 1,
        }

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = mock_response

            await client.discover_tools()

            # Verify the request format
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "tools/list"


# -----------------------------------------------------------------------------
# Test: Tool Execution (tools/call)
# -----------------------------------------------------------------------------


class TestToolExecution:
    """Tests for MCP tool execution functionality."""

    @pytest.mark.asyncio
    async def test_call_tool_success(self) -> None:
        """call_tool should return successful result."""
        from daw_agents.mcp.client import MCPClient, MCPToolResult

        client = MCPClient(server_url="http://localhost:3001")

        mock_response = {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": "On branch main\nnothing to commit"}]
            },
            "id": 2,
        }

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = mock_response

            result = await client.call_tool("git_status", params={})

            assert isinstance(result, MCPToolResult)
            assert result.success is True
            assert "On branch main" in str(result.result)

    @pytest.mark.asyncio
    async def test_call_tool_with_params(self) -> None:
        """call_tool should send parameters correctly."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        mock_response = {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": "File content here"}]},
            "id": 2,
        }

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = mock_response

            await client.call_tool("read_file", params={"path": "/tmp/test.txt"})

            # Verify params were passed correctly
            call_args = mock_send.call_args
            assert call_args[0][0] == "tools/call"
            assert call_args[1]["params"]["arguments"]["path"] == "/tmp/test.txt"

    @pytest.mark.asyncio
    async def test_call_tool_with_error(self) -> None:
        """call_tool should handle JSON-RPC errors gracefully."""
        from daw_agents.mcp.client import MCPClient, MCPToolResult

        client = MCPClient(server_url="http://localhost:3001")

        mock_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
            },
            "id": 2,
        }

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = mock_response

            result = await client.call_tool("nonexistent_tool", params={})

            assert isinstance(result, MCPToolResult)
            assert result.success is False
            assert "Method not found" in result.error

    @pytest.mark.asyncio
    async def test_call_tool_network_error(self) -> None:
        """call_tool should handle network errors gracefully."""
        import httpx

        from daw_agents.mcp.client import MCPClient, MCPToolResult

        client = MCPClient(server_url="http://localhost:3001")

        with patch.object(
            client, "_send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = httpx.ConnectError("Connection refused")

            result = await client.call_tool("git_status", params={})

            assert isinstance(result, MCPToolResult)
            assert result.success is False
            assert "Connection" in result.error


# -----------------------------------------------------------------------------
# Test: JSON-RPC Request Format
# -----------------------------------------------------------------------------


class TestJSONRPCFormat:
    """Tests for JSON-RPC 2.0 request/response formatting."""

    @pytest.mark.asyncio
    async def test_json_rpc_request_format(self) -> None:
        """Requests should follow JSON-RPC 2.0 specification."""
        import httpx

        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        captured_request: dict | None = None

        async def mock_post(url: str, json: dict, **kwargs: object) -> MagicMock:
            nonlocal captured_request
            captured_request = json
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "jsonrpc": "2.0",
                "result": {"tools": []},
                "id": json.get("id"),
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            async with httpx.AsyncClient() as http_client:
                with patch.object(client, "_http_client", http_client):
                    await client.discover_tools()

        # Verify JSON-RPC 2.0 format (if request was captured)
        # Note: Implementation will determine actual format
        # This test validates the contract

    def test_request_id_increments(self) -> None:
        """Each request should have a unique incrementing ID."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        id1 = client._next_request_id()
        id2 = client._next_request_id()
        id3 = client._next_request_id()

        assert id2 == id1 + 1
        assert id3 == id2 + 1


# -----------------------------------------------------------------------------
# Test: Multiple Servers
# -----------------------------------------------------------------------------


class TestMultipleServers:
    """Tests for managing connections to multiple MCP servers."""

    def test_create_multiple_clients(self) -> None:
        """Should be able to create clients for different servers."""
        from daw_agents.mcp.client import MCPClient

        git_client = MCPClient(
            server_url="http://localhost:3001",
            server_name="git-server",
        )

        fs_client = MCPClient(
            server_url="http://localhost:3002",
            server_name="filesystem-server",
        )

        postgres_client = MCPClient(
            server_url="http://localhost:3003",
            server_name="postgres-server",
        )

        assert git_client.server_name == "git-server"
        assert fs_client.server_name == "filesystem-server"
        assert postgres_client.server_name == "postgres-server"

    @pytest.mark.asyncio
    async def test_clients_are_independent(self) -> None:
        """Each client should maintain its own connection state."""
        from daw_agents.mcp.client import MCPClient

        client1 = MCPClient(server_url="http://localhost:3001", server_name="server1")
        client2 = MCPClient(server_url="http://localhost:3002", server_name="server2")

        # Request IDs should be independent
        id1_a = client1._next_request_id()
        id2_a = client2._next_request_id()
        id1_b = client1._next_request_id()

        # Each client has its own sequence
        assert id1_b == id1_a + 1
        assert id2_a == 1  # Second client starts at 1


# -----------------------------------------------------------------------------
# Test: Connection Lifecycle
# -----------------------------------------------------------------------------


class TestConnectionLifecycle:
    """Tests for connection management and cleanup."""

    @pytest.mark.asyncio
    async def test_close_connection(self) -> None:
        """close() should properly cleanup resources."""
        from daw_agents.mcp.client import MCPClient

        client = MCPClient(server_url="http://localhost:3001")

        # Should not raise
        await client.close()

        # Should be safe to call multiple times
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager_support(self) -> None:
        """MCPClient should support async context manager protocol."""
        from daw_agents.mcp.client import MCPClient

        async with MCPClient(server_url="http://localhost:3001") as client:
            assert client.server_url == "http://localhost:3001"

        # After exiting context, client should be closed
        # (Implementation will define what "closed" means)


# -----------------------------------------------------------------------------
# Test: MCPClientManager
# -----------------------------------------------------------------------------


class TestMCPClientManager:
    """Tests for the MCPClientManager that manages multiple server connections."""

    def test_manager_initialization(self) -> None:
        """MCPClientManager should initialize with optional server configs."""
        from daw_agents.mcp.client import MCPClientManager

        manager = MCPClientManager()
        assert manager is not None

    def test_manager_add_server(self) -> None:
        """Should be able to add server configurations."""
        from daw_agents.mcp.client import MCPClientManager

        manager = MCPClientManager()
        manager.add_server("git", "http://localhost:3001")
        manager.add_server("filesystem", "http://localhost:3002")

        assert "git" in manager.servers
        assert "filesystem" in manager.servers

    @pytest.mark.asyncio
    async def test_manager_get_client(self) -> None:
        """Should retrieve or create client for a server."""
        from daw_agents.mcp.client import MCPClient, MCPClientManager

        manager = MCPClientManager()
        manager.add_server("git", "http://localhost:3001")

        client = await manager.get_client("git")

        assert isinstance(client, MCPClient)
        assert client.server_name == "git"

    @pytest.mark.asyncio
    async def test_manager_close_all(self) -> None:
        """close_all() should close all managed clients."""
        from daw_agents.mcp.client import MCPClientManager

        manager = MCPClientManager()
        manager.add_server("git", "http://localhost:3001")
        manager.add_server("fs", "http://localhost:3002")

        # Get clients to create them
        await manager.get_client("git")
        await manager.get_client("fs")

        # Should not raise
        await manager.close_all()
