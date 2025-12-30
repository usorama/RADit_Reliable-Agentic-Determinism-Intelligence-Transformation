"""
Model Router for DAW Agent Workbench.

This module implements:
- TaskType enum for categorizing agent tasks
- ModelRouter class for task-based model selection
- Fallback logic when primary model fails
- Helicone integration for cost tracking

Based on FR-01.1: Router Mode selects models based on task type:
- Planning tasks: o1/Claude Opus (high reasoning)
- Coding tasks: Claude Sonnet/GPT-4o (balanced)
- Validation tasks: GPT-4o (MUST be different from executor model)
- Fast tasks: Claude Haiku/GPT-4o-mini (speed)

Critical Architecture Decision:
The Validator Agent MUST use a different model than the Executor Agent
to ensure cross-validation and avoid model-specific blind spots.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from litellm import acompletion

from daw_agents.models.providers import (
    ModelConfig,
    get_default_configs,
    get_helicone_config,
)

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task types for model routing.

    Each task type maps to different model requirements:
    - PLANNING: High reasoning capability (o1, opus)
    - CODING: Balanced performance (sonnet, gpt-4o)
    - VALIDATION: Cross-validation (MUST differ from CODING)
    - FAST: Speed-optimized (haiku, gpt-4o-mini)
    """

    PLANNING = "planning"
    CODING = "coding"
    VALIDATION = "validation"
    FAST = "fast"


class ModelRouter:
    """Routes LLM requests to appropriate models based on task type.

    The router implements:
    1. Task-based model selection
    2. Automatic fallback when primary model fails
    3. Helicone integration for cost tracking
    4. Cross-validation principle (validator != executor model)

    Example:
        ```python
        router = ModelRouter()

        # Route a planning task to high-reasoning model
        result = await router.route(
            task_type=TaskType.PLANNING,
            messages=[{"role": "user", "content": "Create a PRD for a todo app"}],
        )

        # Get model for a specific task type
        model = router.get_model_for_task(TaskType.CODING)
        ```
    """

    def __init__(
        self,
        configs: dict[TaskType, ModelConfig] | None = None,
    ) -> None:
        """Initialize the ModelRouter.

        Args:
            configs: Optional custom configs. If None, uses defaults from environment.
        """
        self.configs = configs or get_default_configs()
        self._helicone_config = get_helicone_config()
        self._validate_cross_validation_principle()

    def _validate_cross_validation_principle(self) -> None:
        """Validate that validation model differs from coding model.

        This is a CRITICAL architectural requirement to ensure:
        - No model-specific blind spots in validation
        - True cross-validation between executor and validator
        """
        coding_model = self.configs[TaskType.CODING].primary
        validation_model = self.configs[TaskType.VALIDATION].primary

        if coding_model == validation_model:
            logger.warning(
                "CRITICAL: Validation model (%s) should differ from coding model (%s) "
                "for proper cross-validation. Consider updating MODEL_VALIDATION env var.",
                validation_model,
                coding_model,
            )

    def get_model_for_task(self, task_type: TaskType) -> str:
        """Get the primary model identifier for a given task type.

        Args:
            task_type: The type of task to get the model for

        Returns:
            Model identifier string (e.g., "claude-3-5-sonnet-20241022")
        """
        return self.configs[task_type].primary

    def get_config_for_task(self, task_type: TaskType) -> ModelConfig:
        """Get the full configuration for a given task type.

        Args:
            task_type: The type of task to get configuration for

        Returns:
            ModelConfig with primary, fallback, max_tokens, temperature
        """
        return self.configs[task_type]

    def _build_request_params(
        self,
        task_type: TaskType,
        messages: list[dict[str, str]],
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build request parameters for LiteLLM.

        Args:
            task_type: The task type for this request
            messages: Chat messages
            model: Model identifier to use
            metadata: Optional metadata for tracking

        Returns:
            Dictionary of parameters for acompletion call
        """
        config = self.configs[task_type]

        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        # Build metadata for tracking
        request_metadata = metadata.copy() if metadata else {}
        request_metadata["task_type"] = task_type.value

        # Add Helicone integration if configured
        if self._helicone_config.api_key:
            # Use extra_headers for Helicone
            extra_headers = {
                "Helicone-Auth": f"Bearer {self._helicone_config.api_key}",
                "Helicone-Retry-Enabled": "true",
                "helicone-retry-num": "3",
                "helicone-retry-factor": "2",
            }

            # Add custom properties for tracking
            if request_metadata:
                extra_headers["Helicone-Property-TaskType"] = task_type.value
                if "user_id" in request_metadata:
                    extra_headers["Helicone-Property-UserId"] = request_metadata[
                        "user_id"
                    ]
                if "project_id" in request_metadata:
                    extra_headers["Helicone-Property-ProjectId"] = request_metadata[
                        "project_id"
                    ]

            params["extra_headers"] = extra_headers

            # Set API base to Helicone proxy for OpenAI models
            if model.startswith("gpt") or model.startswith("o1"):
                params["api_base"] = self._helicone_config.api_base

        # Always include metadata for tracking
        params["metadata"] = request_metadata

        return params

    async def route(
        self,
        task_type: TaskType,
        messages: list[dict[str, str]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Route a request to the appropriate model based on task type.

        Implements automatic fallback: if the primary model fails,
        the request is retried with the fallback model.

        Args:
            task_type: The type of task (planning, coding, validation, fast)
            messages: Chat messages in OpenAI format
            metadata: Optional metadata for tracking (user_id, project_id, etc.)

        Returns:
            String response from the model

        Raises:
            Exception: If both primary and fallback models fail
        """
        config = self.configs[task_type]

        # Try primary model first
        try:
            logger.debug(
                "Routing %s task to primary model: %s",
                task_type.value,
                config.primary,
            )

            params = self._build_request_params(
                task_type=task_type,
                messages=messages,
                model=config.primary,
                metadata=metadata,
            )

            response = await acompletion(**params)
            return str(response.choices[0].message.content)

        except Exception as primary_error:
            logger.warning(
                "Primary model %s failed for %s task: %s. Trying fallback %s",
                config.primary,
                task_type.value,
                str(primary_error),
                config.fallback,
            )

            # Try fallback model
            try:
                params = self._build_request_params(
                    task_type=task_type,
                    messages=messages,
                    model=config.fallback,
                    metadata=metadata,
                )

                response = await acompletion(**params)
                return str(response.choices[0].message.content)

            except Exception as fallback_error:
                logger.error(
                    "Fallback model %s also failed for %s task: %s",
                    config.fallback,
                    task_type.value,
                    str(fallback_error),
                )
                # Re-raise the original error (more informative)
                raise primary_error from fallback_error

    async def route_with_retry(
        self,
        task_type: TaskType,
        messages: list[dict[str, str]],
        metadata: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> str:
        """Route a request with additional retry logic.

        This method provides extra resilience for critical operations
        by retrying the full fallback sequence multiple times.

        Args:
            task_type: The type of task
            messages: Chat messages
            metadata: Optional metadata for tracking
            max_retries: Maximum number of retry attempts

        Returns:
            String response from the model

        Raises:
            Exception: If all retry attempts fail
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                return await self.route(
                    task_type=task_type,
                    messages=messages,
                    metadata=metadata,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Attempt %d/%d failed for %s task: %s",
                    attempt + 1,
                    max_retries,
                    task_type.value,
                    str(e),
                )

        if last_error:
            raise last_error
        raise RuntimeError("Unexpected error in route_with_retry")
