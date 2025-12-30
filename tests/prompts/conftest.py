"""Pytest configuration for prompt regression tests.

This module provides fixtures and configuration for running prompt
regression tests as part of the CI pipeline.

Part of PROMPT-GOV-002: Implement Prompt Regression Testing Harness.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from daw_agents.testing.prompt_harness import PromptHarness


# =============================================================================
# Path Configuration
# =============================================================================


def get_goldens_path() -> Path:
    """Get the path to the goldens directory.

    Returns:
        Path to tests/prompts/goldens/
    """
    return Path(__file__).parent / "goldens"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def goldens_path() -> Path:
    """Fixture providing path to golden test data."""
    return get_goldens_path()


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Create a mock model router for testing.

    This fixture provides a mock that simulates LLM responses
    without making actual API calls.
    """
    router = MagicMock()
    router.generate = AsyncMock(return_value='{"title": "Test", "overview": "Test overview"}')
    return router


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Create a mock embedding provider for testing.

    This fixture provides a mock that returns consistent embeddings
    for similarity calculations.
    """
    provider = MagicMock()
    # Return consistent high-dimensional embedding vectors
    provider.get_embedding = AsyncMock(return_value=[0.5] * 1536)
    return provider


@pytest.fixture
def prompt_harness(
    mock_model_router: MagicMock,
    mock_embedding_provider: MagicMock,
    goldens_path: Path,
) -> "PromptHarness":
    """Create a PromptHarness instance for testing.

    This fixture wires together the mock dependencies and provides
    a fully configured harness for prompt regression tests.
    """
    from daw_agents.testing.prompt_harness import PromptHarness

    return PromptHarness(
        model_router=mock_model_router,
        embedding_provider=mock_embedding_provider,
        goldens_path=goldens_path,
    )


# =============================================================================
# Pytest Hooks
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for prompt regression tests."""
    config.addinivalue_line(
        "markers",
        "prompt_regression: marks tests as prompt regression tests",
    )


# =============================================================================
# Utility Functions for Tests
# =============================================================================


def load_golden_pair_paths(agent_type: str, prompt_version: str) -> list[tuple[Path, Path]]:
    """Load paths to golden pair files for a specific prompt.

    Args:
        agent_type: Type of agent (e.g., "planner")
        prompt_version: Version string (e.g., "prd_generator_v1.0")

    Returns:
        List of (input_path, expected_path) tuples
    """
    goldens_dir = get_goldens_path() / agent_type / prompt_version
    if not goldens_dir.exists():
        return []

    pairs: list[tuple[Path, Path]] = []
    for input_file in sorted(goldens_dir.glob("input_*.txt")):
        index = input_file.stem.replace("input_", "")
        expected_file = goldens_dir / f"expected_{index}.json"
        if expected_file.exists():
            pairs.append((input_file, expected_file))

    return pairs
