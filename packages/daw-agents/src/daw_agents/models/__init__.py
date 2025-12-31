"""
DAW Agent Models Module.

This module provides model routing and LLM driver abstraction for the agent workbench:

Core Components:
- ModelDriver: Abstract interface for LLM providers (FR-10.1.1)
- ClaudeDriver, OpenAIDriver, GeminiDriver, LocalDriver: Provider implementations
- DriverRegistry: Config-based driver selection (FR-10.1.3)
- ModelRouter: Routes requests to appropriate models based on task type

Design Principle:
    LLM as stateless reasoning unit, system as the OS.
    Drivers can be swapped without code changes (FR-10.1.4).

Usage:
    ```python
    # Using drivers directly (agnostic approach)
    from daw_agents.models import DriverRegistry

    driver = DriverRegistry.get_driver()  # Uses DAW_MODEL_DRIVER env var
    response = await driver.complete(
        messages=[{"role": "user", "content": "Hello"}],
        model="claude-3-5-sonnet-20241022",
    )

    # Using ModelRouter (task-based routing)
    from daw_agents.models import ModelRouter, TaskType

    router = ModelRouter()
    response = await router.route(
        task_type=TaskType.PLANNING,
        messages=[{"role": "user", "content": "Create a PRD"}]
    )
    ```
"""

from daw_agents.models.drivers import (
    ClaudeDriver,
    CompletionResponse,
    DriverRegistry,
    DriverType,
    DriverWithFallback,
    GeminiDriver,
    LocalDriver,
    ModelDriver,
    OpenAIDriver,
    StreamChunk,
)
from daw_agents.models.providers import (
    ModelConfig,
    ModelProvider,
    ProviderConfig,
    get_default_configs,
    get_helicone_config,
)
from daw_agents.models.router import ModelRouter, TaskType

__all__ = [
    # Drivers (FR-10.1)
    "ClaudeDriver",
    "CompletionResponse",
    "DriverRegistry",
    "DriverType",
    "DriverWithFallback",
    "GeminiDriver",
    "LocalDriver",
    "ModelDriver",
    "OpenAIDriver",
    "StreamChunk",
    # Router
    "ModelConfig",
    "ModelProvider",
    "ModelRouter",
    "ProviderConfig",
    "TaskType",
    "get_default_configs",
    "get_helicone_config",
]
