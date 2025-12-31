"""Neo4j database connection management.

This module provides async Neo4j connection with:
- Environment variable configuration (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
- Async driver with connection pooling
- Health check method
- Proper cleanup on shutdown
"""

import logging
import os
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Async Neo4j database connection manager.

    Provides connection pooling, health checks, and lifecycle management
    for Neo4j database connections.

    Configuration via environment variables:
    - NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    - NEO4J_USER: Database username (default: neo4j)
    - NEO4J_PASSWORD: Database password (default: password)
    - NEO4J_DATABASE: Database name (default: neo4j)
    - NEO4J_MAX_CONNECTION_POOL_SIZE: Max connections (default: 50)
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        max_connection_pool_size: int | None = None,
    ) -> None:
        """Initialize Neo4j connection manager.

        Args:
            uri: Neo4j connection URI (overrides NEO4J_URI env var)
            user: Database username (overrides NEO4J_USER env var)
            password: Database password (overrides NEO4J_PASSWORD env var)
            database: Database name (overrides NEO4J_DATABASE env var)
            max_connection_pool_size: Max pool size (overrides NEO4J_MAX_CONNECTION_POOL_SIZE)
        """
        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.getenv("NEO4J_USER", "neo4j")
        self._password = password or os.getenv("NEO4J_PASSWORD", "password")
        self._database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self._max_pool_size = max_connection_pool_size or int(
            os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50")
        )
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j database.

        Creates the async driver with connection pooling.

        Raises:
            AuthError: If authentication fails
            ServiceUnavailable: If Neo4j service is not reachable
        """
        if self._driver is not None:
            return

        logger.info("Connecting to Neo4j at %s", self._uri)
        self._driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
            max_connection_pool_size=self._max_pool_size,
        )

        # Verify connectivity
        await self.health_check()
        logger.info("Successfully connected to Neo4j")

    async def close(self) -> None:
        """Close the Neo4j connection.

        Properly closes the driver and releases all connections.
        """
        if self._driver is not None:
            logger.info("Closing Neo4j connection")
            await self._driver.close()
            self._driver = None

    async def health_check(self) -> dict[str, Any]:
        """Check Neo4j connection health.

        Returns:
            Dictionary with health status including:
            - healthy: bool indicating connection status
            - uri: The configured URI
            - database: The configured database
            - error: Error message if unhealthy

        Raises:
            RuntimeError: If driver is not initialized
        """
        if self._driver is None:
            return {
                "healthy": False,
                "uri": self._uri,
                "database": self._database,
                "error": "Driver not initialized",
            }

        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run("RETURN 1 as health")
                record = await result.single()
                if record and record["health"] == 1:
                    return {
                        "healthy": True,
                        "uri": self._uri,
                        "database": self._database,
                    }
                return {
                    "healthy": False,
                    "uri": self._uri,
                    "database": self._database,
                    "error": "Unexpected health check result",
                }
        except ServiceUnavailable as e:
            logger.error("Neo4j service unavailable: %s", str(e))
            return {
                "healthy": False,
                "uri": self._uri,
                "database": self._database,
                "error": f"Service unavailable: {e}",
            }
        except AuthError as e:
            logger.error("Neo4j authentication failed: %s", str(e))
            return {
                "healthy": False,
                "uri": self._uri,
                "database": self._database,
                "error": f"Authentication failed: {e}",
            }
        except Exception as e:
            logger.error("Neo4j health check failed: %s", str(e))
            return {
                "healthy": False,
                "uri": self._uri,
                "database": self._database,
                "error": str(e),
            }

    @property
    def driver(self) -> AsyncDriver:
        """Get the Neo4j async driver.

        Returns:
            The AsyncDriver instance

        Raises:
            RuntimeError: If driver is not initialized (connect not called)
        """
        if self._driver is None:
            raise RuntimeError(
                "Neo4j driver not initialized. Call connect() first."
            )
        return self._driver

    @property
    def database(self) -> str:
        """Get the configured database name."""
        return self._database

    async def __aenter__(self) -> "Neo4jConnection":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.close()


# Global connection instance (initialized at app startup)
_neo4j_connection: Neo4jConnection | None = None


def get_neo4j_connection() -> Neo4jConnection:
    """Get the global Neo4j connection instance.

    Returns:
        The global Neo4jConnection instance

    Raises:
        RuntimeError: If connection not initialized
    """
    global _neo4j_connection
    if _neo4j_connection is None:
        raise RuntimeError(
            "Neo4j connection not initialized. Call init_neo4j() at app startup."
        )
    return _neo4j_connection


async def init_neo4j(
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> Neo4jConnection:
    """Initialize the global Neo4j connection.

    Should be called at application startup.

    Args:
        uri: Neo4j connection URI
        user: Database username
        password: Database password
        database: Database name

    Returns:
        The initialized Neo4jConnection instance
    """
    global _neo4j_connection
    _neo4j_connection = Neo4jConnection(
        uri=uri,
        user=user,
        password=password,
        database=database,
    )
    await _neo4j_connection.connect()
    return _neo4j_connection


async def close_neo4j() -> None:
    """Close the global Neo4j connection.

    Should be called at application shutdown.
    """
    global _neo4j_connection
    if _neo4j_connection is not None:
        await _neo4j_connection.close()
        _neo4j_connection = None


__all__ = [
    "Neo4jConnection",
    "get_neo4j_connection",
    "init_neo4j",
    "close_neo4j",
]
