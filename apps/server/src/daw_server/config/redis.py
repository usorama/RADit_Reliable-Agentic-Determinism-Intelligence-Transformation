"""Redis configuration for Celery and caching."""

import os


class RedisConfig:
    """Configuration for Redis connections.

    Attributes:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        password: Redis password (default: empty)
        db: Redis database number (default: 0)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        password: str | None = None,
        db: int | None = None,
    ) -> None:
        """Initialize Redis configuration.

        Args:
            host: Redis host (defaults to REDIS_HOST env var or localhost)
            port: Redis port (defaults to REDIS_PORT env var or 6379)
            password: Redis password (defaults to REDIS_PASSWORD env var or empty)
            db: Redis database (defaults to REDIS_DB env var or 0)
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD", "")
        self.db = db or int(os.getenv("REDIS_DB", "0"))

    @property
    def url(self) -> str:
        """Get Redis URL for general connections.

        Returns:
            Redis URL in format redis://[:password@]host:port/db
        """
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"

    @property
    def celery_broker_url(self) -> str:
        """Get Redis URL for Celery broker.

        Returns:
            Redis URL for Celery broker
        """
        return self.url

    @property
    def celery_result_backend(self) -> str:
        """Get Redis URL for Celery result backend.

        Returns:
            Redis URL for Celery result backend
        """
        return self.url
