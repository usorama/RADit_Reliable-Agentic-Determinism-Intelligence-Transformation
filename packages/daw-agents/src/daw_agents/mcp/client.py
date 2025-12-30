"""MCP Client Interface for Model Context Protocol.

This module provides a generic MCP client wrapper that can discover tools
from connected MCP servers and execute them using JSON-RPC 2.0.

The Model Context Protocol (MCP) is an open standard for AI systems to
integrate with external tools, systems, and data sources.

Example usage:
    async with MCPClient(server_url="http://localhost:3001") as client:
        tools = await client.discover_tools()
        result = await client.call_tool("git_status", params={})

References:
    - MCP Specification: https://modelcontextprotocol.io/specification/2025-06-18
    - JSON-RPC 2.0: https://www.jsonrpc.org/specification
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------


class MCPTool(BaseModel):
    """Represents a tool exposed by an MCP server.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        input_schema: JSON Schema defining the tool's input parameters
    """

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    """Represents the result of a tool execution.

    Attributes:
        success: Whether the tool executed successfully
        result: The result data from the tool (if successful)
        error: Error message (if unsuccessful)
    """

    success: bool
    result: Any = None
    error: str | None = None


class JSONRPCError(BaseModel):
    """Represents a JSON-RPC 2.0 error object.

    Attributes:
        code: Error code (negative integer)
        message: Human-readable error message
        data: Additional error data (optional)
    """

    code: int
    message: str
    data: Any = None


# -----------------------------------------------------------------------------
# MCP Client
# -----------------------------------------------------------------------------


class MCPClient:
    """Client for interacting with MCP servers using JSON-RPC 2.0.

    This client provides methods to:
    1. Discover available tools from an MCP server
    2. Execute tools with parameters
    3. Handle JSON-RPC errors gracefully

    The client uses HTTP transport with JSON-RPC 2.0 protocol for communication.

    Attributes:
        server_url: The base URL of the MCP server
        server_name: A friendly name for this server connection
        timeout: Request timeout in seconds

    Example:
        client = MCPClient(
            server_url="http://localhost:3001",
            server_name="git-server"
        )
        tools = await client.discover_tools()
        result = await client.call_tool("git_status", params={})
        await client.close()
    """

    def __init__(
        self,
        server_url: str,
        server_name: str = "default",
        timeout: float = 30.0,
    ) -> None:
        """Initialize the MCP client.

        Args:
            server_url: The base URL of the MCP server
            server_name: A friendly name for this server connection
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.server_url = server_url
        self.server_name = server_name
        self.timeout = timeout
        self._request_id = 0
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> MCPClient:
        """Enter async context manager."""
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager."""
        await self.close()

    def _next_request_id(self) -> int:
        """Generate the next request ID.

        Returns:
            Incrementing integer ID for each request
        """
        self._request_id += 1
        return self._request_id

    def _build_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a JSON-RPC 2.0 request object.

        Args:
            method: The RPC method name
            params: Optional parameters for the method

        Returns:
            A properly formatted JSON-RPC 2.0 request
        """
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._next_request_id(),
        }
        if params is not None:
            request["params"] = params
        return request

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to the MCP server.

        Args:
            method: The RPC method name
            params: Optional parameters for the method

        Returns:
            The JSON-RPC response as a dictionary

        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)

        request = self._build_request(method, params)

        logger.debug(
            "Sending MCP request to %s: method=%s, id=%s",
            self.server_url,
            method,
            request["id"],
        )

        response = await self._http_client.post(
            self.server_url,
            json=request,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        result: dict[str, Any] = response.json()
        logger.debug("Received MCP response: id=%s", result.get("id"))

        return result

    async def discover_tools(self) -> list[MCPTool]:
        """Discover available tools from the MCP server.

        Sends a 'tools/list' request to the server and parses the response
        into MCPTool objects.

        Returns:
            List of available tools

        Example:
            tools = await client.discover_tools()
            for tool in tools:
                print(f"{tool.name}: {tool.description}")
        """
        try:
            response = await self._send_request("tools/list")

            if "error" in response:
                error = JSONRPCError(**response["error"])
                logger.error(
                    "Failed to discover tools: %s (code: %d)",
                    error.message,
                    error.code,
                )
                return []

            result = response.get("result", {})
            tools_data = result.get("tools", [])

            tools = []
            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data.get("name", ""),
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                )
                tools.append(tool)

            logger.info(
                "Discovered %d tools from %s",
                len(tools),
                self.server_name,
            )
            return tools

        except httpx.HTTPError as e:
            logger.error("HTTP error during tool discovery: %s", str(e))
            return []

    async def call_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> MCPToolResult:
        """Execute a tool on the MCP server.

        Sends a 'tools/call' request with the tool name and arguments.

        Args:
            tool_name: The name of the tool to execute
            params: Parameters/arguments to pass to the tool

        Returns:
            MCPToolResult containing the result or error

        Example:
            result = await client.call_tool(
                "read_file",
                params={"path": "/tmp/test.txt"}
            )
            if result.success:
                print(result.result)
            else:
                print(f"Error: {result.error}")
        """
        try:
            response = await self._send_request(
                "tools/call",
                params={"name": tool_name, "arguments": params},
            )

            if "error" in response:
                error = JSONRPCError(**response["error"])
                logger.warning(
                    "Tool call failed: %s - %s (code: %d)",
                    tool_name,
                    error.message,
                    error.code,
                )
                return MCPToolResult(
                    success=False,
                    result=None,
                    error=error.message,
                )

            result = response.get("result", {})
            content = result.get("content", [])

            # Extract text content from the response
            extracted_result: Any = None
            if content:
                # Handle text content (most common)
                for item in content:
                    if item.get("type") == "text":
                        if extracted_result is None:
                            extracted_result = item.get("text", "")
                        else:
                            extracted_result = str(extracted_result) + "\n" + item.get("text", "")
                    else:
                        # For non-text content, store the raw item
                        if extracted_result is None:
                            extracted_result = item
                        elif isinstance(extracted_result, list):
                            extracted_result.append(item)
                        else:
                            extracted_result = [extracted_result, item]

            # Also check for structuredContent (MCP 2025-06-18 spec)
            if "structuredContent" in result:
                structured = result["structuredContent"]
                if extracted_result is None:
                    extracted_result = structured
                else:
                    extracted_result = {
                        "content": extracted_result,
                        "structured": structured,
                    }

            logger.info("Tool %s executed successfully on %s", tool_name, self.server_name)
            return MCPToolResult(
                success=True,
                result=extracted_result if extracted_result is not None else result,
                error=None,
            )

        except httpx.ConnectError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error("Failed to call tool %s: %s", tool_name, error_msg)
            return MCPToolResult(
                success=False,
                result=None,
                error=error_msg,
            )
        except httpx.HTTPError as e:
            error_msg = f"HTTP error: {str(e)}"
            logger.error("Failed to call tool %s: %s", tool_name, error_msg)
            return MCPToolResult(
                success=False,
                result=None,
                error=error_msg,
            )

    async def close(self) -> None:
        """Close the HTTP client connection.

        Safe to call multiple times.
        """
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
            logger.debug("Closed MCP client connection to %s", self.server_name)


# -----------------------------------------------------------------------------
# MCP Client Manager
# -----------------------------------------------------------------------------


class MCPClientManager:
    """Manages multiple MCP server connections.

    Provides a centralized way to configure and access multiple MCP servers.

    Example:
        manager = MCPClientManager()
        manager.add_server("git", "http://localhost:3001")
        manager.add_server("filesystem", "http://localhost:3002")

        git_client = await manager.get_client("git")
        tools = await git_client.discover_tools()

        await manager.close_all()
    """

    def __init__(self) -> None:
        """Initialize the client manager."""
        self.servers: dict[str, str] = {}
        self._clients: dict[str, MCPClient] = {}

    def add_server(self, name: str, url: str) -> None:
        """Add a server configuration.

        Args:
            name: Friendly name for the server
            url: The server's URL
        """
        self.servers[name] = url
        logger.debug("Added MCP server: %s -> %s", name, url)

    async def get_client(self, name: str) -> MCPClient:
        """Get or create a client for a server.

        Args:
            name: The server name

        Returns:
            An MCPClient instance for the server

        Raises:
            KeyError: If the server name is not configured
        """
        if name not in self.servers:
            raise KeyError(f"Server '{name}' not configured")

        if name not in self._clients:
            self._clients[name] = MCPClient(
                server_url=self.servers[name],
                server_name=name,
            )
            logger.debug("Created MCP client for server: %s", name)

        return self._clients[name]

    async def close_all(self) -> None:
        """Close all managed client connections."""
        for name, client in self._clients.items():
            await client.close()
            logger.debug("Closed MCP client: %s", name)
        self._clients.clear()
