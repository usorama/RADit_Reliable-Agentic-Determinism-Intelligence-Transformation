"""
DAW Agent Models Module.

This module provides model routing and configuration for the agent workbench:
- TaskType: Enum for categorizing agent tasks
- ModelRouter: Routes requests to appropriate models based on task type
- ModelConfig: Configuration for per-task-type model settings
- ModelProvider: Supported LLM providers

Usage:
    ```python
    from daw_agents.models import ModelRouter, TaskType

    router = ModelRouter()
    response = await router.route(
        task_type=TaskType.PLANNING,
        messages=[{"role": "user", "content": "Create a PRD"}]
    )
    ```
"""

from daw_agents.models.providers import (
    ModelConfig,
    ModelProvider,
    ProviderConfig,
    get_default_configs,
    get_helicone_config,
)
from daw_agents.models.router import ModelRouter, TaskType

__all__ = [
    "ModelConfig",
    "ModelProvider",
    "ModelRouter",
    "ProviderConfig",
    "TaskType",
    "get_default_configs",
    "get_helicone_config",
]
