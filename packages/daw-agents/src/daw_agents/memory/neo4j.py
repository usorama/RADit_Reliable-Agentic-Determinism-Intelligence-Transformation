"""
Neo4j connector module providing a singleton pattern for managing Neo4j connections.

This module provides:
- Neo4jConfig: Configuration for Neo4j connection
- Neo4jConnector: Singleton class for managing Neo4j connections and graph operations
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Neo4jConfig(BaseModel):
    """Configuration for Neo4j connection."""

    uri: str = Field(default="bolt://localhost:7687", description="Neo4j bolt URI")
    user: str = Field(default="neo4j", description="Neo4j username")
    password: str = Field(..., description="Neo4j password")
    database: str = Field(default="neo4j", description="Neo4j database name")
    max_connection_pool_size: int = Field(
        default=50, description="Maximum connection pool size"
    )


class Neo4jConnector:
    """
    Singleton class for managing Neo4j connections and graph operations.

    This class provides:
    - Connection pool management via singleton pattern
    - Basic graph operations (create node, create relationship, query)
    - Health check functionality
    - Graceful shutdown

    Example:
        config = Neo4jConfig(password="your_password")
        connector = Neo4jConnector.get_instance(config)
        node_id = await connector.create_node(["Person"], {"name": "Alice"})
        await connector.close()
    """

    _instance: ClassVar[Neo4jConnector | None] = None
    _driver: ClassVar[Any | None] = None
    _config: ClassVar[Neo4jConfig | None] = None

    def __new__(cls) -> Neo4jConnector:
        """Prevent direct instantiation - use get_instance()."""
        raise TypeError("Use Neo4jConnector.get_instance() instead of direct instantiation")

    @classmethod
    def get_instance(cls, config: Neo4jConfig | None = None) -> Neo4jConnector:
        """
        Get or create the singleton instance.

        Args:
            config: Neo4j configuration. Required on first call,
                   optional thereafter.

        Returns:
            The singleton Neo4jConnector instance.

        Raises:
            ValueError: If called without config when no instance exists.
        """
        if cls._instance is None:
            if config is None:
                raise ValueError("Config required for first initialization")

            # Create instance without calling __new__ normally
            instance = object.__new__(cls)
            cls._instance = instance
            cls._config = config

            # Initialize the driver
            cls._driver = AsyncGraphDatabase.driver(
                config.uri,
                auth=(config.user, config.password),
                max_connection_pool_size=config.max_connection_pool_size,
            )
            logger.info("Neo4j connector initialized with URI: %s", config.uri)

        return cls._instance

    @property
    def config(self) -> Neo4jConfig:
        """Get the current configuration."""
        if self._config is None:
            raise RuntimeError("Connector not initialized")
        return self._config

    @property
    def database(self) -> str:
        """Get the database name."""
        return self.config.database

    async def create_node(
        self, labels: list[str], properties: dict[str, Any]
    ) -> str:
        """
        Create a node in the graph and return its element_id.

        Args:
            labels: List of labels for the node.
            properties: Dictionary of properties for the node.

        Returns:
            The element_id of the created node.

        Raises:
            Neo4jError: If node creation fails.
        """
        if self._driver is None:
            raise RuntimeError("Driver not initialized")

        labels_str = ":".join(labels) if labels else ""
        cypher = f"CREATE (n:{labels_str} $props) RETURN elementId(n) as id"

        async with self._driver.session(database=self.database) as session:
            result = await session.run(cypher, props=properties)
            record = await result.single()
            if record is None:
                raise Neo4jError("Failed to create node - no record returned")
            element_id: str = record["id"]
            logger.debug("Created node with id: %s", element_id)
            return element_id

    async def create_relationship(
        self,
        from_node_id: str,
        to_node_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a relationship between two nodes.

        Args:
            from_node_id: Element ID of the source node.
            to_node_id: Element ID of the target node.
            rel_type: Type of the relationship.
            properties: Optional dictionary of properties for the relationship.

        Returns:
            The element_id of the created relationship.

        Raises:
            Neo4jError: If relationship creation fails.
        """
        if self._driver is None:
            raise RuntimeError("Driver not initialized")

        props = properties or {}
        cypher = """
            MATCH (a) WHERE elementId(a) = $from_id
            MATCH (b) WHERE elementId(b) = $to_id
            CREATE (a)-[r:{rel_type} $props]->(b)
            RETURN elementId(r) as id
        """.replace("{rel_type}", rel_type)

        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                cypher, from_id=from_node_id, to_id=to_node_id, props=props
            )
            record = await result.single()
            if record is None:
                raise Neo4jError("Failed to create relationship - no record returned")
            rel_id: str = record["id"]
            logger.debug("Created relationship with id: %s", rel_id)
            return rel_id

    async def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            cypher: The Cypher query to execute.
            params: Optional parameters for the query.

        Returns:
            List of dictionaries containing the query results.
        """
        if self._driver is None:
            raise RuntimeError("Driver not initialized")

        async with self._driver.session(database=self.database) as session:
            result = await session.run(cypher, params or {})
            records: list[dict[str, Any]] = []
            async for record in result:
                records.append(record.data())
            return records

    async def get_node_by_id(self, node_id: str) -> dict[str, Any] | None:
        """
        Retrieve a node by its element ID.

        Args:
            node_id: The element ID of the node.

        Returns:
            Dictionary with 'labels' and 'properties' keys, or None if not found.
        """
        if self._driver is None:
            raise RuntimeError("Driver not initialized")

        cypher = "MATCH (n) WHERE elementId(n) = $id RETURN n"

        async with self._driver.session(database=self.database) as session:
            result = await session.run(cypher, id=node_id)
            record = await result.single()
            if record is None:
                return None

            node = record["n"]
            return {
                "labels": list(node.labels),
                "properties": dict(node.items()),
            }

    async def is_connected(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if connected, False otherwise.
        """
        if self._driver is None:
            return False

        try:
            await self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning("Neo4j connectivity check failed: %s", e)
            return False

    async def close(self) -> None:
        """
        Close the driver connection and reset the singleton.

        This method is idempotent - calling it multiple times is safe.
        """
        if self._driver is not None:
            await self._driver.close()
            logger.info("Neo4j driver closed")

        Neo4jConnector._driver = None
        Neo4jConnector._instance = None
        Neo4jConnector._config = None


__all__ = ["Neo4jConfig", "Neo4jConnector"]
