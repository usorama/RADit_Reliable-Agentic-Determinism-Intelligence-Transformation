"""Celery task definitions for DAW agent workflows.

This module defines Celery tasks for:
1. run_planner - Execute planner/taskmaster agent workflow
2. run_executor - Execute developer agent workflow
3. run_validator - Execute validator agent workflow

Each task is configured with:
- Appropriate queue routing
- Retry policy with exponential backoff
- Proper error handling
"""

from typing import Any

from celery import Task
from celery.utils.log import get_task_logger

from daw_agents.workers.celery_app import (
    QUEUE_EXECUTOR,
    QUEUE_PLANNER,
    QUEUE_VALIDATOR,
    RetryPolicy,
    celery_app,
)

# Configure task logger
logger = get_task_logger(__name__)

# Default retry policy for all tasks
DEFAULT_RETRY_POLICY = RetryPolicy()


class BaseTaskWithRetry(Task):
    """Base task class with exponential backoff retry configuration.

    This class provides common retry configuration for all DAW agent tasks:
    - autoretry_for: Exceptions to retry on
    - max_retries: Maximum retry attempts
    - retry_backoff: Exponential backoff enabled
    - retry_backoff_max: Maximum backoff delay
    - retry_jitter: Add randomness to prevent thundering herd
    """

    autoretry_for = (Exception,)
    max_retries = DEFAULT_RETRY_POLICY.max_retries
    retry_backoff = DEFAULT_RETRY_POLICY.retry_backoff
    retry_backoff_max = DEFAULT_RETRY_POLICY.retry_backoff_max
    retry_jitter = DEFAULT_RETRY_POLICY.retry_jitter


@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="daw_agents.workers.tasks.run_planner",
    queue=QUEUE_PLANNER,
)
def run_planner(
    self: Task,
    task_id: str,
    input_data: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute planner/taskmaster agent workflow.

    This task runs the planner agent to:
    - Analyze user requirements
    - Generate PRD documents
    - Decompose tasks with dependencies
    - Prioritize and schedule work

    Args:
        self: Bound task instance for retry access.
        task_id: Unique identifier for the planning task.
        input_data: Input data including user requirements and context.
        options: Optional configuration for the planner agent.

    Returns:
        Dictionary containing:
        - task_id: The task identifier
        - status: "success" or "error"
        - result: Planning output (PRD, tasks, etc.)
        - metadata: Execution metadata (duration, model used, etc.)

    Raises:
        Exception: Any error during planning is retried with exponential backoff.

    Example:
        >>> result = run_planner.delay(
        ...     task_id="plan-001",
        ...     input_data={"requirements": "Build a REST API"},
        ... )
    """
    logger.info(f"Starting planner task: {task_id}")

    try:
        # Placeholder for actual planner agent integration
        # In production, this would call:
        # from daw_agents.agents.planner import Taskmaster
        # taskmaster = Taskmaster(...)
        # result = await taskmaster.run(input_data)

        result = {
            "task_id": task_id,
            "status": "success",
            "result": {
                "prd_generated": True,
                "tasks_count": 0,
                "input_processed": bool(input_data),
            },
            "metadata": {
                "agent": "planner",
                "attempt": self.request.retries + 1,
            },
        }

        logger.info(f"Planner task completed: {task_id}")
        return result

    except Exception as exc:
        logger.error(f"Planner task failed: {task_id}, error: {exc}")
        raise


@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="daw_agents.workers.tasks.run_executor",
    queue=QUEUE_EXECUTOR,
)
def run_executor(
    self: Task,
    task_id: str,
    input_data: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute developer agent workflow.

    This task runs the executor/developer agent to:
    - Write tests following TDD workflow
    - Implement code changes
    - Run code in sandbox environment
    - Refactor and improve code

    Args:
        self: Bound task instance for retry access.
        task_id: Unique identifier for the execution task.
        input_data: Input data including task specification and context.
        options: Optional configuration for the executor agent.

    Returns:
        Dictionary containing:
        - task_id: The task identifier
        - status: "success" or "error"
        - result: Execution output (code, test results, etc.)
        - metadata: Execution metadata (duration, model used, etc.)

    Raises:
        Exception: Any error during execution is retried with exponential backoff.

    Example:
        >>> result = run_executor.delay(
        ...     task_id="exec-001",
        ...     input_data={"task": "Implement user authentication"},
        ... )
    """
    logger.info(f"Starting executor task: {task_id}")

    try:
        # Placeholder for actual executor agent integration
        # In production, this would call:
        # from daw_agents.agents.developer import Developer
        # developer = Developer(...)
        # result = await developer.run(input_data)

        result = {
            "task_id": task_id,
            "status": "success",
            "result": {
                "code_generated": True,
                "tests_passed": True,
                "input_processed": bool(input_data),
            },
            "metadata": {
                "agent": "executor",
                "attempt": self.request.retries + 1,
            },
        }

        logger.info(f"Executor task completed: {task_id}")
        return result

    except Exception as exc:
        logger.error(f"Executor task failed: {task_id}, error: {exc}")
        raise


@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="daw_agents.workers.tasks.run_validator",
    queue=QUEUE_VALIDATOR,
)
def run_validator(
    self: Task,
    task_id: str,
    input_data: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute validator agent workflow.

    This task runs the validator agent to:
    - Review code changes
    - Run validation checks
    - Cross-validate with different models
    - Generate validation reports

    Args:
        self: Bound task instance for retry access.
        task_id: Unique identifier for the validation task.
        input_data: Input data including code and context to validate.
        options: Optional configuration for the validator agent.

    Returns:
        Dictionary containing:
        - task_id: The task identifier
        - status: "success" or "error"
        - result: Validation output (issues, score, etc.)
        - metadata: Execution metadata (duration, model used, etc.)

    Raises:
        Exception: Any error during validation is retried with exponential backoff.

    Example:
        >>> result = run_validator.delay(
        ...     task_id="val-001",
        ...     input_data={"code": "def hello(): pass", "tests": "..."},
        ... )
    """
    logger.info(f"Starting validator task: {task_id}")

    try:
        # Placeholder for actual validator agent integration
        # In production, this would call:
        # from daw_agents.agents.validator import Validator
        # validator = Validator(...)
        # result = await validator.run(input_data)

        result = {
            "task_id": task_id,
            "status": "success",
            "result": {
                "validation_passed": True,
                "issues_found": 0,
                "input_processed": bool(input_data),
            },
            "metadata": {
                "agent": "validator",
                "attempt": self.request.retries + 1,
            },
        }

        logger.info(f"Validator task completed: {task_id}")
        return result

    except Exception as exc:
        logger.error(f"Validator task failed: {task_id}, error: {exc}")
        raise
