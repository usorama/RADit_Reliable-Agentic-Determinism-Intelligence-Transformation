"""
Tests for Neo4j connector module.

These tests use mocking to avoid requiring a running Neo4j instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.memory.neo4j import Neo4jConfig, Neo4jConnector

if TYPE_CHECKING:
    pass


class TestNeo4jConfig:
    """Tests for Neo4jConfig."""

    def test_config_with_defaults(self) -> None:
        """Test that config has sensible defaults."""
        config = Neo4jConfig(password="test_password")
        assert config.uri == "bolt://localhost:7687"
        assert config.user == "neo4j"
        assert config.password == "test_password"
        assert config.database == "neo4j"
        assert config.max_connection_pool_size == 50

    def test_config_custom_values(self) -> None:
        """Test that config accepts custom values."""
        config = Neo4jConfig(
            uri="bolt://custom-host:7688",
            user="custom_user",
            password="custom_password",
            database="custom_db",
            max_connection_pool_size=100,
        )
        assert config.uri == "bolt://custom-host:7688"
        assert config.user == "custom_user"
        assert config.password == "custom_password"
        assert config.database == "custom_db"
        assert config.max_connection_pool_size == 100


class TestNeo4jConnectorSingleton:
    """Tests for Neo4j connector singleton pattern."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None

    def test_singleton_returns_same_instance(self) -> None:
        """Test that get_instance returns the same instance."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver

            instance1 = Neo4jConnector.get_instance(config)
            instance2 = Neo4jConnector.get_instance(config)

            assert instance1 is instance2
            # Driver should only be created once
            mock_db.driver.assert_called_once()

    def test_get_instance_without_config_raises_error(self) -> None:
        """Test that get_instance without config and no existing instance raises error."""
        with pytest.raises(ValueError, match="Config required"):
            Neo4jConnector.get_instance()

    def test_get_instance_reuses_existing_without_config(self) -> None:
        """Test that get_instance returns existing instance without config."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver

            instance1 = Neo4jConnector.get_instance(config)
            instance2 = Neo4jConnector.get_instance()

            assert instance1 is instance2


class TestNeo4jConnectorOperations:
    """Tests for Neo4j connector operations."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None

    @pytest.fixture
    def connector(self) -> Neo4jConnector:
        """Create a connector instance with mocked driver."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver
            connector = Neo4jConnector.get_instance(config)
            connector._driver = mock_driver  # type: ignore[attr-defined]
            return connector

    @pytest.mark.asyncio
    async def test_create_node_returns_element_id(self, connector: Neo4jConnector) -> None:
        """Test that create_node returns the element_id."""
        mock_driver = connector._driver  # type: ignore[attr-defined]
        mock_result = AsyncMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value="4:test:12345")
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=mock_session)

        element_id = await connector.create_node(
            labels=["Person"], properties={"name": "Alice", "age": 30}
        )

        assert element_id == "4:test:12345"
        mock_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_relationship(self, connector: Neo4jConnector) -> None:
        """Test that create_relationship creates edge between nodes."""
        mock_driver = connector._driver  # type: ignore[attr-defined]
        mock_result = AsyncMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value="rel:12345")
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=mock_session)

        rel_id = await connector.create_relationship(
            from_node_id="4:test:1",
            to_node_id="4:test:2",
            rel_type="KNOWS",
            properties={"since": 2020},
        )

        assert rel_id == "rel:12345"
        mock_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_returns_results(self, connector: Neo4jConnector) -> None:
        """Test that query executes Cypher and returns results."""
        mock_driver = connector._driver  # type: ignore[attr-defined]

        # Create mock records that properly iterate
        mock_record1 = MagicMock()
        mock_record1.data.return_value = {"name": "Alice"}
        mock_record2 = MagicMock()
        mock_record2.data.return_value = {"name": "Bob"}

        mock_result = MagicMock()

        # Mock async iteration using MagicMock with async iter
        mock_result.__aiter__ = lambda self: mock_record_iter()

        async def mock_record_iter() -> AsyncMock:
            for record in [mock_record1, mock_record2]:
                yield record

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=mock_session)

        results = await connector.query(
            cypher="MATCH (p:Person) RETURN p.name as name", params=None
        )

        assert len(results) == 2
        assert results[0]["name"] == "Alice"
        assert results[1]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_get_node_by_id(self, connector: Neo4jConnector) -> None:
        """Test that get_node_by_id retrieves a node."""
        mock_driver = connector._driver  # type: ignore[attr-defined]
        mock_result = AsyncMock()

        mock_node = MagicMock()
        mock_node.labels = frozenset(["Person"])
        mock_node.items.return_value = [("name", "Alice"), ("age", 30)]

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=mock_node)
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=mock_session)

        node = await connector.get_node_by_id("4:test:12345")

        assert node is not None
        assert node["labels"] == ["Person"]
        assert node["properties"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_node_by_id_returns_none_for_missing(
        self, connector: Neo4jConnector
    ) -> None:
        """Test that get_node_by_id returns None for non-existent node."""
        mock_driver = connector._driver  # type: ignore[attr-defined]
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=mock_session)

        node = await connector.get_node_by_id("4:test:nonexistent")

        assert node is None


class TestNeo4jConnectorHealthCheck:
    """Tests for Neo4j connector health check."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None

    @pytest.mark.asyncio
    async def test_is_connected_returns_true_when_connected(self) -> None:
        """Test that is_connected returns True when database is reachable."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_driver.verify_connectivity = AsyncMock(return_value=None)
            mock_db.driver.return_value = mock_driver

            connector = Neo4jConnector.get_instance(config)
            connector._driver = mock_driver

            is_connected = await connector.is_connected()

            assert is_connected is True
            mock_driver.verify_connectivity.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_connected_returns_false_when_disconnected(self) -> None:
        """Test that is_connected returns False when database is unreachable."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_driver.verify_connectivity = AsyncMock(side_effect=Exception("Connection failed"))
            mock_db.driver.return_value = mock_driver

            connector = Neo4jConnector.get_instance(config)
            connector._driver = mock_driver

            is_connected = await connector.is_connected()

            assert is_connected is False


class TestNeo4jConnectorLifecycle:
    """Tests for Neo4j connector lifecycle management."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None

    @pytest.mark.asyncio
    async def test_graceful_close(self) -> None:
        """Test that close properly closes the driver connection."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_driver.close = AsyncMock(return_value=None)
            mock_db.driver.return_value = mock_driver

            connector = Neo4jConnector.get_instance(config)
            connector._driver = mock_driver

            await connector.close()

            mock_driver.close.assert_called_once()
            assert Neo4jConnector._instance is None
            assert Neo4jConnector._driver is None

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self) -> None:
        """Test that calling close multiple times is safe."""
        config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_driver.close = AsyncMock(return_value=None)
            mock_db.driver.return_value = mock_driver

            connector = Neo4jConnector.get_instance(config)

            await connector.close()
            # Driver should be reset to None after first close
            assert Neo4jConnector._driver is None
            assert Neo4jConnector._instance is None

            # Second close should not raise and should be a no-op
            # Need to get a new reference since instance was cleared
            # But calling close on the old reference shouldn't crash
            await connector.close()

            # close should only be called once on the driver (first time only)
            mock_driver.close.assert_called_once()
