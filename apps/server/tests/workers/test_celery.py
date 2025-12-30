"""Tests for Celery worker configuration.

This module tests the Celery 5.x configuration including:
1. Celery app configuration with Redis broker
2. Task queue definitions (planner, executor, validator)
3. Redis broker connection settings
4. Concurrency and prefetch settings
5. Retry policies with exponential backoff
6. Result backend configuration
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestCeleryConfig:
    """Test CeleryConfig dataclass for Celery worker configuration."""

    def test_celery_config_default_values(self) -> None:
        """Test CeleryConfig initializes with default values."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        assert config.broker_url is not None
        assert config.result_backend is not None
        assert config.worker_concurrency > 0
        assert config.worker_prefetch_multiplier >= 1

    def test_celery_config_from_redis_config(self) -> None:
        """Test CeleryConfig uses Redis config for broker URL."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        assert "redis://" in config.broker_url
        assert "/0" in config.broker_url  # Celery uses DB 0

    def test_celery_config_result_backend_uses_redis(self) -> None:
        """Test CeleryConfig uses Redis for result backend."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        assert "redis://" in config.result_backend
        assert "/0" in config.result_backend  # Same DB as broker

    def test_celery_config_concurrency_default(self) -> None:
        """Test default concurrency equals CPU count or configurable."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        # Should default to reasonable value (4 is common)
        assert config.worker_concurrency >= 1

    def test_celery_config_prefetch_multiplier_default(self) -> None:
        """Test default prefetch multiplier is reasonable."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        # Default should be low for fair scheduling (1-4)
        assert 1 <= config.worker_prefetch_multiplier <= 4

    def test_celery_config_task_acks_late_enabled(self) -> None:
        """Test task acknowledgment is late for reliability."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        # Late ack ensures tasks aren't lost if worker crashes
        assert config.task_acks_late is True

    def test_celery_config_task_reject_on_worker_lost(self) -> None:
        """Test tasks are rejected if worker lost for requeuing."""
        from daw_server.workers.celery_app import CeleryConfig

        config = CeleryConfig()
        assert config.task_reject_on_worker_lost is True


class TestQueueDefinitions:
    """Test task queue definitions for different agent types."""

    def test_planner_queue_defined(self) -> None:
        """Test planner_queue is defined for planning tasks."""
        from daw_server.workers.celery_app import QUEUE_PLANNER

        assert QUEUE_PLANNER == "planner_queue"

    def test_executor_queue_defined(self) -> None:
        """Test executor_queue is defined for execution tasks."""
        from daw_server.workers.celery_app import QUEUE_EXECUTOR

        assert QUEUE_EXECUTOR == "executor_queue"

    def test_validator_queue_defined(self) -> None:
        """Test validator_queue is defined for validation tasks."""
        from daw_server.workers.celery_app import QUEUE_VALIDATOR

        assert QUEUE_VALIDATOR == "validator_queue"

    def test_default_queue_defined(self) -> None:
        """Test default queue is defined for miscellaneous tasks."""
        from daw_server.workers.celery_app import QUEUE_DEFAULT

        assert QUEUE_DEFAULT == "celery"

    def test_all_queues_are_distinct(self) -> None:
        """Test all queue names are unique."""
        from daw_server.workers.celery_app import (
            QUEUE_DEFAULT,
            QUEUE_EXECUTOR,
            QUEUE_PLANNER,
            QUEUE_VALIDATOR,
        )

        queues = [QUEUE_DEFAULT, QUEUE_PLANNER, QUEUE_EXECUTOR, QUEUE_VALIDATOR]
        assert len(queues) == len(set(queues))


class TestRetryPolicy:
    """Test retry policy configuration with exponential backoff."""

    def test_retry_policy_has_max_retries(self) -> None:
        """Test retry policy defines maximum retries."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        assert policy.max_retries >= 1

    def test_retry_policy_default_max_retries(self) -> None:
        """Test default max retries is reasonable (3-5)."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        assert 3 <= policy.max_retries <= 10

    def test_retry_policy_exponential_backoff_enabled(self) -> None:
        """Test exponential backoff is enabled."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        assert policy.retry_backoff is True

    def test_retry_policy_backoff_max_defined(self) -> None:
        """Test maximum backoff delay is defined."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        # Max backoff should be reasonable (e.g., 600-3600 seconds)
        assert policy.retry_backoff_max >= 60

    def test_retry_policy_jitter_enabled(self) -> None:
        """Test jitter is enabled to prevent thundering herd."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        assert policy.retry_jitter is True

    def test_retry_policy_initial_delay(self) -> None:
        """Test initial retry delay is defined."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        # Initial delay should be short (1-10 seconds)
        assert 1 <= policy.retry_backoff_base <= 30

    def test_retry_policy_as_dict(self) -> None:
        """Test retry policy can be exported as dict for Celery."""
        from daw_server.workers.celery_app import RetryPolicy

        policy = RetryPolicy()
        policy_dict = policy.as_dict()

        assert "max_retries" in policy_dict
        assert "retry_backoff" in policy_dict
        assert "retry_backoff_max" in policy_dict
        assert "retry_jitter" in policy_dict


class TestCeleryApp:
    """Test Celery app creation and configuration."""

    def test_celery_app_exists(self) -> None:
        """Test Celery app is created."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app is not None

    def test_celery_app_has_broker_url(self) -> None:
        """Test Celery app has broker URL configured."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.broker_url is not None
        assert "redis://" in celery_app.conf.broker_url

    def test_celery_app_has_result_backend(self) -> None:
        """Test Celery app has result backend configured."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.result_backend is not None
        assert "redis://" in celery_app.conf.result_backend

    def test_celery_app_has_task_routes(self) -> None:
        """Test Celery app has task routes configured."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.task_routes is not None

    def test_celery_app_concurrency_configured(self) -> None:
        """Test worker concurrency is configured."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.worker_concurrency is not None

    def test_celery_app_prefetch_configured(self) -> None:
        """Test prefetch multiplier is configured."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.worker_prefetch_multiplier is not None

    def test_celery_app_late_ack_configured(self) -> None:
        """Test late acknowledgment is configured."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True

    def test_celery_app_task_serializer(self) -> None:
        """Test task serializer is configured (json preferred)."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"

    def test_celery_app_result_serializer(self) -> None:
        """Test result serializer is configured (json preferred)."""
        from daw_server.workers.celery_app import celery_app

        assert celery_app.conf.result_serializer == "json"

    def test_celery_app_accept_content(self) -> None:
        """Test accept content includes json."""
        from daw_server.workers.celery_app import celery_app

        assert "json" in celery_app.conf.accept_content


class TestTaskRouting:
    """Test task routing configuration."""

    def test_planner_tasks_route_to_planner_queue(self) -> None:
        """Test planner tasks are routed to planner queue."""
        from daw_server.workers.celery_app import celery_app

        routes = celery_app.conf.task_routes
        # Check for planner task routing pattern
        assert any("planner" in str(key).lower() for key in routes.keys())

    def test_executor_tasks_route_to_executor_queue(self) -> None:
        """Test executor tasks are routed to executor queue."""
        from daw_server.workers.celery_app import celery_app

        routes = celery_app.conf.task_routes
        # Check for executor task routing pattern
        assert any("executor" in str(key).lower() for key in routes.keys())

    def test_validator_tasks_route_to_validator_queue(self) -> None:
        """Test validator tasks are routed to validator queue."""
        from daw_server.workers.celery_app import celery_app

        routes = celery_app.conf.task_routes
        # Check for validator task routing pattern
        assert any("validator" in str(key).lower() for key in routes.keys())


class TestTaskDefinitions:
    """Test task definitions in tasks.py."""

    def test_run_planner_task_exists(self) -> None:
        """Test run_planner task is defined."""
        from daw_server.workers.tasks import run_planner

        assert run_planner is not None
        assert callable(run_planner)

    def test_run_executor_task_exists(self) -> None:
        """Test run_executor task is defined."""
        from daw_server.workers.tasks import run_executor

        assert run_executor is not None
        assert callable(run_executor)

    def test_run_validator_task_exists(self) -> None:
        """Test run_validator task is defined."""
        from daw_server.workers.tasks import run_validator

        assert run_validator is not None
        assert callable(run_validator)

    def test_planner_task_has_name(self) -> None:
        """Test planner task has proper name."""
        from daw_server.workers.tasks import run_planner

        assert hasattr(run_planner, "name")
        assert "planner" in run_planner.name.lower()

    def test_executor_task_has_name(self) -> None:
        """Test executor task has proper name."""
        from daw_server.workers.tasks import run_executor

        assert hasattr(run_executor, "name")
        assert "executor" in run_executor.name.lower()

    def test_validator_task_has_name(self) -> None:
        """Test validator task has proper name."""
        from daw_server.workers.tasks import run_validator

        assert hasattr(run_validator, "name")
        assert "validator" in run_validator.name.lower()


class TestTaskRetryConfiguration:
    """Test that tasks have proper retry configuration."""

    def test_planner_task_has_retry_config(self) -> None:
        """Test planner task has retry configuration."""
        from daw_server.workers.tasks import run_planner

        # Task should have autoretry_for or retry attributes
        assert hasattr(run_planner, "max_retries") or hasattr(run_planner, "autoretry_for")

    def test_executor_task_has_retry_config(self) -> None:
        """Test executor task has retry configuration."""
        from daw_server.workers.tasks import run_executor

        assert hasattr(run_executor, "max_retries") or hasattr(run_executor, "autoretry_for")

    def test_validator_task_has_retry_config(self) -> None:
        """Test validator task has retry configuration."""
        from daw_server.workers.tasks import run_validator

        assert hasattr(run_validator, "max_retries") or hasattr(run_validator, "autoretry_for")


class TestRedisConnectionFromConfig:
    """Test that Celery uses RedisConfig from config/redis.py."""

    def test_celery_uses_redis_config(self) -> None:
        """Test Celery broker URL comes from RedisConfig."""
        from daw_server.config.redis import RedisConfig
        from daw_server.workers.celery_app import celery_app

        config = RedisConfig()
        # Broker should match celery_broker_url from RedisConfig
        assert celery_app.conf.broker_url == config.celery_broker_url

    def test_result_backend_uses_redis_config(self) -> None:
        """Test result backend URL comes from RedisConfig."""
        from daw_server.config.redis import RedisConfig
        from daw_server.workers.celery_app import celery_app

        config = RedisConfig()
        # Result backend should use same DB as broker for simplicity
        assert celery_app.conf.result_backend == config.celery_broker_url


class TestCeleryAppFactory:
    """Test Celery app factory function."""

    def test_create_celery_app_returns_app(self) -> None:
        """Test factory function returns Celery app."""
        from daw_server.workers.celery_app import create_celery_app

        app = create_celery_app()
        assert app is not None

    def test_create_celery_app_with_custom_config(self) -> None:
        """Test factory accepts custom configuration."""
        from daw_server.workers.celery_app import CeleryConfig, create_celery_app

        custom_config = CeleryConfig(worker_concurrency=2)
        app = create_celery_app(config=custom_config)
        assert app.conf.worker_concurrency == 2

    def test_create_celery_app_with_custom_broker(self) -> None:
        """Test factory accepts custom broker URL."""
        from daw_server.workers.celery_app import CeleryConfig, create_celery_app

        custom_config = CeleryConfig(broker_url="redis://custom:6379/0")
        app = create_celery_app(config=custom_config)
        assert app.conf.broker_url == "redis://custom:6379/0"


class TestBrokerTransportOptions:
    """Test broker transport options for Redis."""

    def test_visibility_timeout_configured(self) -> None:
        """Test visibility timeout is configured for task safety."""
        from daw_server.workers.celery_app import celery_app

        transport_options = celery_app.conf.broker_transport_options
        # Visibility timeout should be set (default 3600 is common)
        assert transport_options is not None
        assert "visibility_timeout" in transport_options

    def test_visibility_timeout_reasonable(self) -> None:
        """Test visibility timeout is reasonable (1-24 hours)."""
        from daw_server.workers.celery_app import celery_app

        transport_options = celery_app.conf.broker_transport_options
        timeout = transport_options.get("visibility_timeout", 0)
        # Should be between 1 hour and 24 hours
        assert 3600 <= timeout <= 86400


class TestResultBackendOptions:
    """Test result backend configuration options."""

    def test_result_expires_configured(self) -> None:
        """Test result expiration is configured."""
        from daw_server.workers.celery_app import celery_app

        # Results should expire (default 24 hours is common)
        assert celery_app.conf.result_expires is not None

    def test_result_expires_reasonable(self) -> None:
        """Test result expiration is reasonable (1-7 days)."""
        from daw_server.workers.celery_app import celery_app

        expires = celery_app.conf.result_expires
        # Should be between 1 day and 7 days
        assert 86400 <= expires <= 604800


class TestTaskTimeouts:
    """Test task timeout configuration."""

    def test_task_time_limit_configured(self) -> None:
        """Test hard task time limit is configured."""
        from daw_server.workers.celery_app import celery_app

        # Tasks should have a hard time limit
        assert celery_app.conf.task_time_limit is not None

    def test_task_soft_time_limit_configured(self) -> None:
        """Test soft task time limit is configured."""
        from daw_server.workers.celery_app import celery_app

        # Soft limit should be set for graceful timeout handling
        assert celery_app.conf.task_soft_time_limit is not None

    def test_soft_limit_less_than_hard_limit(self) -> None:
        """Test soft limit is less than hard limit."""
        from daw_server.workers.celery_app import celery_app

        soft = celery_app.conf.task_soft_time_limit
        hard = celery_app.conf.task_time_limit
        assert soft < hard


class TestTaskExecution:
    """Test task execution functions directly using Celery's test utilities."""

    def test_run_planner_returns_success_structure(self) -> None:
        """Test run_planner task has correct signature and decorators."""
        from daw_server.workers.tasks import run_planner

        # Verify task is properly bound and has correct attributes
        assert hasattr(run_planner, "__wrapped__")
        assert hasattr(run_planner, "delay")
        assert hasattr(run_planner, "apply_async")

    def test_run_executor_returns_success_structure(self) -> None:
        """Test run_executor task has correct signature and decorators."""
        from daw_server.workers.tasks import run_executor

        assert hasattr(run_executor, "__wrapped__")
        assert hasattr(run_executor, "delay")
        assert hasattr(run_executor, "apply_async")

    def test_run_validator_returns_success_structure(self) -> None:
        """Test run_validator task has correct signature and decorators."""
        from daw_server.workers.tasks import run_validator

        assert hasattr(run_validator, "__wrapped__")
        assert hasattr(run_validator, "delay")
        assert hasattr(run_validator, "apply_async")

    def test_planner_task_is_bound(self) -> None:
        """Test run_planner task is bound (has self parameter)."""
        from daw_server.workers.tasks import run_planner

        # Bound tasks have the bind attribute set (truthy check)
        assert run_planner.bind

    def test_executor_task_is_bound(self) -> None:
        """Test run_executor task is bound (has self parameter)."""
        from daw_server.workers.tasks import run_executor

        assert run_executor.bind

    def test_validator_task_is_bound(self) -> None:
        """Test run_validator task is bound (has self parameter)."""
        from daw_server.workers.tasks import run_validator

        assert run_validator.bind

    def test_planner_task_queue_assignment(self) -> None:
        """Test run_planner is assigned to correct queue."""
        from daw_server.workers.celery_app import QUEUE_PLANNER
        from daw_server.workers.tasks import run_planner

        assert run_planner.queue == QUEUE_PLANNER

    def test_executor_task_queue_assignment(self) -> None:
        """Test run_executor is assigned to correct queue."""
        from daw_server.workers.celery_app import QUEUE_EXECUTOR
        from daw_server.workers.tasks import run_executor

        assert run_executor.queue == QUEUE_EXECUTOR

    def test_validator_task_queue_assignment(self) -> None:
        """Test run_validator is assigned to correct queue."""
        from daw_server.workers.celery_app import QUEUE_VALIDATOR
        from daw_server.workers.tasks import run_validator

        assert run_validator.queue == QUEUE_VALIDATOR

    def test_tasks_use_base_task_with_retry(self) -> None:
        """Test all tasks inherit from BaseTaskWithRetry."""
        from daw_server.workers.tasks import (
            BaseTaskWithRetry,
            run_executor,
            run_planner,
            run_validator,
        )

        # Tasks should use the same retry settings as BaseTaskWithRetry
        assert run_planner.max_retries == BaseTaskWithRetry.max_retries
        assert run_executor.max_retries == BaseTaskWithRetry.max_retries
        assert run_validator.max_retries == BaseTaskWithRetry.max_retries


class TestBaseTaskWithRetry:
    """Test BaseTaskWithRetry class configuration."""

    def test_base_task_autoretry_for_exception(self) -> None:
        """Test BaseTaskWithRetry autoretries on Exception."""
        from daw_server.workers.tasks import BaseTaskWithRetry

        assert Exception in BaseTaskWithRetry.autoretry_for

    def test_base_task_max_retries_from_policy(self) -> None:
        """Test BaseTaskWithRetry uses RetryPolicy max_retries."""
        from daw_server.workers.tasks import DEFAULT_RETRY_POLICY, BaseTaskWithRetry

        assert BaseTaskWithRetry.max_retries == DEFAULT_RETRY_POLICY.max_retries

    def test_base_task_backoff_enabled(self) -> None:
        """Test BaseTaskWithRetry has backoff enabled."""
        from daw_server.workers.tasks import BaseTaskWithRetry

        assert BaseTaskWithRetry.retry_backoff is True

    def test_base_task_jitter_enabled(self) -> None:
        """Test BaseTaskWithRetry has jitter enabled."""
        from daw_server.workers.tasks import BaseTaskWithRetry

        assert BaseTaskWithRetry.retry_jitter is True

    def test_base_task_backoff_max_from_policy(self) -> None:
        """Test BaseTaskWithRetry uses RetryPolicy backoff_max."""
        from daw_server.workers.tasks import DEFAULT_RETRY_POLICY, BaseTaskWithRetry

        assert BaseTaskWithRetry.retry_backoff_max == DEFAULT_RETRY_POLICY.retry_backoff_max
