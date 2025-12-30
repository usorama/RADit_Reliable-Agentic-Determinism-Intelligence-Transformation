"""Celery application configuration for background task processing.

This module provides:
1. CeleryConfig - Configuration dataclass for Celery workers
2. RetryPolicy - Configuration for exponential backoff retry
3. celery_app - Pre-configured Celery application instance
4. create_celery_app - Factory function for creating Celery apps

Architecture:
- Uses Redis as broker (from config/redis.py)
- Uses Redis as result backend
- Defines queues for planner, executor, and validator agents
- Configures exponential backoff retry policies
"""

import os
from dataclasses import dataclass, field
from typing import Any

from celery import Celery

from daw_agents.config.redis import RedisConfig

# Queue constants for task routing
QUEUE_DEFAULT = "celery"
QUEUE_PLANNER = "planner_queue"
QUEUE_EXECUTOR = "executor_queue"
QUEUE_VALIDATOR = "validator_queue"


@dataclass
class RetryPolicy:
    """Configuration for task retry with exponential backoff.

    This dataclass defines retry behavior for Celery tasks including:
    - Maximum number of retries
    - Exponential backoff settings
    - Jitter to prevent thundering herd

    Attributes:
        max_retries: Maximum number of retry attempts (default: 5)
        retry_backoff: Enable exponential backoff (default: True)
        retry_backoff_base: Base delay in seconds for backoff (default: 2)
        retry_backoff_max: Maximum backoff delay in seconds (default: 600)
        retry_jitter: Add randomness to backoff (default: True)
    """

    max_retries: int = 5
    retry_backoff: bool = True
    retry_backoff_base: int = 2
    retry_backoff_max: int = 600
    retry_jitter: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Export retry policy as dict for Celery task configuration.

        Returns:
            Dictionary with retry policy settings.
        """
        return {
            "max_retries": self.max_retries,
            "retry_backoff": self.retry_backoff,
            "retry_backoff_max": self.retry_backoff_max,
            "retry_jitter": self.retry_jitter,
        }


@dataclass
class CeleryConfig:
    """Configuration for Celery workers.

    This dataclass manages Celery configuration including:
    - Broker URL (from RedisConfig)
    - Result backend
    - Worker concurrency and prefetch settings
    - Task acknowledgment settings
    - Serialization settings

    Attributes:
        broker_url: Redis broker URL (from RedisConfig)
        result_backend: Redis result backend URL
        worker_concurrency: Number of concurrent worker processes
        worker_prefetch_multiplier: Prefetch multiplier per worker
        task_acks_late: Acknowledge tasks after execution (default: True)
        task_reject_on_worker_lost: Reject tasks if worker is lost (default: True)
        task_serializer: Serializer for tasks (default: "json")
        result_serializer: Serializer for results (default: "json")
        accept_content: Accepted content types (default: ["json"])
        result_expires: Result expiration in seconds (default: 86400 = 24h)
        task_time_limit: Hard time limit in seconds (default: 3600 = 1h)
        task_soft_time_limit: Soft time limit in seconds (default: 3300 = 55min)
        visibility_timeout: Broker visibility timeout (default: 43200 = 12h)
    """

    broker_url: str = ""
    result_backend: str = ""
    worker_concurrency: int = 0
    worker_prefetch_multiplier: int = 2
    task_acks_late: bool = True
    task_reject_on_worker_lost: bool = True
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: list[str] = field(default_factory=lambda: ["json"])
    result_expires: int = 86400  # 24 hours
    task_time_limit: int = 3600  # 1 hour hard limit
    task_soft_time_limit: int = 3300  # 55 minutes soft limit
    visibility_timeout: int = 43200  # 12 hours

    def __post_init__(self) -> None:
        """Initialize values from RedisConfig and environment if not provided."""
        redis_config = RedisConfig()

        if not self.broker_url:
            self.broker_url = redis_config.celery_broker_url

        if not self.result_backend:
            self.result_backend = redis_config.celery_broker_url

        if self.worker_concurrency == 0:
            # Default to 4 or CPU count from environment
            env_concurrency = os.getenv("CELERY_WORKER_CONCURRENCY")
            if env_concurrency:
                self.worker_concurrency = int(env_concurrency)
            else:
                self.worker_concurrency = 4


def create_celery_app(
    name: str = "daw_agents",
    config: CeleryConfig | None = None,
) -> Celery:
    """Create and configure a Celery application.

    Factory function that creates a Celery app with proper configuration
    for the DAW agents workbench.

    Args:
        name: Name of the Celery application.
        config: Optional CeleryConfig instance. If not provided,
                uses default configuration from RedisConfig.

    Returns:
        Configured Celery application instance.

    Example:
        >>> app = create_celery_app()
        >>> app.conf.broker_url
        'redis://localhost:6379/0'
    """
    if config is None:
        config = CeleryConfig()

    app = Celery(name)

    # Configure broker and backend
    app.conf.broker_url = config.broker_url
    app.conf.result_backend = config.result_backend

    # Configure worker settings
    app.conf.worker_concurrency = config.worker_concurrency
    app.conf.worker_prefetch_multiplier = config.worker_prefetch_multiplier

    # Configure task acknowledgment
    app.conf.task_acks_late = config.task_acks_late
    app.conf.task_reject_on_worker_lost = config.task_reject_on_worker_lost

    # Configure serialization
    app.conf.task_serializer = config.task_serializer
    app.conf.result_serializer = config.result_serializer
    app.conf.accept_content = config.accept_content

    # Configure result expiration
    app.conf.result_expires = config.result_expires

    # Configure timeouts
    app.conf.task_time_limit = config.task_time_limit
    app.conf.task_soft_time_limit = config.task_soft_time_limit

    # Configure broker transport options
    app.conf.broker_transport_options = {
        "visibility_timeout": config.visibility_timeout,
    }

    # Configure task routes
    app.conf.task_routes = {
        "daw_agents.workers.tasks.run_planner": {"queue": QUEUE_PLANNER},
        "daw_agents.workers.tasks.run_executor": {"queue": QUEUE_EXECUTOR},
        "daw_agents.workers.tasks.run_validator": {"queue": QUEUE_VALIDATOR},
    }

    # Auto-discover tasks
    app.autodiscover_tasks(["daw_agents.workers"])

    return app


# Create the default Celery app instance
celery_app = create_celery_app()
