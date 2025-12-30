"""Redis configuration for dual-purpose: Celery broker + LangGraph checkpoints.

This module provides:
1. RedisConfig - Configuration dataclass for Redis connections
2. get_redis_client() - Factory for synchronous Redis client
3. get_async_redis_client() - Factory for asynchronous Redis client

Architecture:
- Database 0: Celery message broker (task queue)
- Database 1: LangGraph checkpoint persistence (state recovery)

Both purposes use the same Redis instance but separate logical databases
to prevent key collisions and enable independent management.
"""

import os
from dataclasses import dataclass
from typing import Optional

try:
    from redis import Redis
    from redis.asyncio import Redis as AsyncRedis
except ImportError:
    raise ImportError(
        "redis package not found. Install with: pip install redis"
    )


@dataclass
class RedisConfig:
    """Redis connection configuration for dual-purpose use.

    This dataclass manages Redis configuration for both:
    - Celery broker (message queue for background tasks)
    - LangGraph checkpoints (state persistence for agent workflows)

    Attributes:
        host: Redis server hostname (default: localhost)
        port: Redis server port (default: 6379)
        password: Redis authentication password (default: None)
        db_celery: Database number for Celery broker (default: 0)
        db_langgraph: Database number for LangGraph checkpoints (default: 1)
    """

    host: str = ""
    port: int = 0
    password: Optional[str] = None
    db_celery: int = 0
    db_langgraph: int = 1

    def __post_init__(self) -> None:
        """Initialize values from environment if not provided."""
        if not self.host:
            self.host = os.getenv("REDIS_HOST", "localhost")
        if self.port == 0:
            self.port = int(os.getenv("REDIS_PORT", "6379"))
        if self.password is None:
            self.password = os.getenv("REDIS_PASSWORD")

    @property
    def celery_broker_url(self) -> str:
        """Generate Celery broker connection URL.

        Returns:
            Redis URL for Celery broker configuration.
            Format: redis://[password@]host:port/db_number

        Example:
            redis://localhost:6379/0
            redis://:secret@redis.example.com:6379/0
        """
        auth: str = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db_celery}"

    @property
    def langgraph_url(self) -> str:
        """Generate LangGraph checkpoint connection URL.

        Returns:
            Redis URL for LangGraph checkpoint persistence.
            Format: redis://[password@]host:port/db_number

        Example:
            redis://localhost:6379/1
            redis://:secret@redis.example.com:6379/1
        """
        auth: str = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db_langgraph}"


def get_redis_client(db: int = 0) -> Redis:
    """Get synchronous Redis client.

    Creates a synchronous Redis client for blocking operations.
    Decodes responses to strings for easier handling.

    Args:
        db: Redis database number to connect to (default: 0)

    Returns:
        Configured Redis client instance

    Raises:
        ImportError: If redis package is not installed
        ConnectionError: If Redis server is not available

    Example:
        >>> client = get_redis_client(db=0)
        >>> client.set("key", "value")
        >>> value = client.get("key")
    """
    config = RedisConfig()
    return Redis(
        host=config.host,
        port=config.port,
        password=config.password,
        db=db,
        decode_responses=True,
    )


async def get_async_redis_client(db: int = 0) -> AsyncRedis:
    """Get asynchronous Redis client.

    Creates an asynchronous Redis client for non-blocking operations
    in async contexts. Decodes responses to strings for easier handling.

    Args:
        db: Redis database number to connect to (default: 0)

    Returns:
        Configured async Redis client instance

    Raises:
        ImportError: If redis package is not installed
        ConnectionError: If Redis server is not available

    Example:
        >>> client = await get_async_redis_client(db=0)
        >>> await client.set("key", "value")
        >>> value = await client.get("key")
        >>> await client.close()
    """
    config = RedisConfig()
    return await AsyncRedis(
        host=config.host,
        port=config.port,
        password=config.password,
        db=db,
        decode_responses=True,
    )
