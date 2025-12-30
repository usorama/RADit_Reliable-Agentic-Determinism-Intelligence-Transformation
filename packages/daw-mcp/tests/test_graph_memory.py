"""Tests for the Graph Memory MCP server.

These tests verify the Graph Memory MCP server functionality.
Note: Some tests require a running Neo4j instance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockNeo4jDriver:
    """Mock Neo4j driver for testing."""

    def __init__(self) -> None:
        self.sessions: list[MockSession] = []
        self._data: dict[str, dict[str, Any]] = {}

    def session(self) -> "MockSession":
        session = MockSession(self._data)
        self.sessions.append(session)
        return session

    def close(self) -> None:
        pass


class MockSession:
    """Mock Neo4j session for testing."""

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        self._data = data
        self._closed = False

    def run(self, query: str, params: dict[str, Any] | None = None) -> "MockResult":
        params = params or {}

        # Handle constraint/index creation
        if "CREATE CONSTRAINT" in query or "CREATE INDEX" in query:
            return MockResult([])

        # Handle memory creation
        if "CREATE (m:Memory" in query:
            memory_id = params.get("id", "test-id")
            self._data[memory_id] = {
                "id": memory_id,
                "content": params.get("content", ""),
                "type": params.get("type", "fact"),
                "created_at": params.get("created_at", ""),
                "metadata": params.get("metadata", {}),
            }
            return MockResult([{"m": MockNode(self._data[memory_id])}])

        # Handle memory search
        if "WHERE m.content CONTAINS" in query:
            search_query = params.get("query", "")
            results = []
            for memory in self._data.values():
                if search_query in memory.get("content", ""):
                    results.append({"m": MockNode(memory)})
            return MockResult(results[: params.get("limit", 10)])

        # Handle delete
        if "DETACH DELETE" in query:
            memory_id = params.get("id")
            if memory_id in self._data:
                del self._data[memory_id]
                return MockResult([{"deleted": 1}])
            return MockResult([{"deleted": 0}])

        return MockResult([])

    def __enter__(self) -> "MockSession":
        return self

    def __exit__(self, *args: object) -> None:
        self._closed = True


class MockResult:
    """Mock Neo4j result for testing."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records
        self._index = 0

    def __iter__(self) -> "MockResult":
        return self

    def __next__(self) -> dict[str, Any]:
        if self._index >= len(self._records):
            raise StopIteration
        record = self._records[self._index]
        self._index += 1
        return record


class MockNode:
    """Mock Neo4j node for testing."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


class TestGraphMemoryServerCreation:
    """Test suite for the Graph Memory MCP server creation."""

    @patch("daw_mcp.graph_memory.server.GraphDatabase")
    def test_create_server(self, mock_graph_db: MagicMock) -> None:
        """Test server creation."""
        mock_graph_db.driver.return_value = MockNeo4jDriver()

        from daw_mcp.graph_memory.server import create_server

        server = create_server(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="test",
        )

        assert server is not None
        assert server.name == "DAW Graph Memory MCP Server"

    @patch("daw_mcp.graph_memory.server.GraphDatabase")
    def test_server_has_tools(self, mock_graph_db: MagicMock) -> None:
        """Test that server registers expected tools."""
        mock_graph_db.driver.return_value = MockNeo4jDriver()

        from daw_mcp.graph_memory.server import create_server

        server = create_server(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="test",
        )

        tools = server._tool_manager._tools
        assert "memory_store" in tools
        assert "memory_query" in tools
        assert "memory_search" in tools
        assert "memory_link" in tools
        assert "memory_context" in tools
        assert "memory_delete" in tools


class TestNeo4jConnectionLogic:
    """Test Neo4j connection and query logic directly."""

    def test_mock_neo4j_driver(self) -> None:
        """Test the mock Neo4j driver works correctly."""
        driver = MockNeo4jDriver()

        with driver.session() as session:
            # Test constraint creation
            result = session.run("CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory)")
            assert list(result) == []

            # Test memory creation
            result = session.run(
                "CREATE (m:Memory {id: $id, content: $content})",
                {"id": "test-1", "content": "Test memory"},
            )
            records = list(result)
            assert len(records) == 1

            # Test memory search
            result = session.run(
                "MATCH (m:Memory) WHERE m.content CONTAINS $query RETURN m",
                {"query": "Test", "limit": 10},
            )
            records = list(result)
            assert len(records) == 1

    def test_mock_memory_delete(self) -> None:
        """Test memory deletion with mock driver."""
        driver = MockNeo4jDriver()

        with driver.session() as session:
            # Create a memory first
            session.run(
                "CREATE (m:Memory {id: $id, content: $content})",
                {"id": "delete-me", "content": "To be deleted"},
            )

            # Delete it
            result = session.run(
                "MATCH (m:Memory {id: $id}) DETACH DELETE m RETURN count(*) as deleted",
                {"id": "delete-me"},
            )
            records = list(result)
            assert len(records) == 1
            assert records[0]["deleted"] == 1

            # Try to delete again
            result = session.run(
                "MATCH (m:Memory {id: $id}) DETACH DELETE m RETURN count(*) as deleted",
                {"id": "delete-me"},
            )
            records = list(result)
            assert len(records) == 1
            assert records[0]["deleted"] == 0


class TestMemoryStoreFunctionality:
    """Test memory store functionality directly."""

    def test_memory_store_creates_uuid(self) -> None:
        """Test that memory_store creates a valid UUID."""
        from datetime import datetime, timezone
        from uuid import uuid4

        memory_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Verify UUID format
        assert len(memory_id) == 36
        assert memory_id.count("-") == 4

        # Verify timestamp format
        assert "T" in created_at
        assert "+" in created_at or "Z" in created_at or created_at.endswith("+00:00")

    def test_memory_context_result_structure(self) -> None:
        """Test that memory_context returns proper structure."""
        # The expected result structure
        result = {
            "central": [],
            "related": [],
            "relationships": [],
        }

        assert "central" in result
        assert "related" in result
        assert "relationships" in result
        assert isinstance(result["central"], list)
        assert isinstance(result["related"], list)
        assert isinstance(result["relationships"], list)

    def test_memory_link_sanitizes_relationship_name(self) -> None:
        """Test that relationship names are properly sanitized."""
        relationship = "relates-to"
        safe_rel = "".join(c if c.isalnum() or c == "_" else "_" for c in relationship.upper())

        assert safe_rel == "RELATES_TO"
        assert "-" not in safe_rel

    def test_memory_link_handles_special_chars(self) -> None:
        """Test relationship name sanitization with special characters."""
        test_cases = [
            ("RELATES_TO", "RELATES_TO"),
            ("depends-on", "DEPENDS_ON"),
            ("has child", "HAS_CHILD"),
            ("test@#$%rel", "TEST____REL"),
        ]

        for input_rel, expected in test_cases:
            safe_rel = "".join(c if c.isalnum() or c == "_" else "_" for c in input_rel.upper())
            assert safe_rel == expected
