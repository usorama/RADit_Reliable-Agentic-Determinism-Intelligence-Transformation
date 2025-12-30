"""Celery workers for background task processing.

This package provides:
- CeleryConfig: Configuration dataclass for Celery workers
- celery_app: Pre-configured Celery application instance
- create_celery_app: Factory function for creating Celery apps
- Task definitions for planner, executor, and validator agents
- Queue constants for task routing
- RetryPolicy: Configuration for exponential backoff retry
"""

from daw_agents.workers.celery_app import (
    QUEUE_DEFAULT,
    QUEUE_EXECUTOR,
    QUEUE_PLANNER,
    QUEUE_VALIDATOR,
    CeleryConfig,
    RetryPolicy,
    celery_app,
    create_celery_app,
)
from daw_agents.workers.tasks import run_executor, run_planner, run_validator

__all__ = [
    # Configuration
    "CeleryConfig",
    "RetryPolicy",
    # Queue constants
    "QUEUE_DEFAULT",
    "QUEUE_PLANNER",
    "QUEUE_EXECUTOR",
    "QUEUE_VALIDATOR",
    # Celery app
    "celery_app",
    "create_celery_app",
    # Tasks
    "run_planner",
    "run_executor",
    "run_validator",
]
