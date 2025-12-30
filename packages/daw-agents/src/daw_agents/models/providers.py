"""
Model Provider Configuration for DAW Agent Workbench.

This module defines:
- ModelProvider enum for supported LLM providers
- ModelConfig Pydantic model for per-task-type configurations
- ProviderConfig for loading configurations from environment
- Default model configurations based on task types

Based on FR-01.1: Model Router selects models based on task complexity.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from daw_agents.models.router import TaskType


class ModelProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ModelConfig(BaseModel):
    """Configuration for a model used in a specific task type.

    Attributes:
        primary: Primary model identifier (e.g., "claude-3-5-sonnet-20241022")
        fallback: Fallback model identifier used when primary fails
        max_tokens: Maximum tokens for response generation
        temperature: Temperature for response generation (0.0-2.0)
    """

    primary: str
    fallback: str
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class ProviderConfig(BaseModel):
    """Provider-level configuration.

    Attributes:
        api_key: API key for the provider
        api_base: Optional custom API base URL (e.g., Helicone proxy)
    """

    api_key: str | None = None
    api_base: str | None = None


def get_default_configs() -> dict[TaskType, ModelConfig]:
    """Get default model configurations for all task types.

    Returns configurations that enforce:
    - Planning: High reasoning models (o1/opus) for complex analysis
    - Coding: Balanced models (sonnet/gpt-4o) for code generation
    - Validation: DIFFERENT model than coding for cross-validation principle
    - Fast: Speed-optimized models (haiku/gpt-4o-mini) for quick tasks

    Returns:
        Dictionary mapping TaskType to ModelConfig
    """
    # Import here to avoid circular dependency
    from daw_agents.models.router import TaskType

    # Load from environment with sensible defaults
    planning_model = os.environ.get("MODEL_PLANNING", "o1-preview")
    coding_model = os.environ.get("MODEL_CODING", "claude-3-5-sonnet-20241022")
    validation_model = os.environ.get("MODEL_VALIDATION", "gpt-4o")
    fast_model = os.environ.get("MODEL_FAST", "claude-3-haiku-20240307")

    return {
        TaskType.PLANNING: ModelConfig(
            primary=planning_model,
            fallback="claude-3-opus-20240229",  # High reasoning fallback
            max_tokens=8192,  # Longer context for planning
            temperature=0.3,  # Lower temperature for consistent planning
        ),
        TaskType.CODING: ModelConfig(
            primary=coding_model,
            fallback="gpt-4o",  # Balanced fallback
            max_tokens=4096,
            temperature=0.2,  # Low temperature for precise code
        ),
        TaskType.VALIDATION: ModelConfig(
            primary=validation_model,
            # CRITICAL: Fallback must also be different from coding primary
            fallback="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.1,  # Very low temperature for consistent validation
        ),
        TaskType.FAST: ModelConfig(
            primary=fast_model,
            fallback="gpt-4o-mini",  # Fast fallback
            max_tokens=2048,  # Shorter for fast tasks
            temperature=0.5,
        ),
    }


def get_helicone_config() -> ProviderConfig:
    """Get Helicone proxy configuration.

    Helicone is used for cost tracking and observability.

    Returns:
        ProviderConfig with Helicone settings
    """
    api_key = os.environ.get("HELICONE_API_KEY")
    api_base = os.environ.get("HELICONE_BASE_URL", "https://oai.helicone.ai/v1")

    return ProviderConfig(
        api_key=api_key,
        api_base=api_base if api_key else None,
    )
