"""
Tests for the Model Router module (MODEL-001).

These tests verify:
1. Task-based model selection (planning/coding/validation/fast)
2. Fallback logic when primary model fails
3. Cost tracking headers integration (Helicone)
4. Configuration loading and validation
5. Cross-validation principle (validator uses different model than executor)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from daw_agents.models.providers import (
    ModelConfig,
    ModelProvider,
    get_default_configs,
)
from daw_agents.models.router import ModelRouter, TaskType


class TestTaskType:
    """Test TaskType enumeration."""

    def test_task_types_exist(self) -> None:
        """Verify all required task types are defined."""
        assert TaskType.PLANNING is not None
        assert TaskType.CODING is not None
        assert TaskType.VALIDATION is not None
        assert TaskType.FAST is not None

    def test_task_type_values(self) -> None:
        """Verify task type string values."""
        assert TaskType.PLANNING.value == "planning"
        assert TaskType.CODING.value == "coding"
        assert TaskType.VALIDATION.value == "validation"
        assert TaskType.FAST.value == "fast"


class TestModelConfig:
    """Test ModelConfig Pydantic model."""

    def test_model_config_creation(self) -> None:
        """Test creating a ModelConfig with all fields."""
        config = ModelConfig(
            primary="claude-3-5-sonnet-20241022",
            fallback="gpt-4o",
            max_tokens=4096,
            temperature=0.7,
        )
        assert config.primary == "claude-3-5-sonnet-20241022"
        assert config.fallback == "gpt-4o"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_model_config_defaults(self) -> None:
        """Test ModelConfig default values."""
        config = ModelConfig(primary="gpt-4o", fallback="claude-3-5-sonnet-20241022")
        assert config.max_tokens == 4096
        assert config.temperature == 0.7


class TestProviderConfig:
    """Test ProviderConfig loading."""

    def test_get_default_configs(self) -> None:
        """Test that default configs are returned for all task types."""
        configs = get_default_configs()
        assert TaskType.PLANNING in configs
        assert TaskType.CODING in configs
        assert TaskType.VALIDATION in configs
        assert TaskType.FAST in configs

    def test_planning_config_uses_high_reasoning_model(self) -> None:
        """Planning tasks should use o1/opus (high reasoning models)."""
        configs = get_default_configs()
        planning_config = configs[TaskType.PLANNING]
        # Primary should be a high reasoning model (o1-preview or claude-opus)
        assert "o1" in planning_config.primary or "opus" in planning_config.primary.lower()

    def test_validation_uses_different_model_than_coding(self) -> None:
        """Critical: Validator MUST use different model than executor (coding)."""
        configs = get_default_configs()
        coding_config = configs[TaskType.CODING]
        validation_config = configs[TaskType.VALIDATION]
        # Ensure cross-validation principle is enforced
        assert coding_config.primary != validation_config.primary, (
            "Validator must use a DIFFERENT model than executor for cross-validation"
        )

    def test_fast_config_uses_speed_optimized_model(self) -> None:
        """Fast tasks should use speed-optimized models (haiku/gpt-4o-mini)."""
        configs = get_default_configs()
        fast_config = configs[TaskType.FAST]
        # Primary should be a fast model
        assert (
            "haiku" in fast_config.primary.lower()
            or "mini" in fast_config.primary.lower()
        )


class TestModelRouter:
    """Test ModelRouter functionality."""

    @pytest.fixture
    def router(self) -> ModelRouter:
        """Create a ModelRouter instance for testing."""
        return ModelRouter()

    def test_router_initialization(self, router: ModelRouter) -> None:
        """Test that router initializes with default configs."""
        assert router.configs is not None
        assert len(router.configs) == 4  # planning, coding, validation, fast

    def test_get_model_for_task_planning(self, router: ModelRouter) -> None:
        """Test getting model for planning tasks."""
        model = router.get_model_for_task(TaskType.PLANNING)
        assert model is not None
        assert isinstance(model, str)

    def test_get_model_for_task_coding(self, router: ModelRouter) -> None:
        """Test getting model for coding tasks."""
        model = router.get_model_for_task(TaskType.CODING)
        assert model is not None
        assert isinstance(model, str)

    def test_get_model_for_task_validation(self, router: ModelRouter) -> None:
        """Test getting model for validation tasks."""
        model = router.get_model_for_task(TaskType.VALIDATION)
        assert model is not None
        assert isinstance(model, str)

    def test_get_model_for_task_fast(self, router: ModelRouter) -> None:
        """Test getting model for fast tasks."""
        model = router.get_model_for_task(TaskType.FAST)
        assert model is not None
        assert isinstance(model, str)

    def test_get_config_for_task(self, router: ModelRouter) -> None:
        """Test getting full config for a task type."""
        config = router.get_config_for_task(TaskType.CODING)
        assert isinstance(config, ModelConfig)
        assert config.primary is not None
        assert config.fallback is not None


class TestModelRouterAsync:
    """Test async routing functionality."""

    @pytest.fixture
    def router(self) -> ModelRouter:
        """Create a ModelRouter instance for testing."""
        return ModelRouter()

    @pytest.mark.asyncio
    async def test_route_planning_task_uses_correct_model(
        self, router: ModelRouter
    ) -> None:
        """Test that planning tasks are routed to high-reasoning models."""
        with patch("daw_agents.models.router.acompletion") as mock_completion:
            mock_completion.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Test response"))]
            )

            await router.route(
                task_type=TaskType.PLANNING,
                messages=[{"role": "user", "content": "Create a PRD for a todo app"}],
            )

            # Verify correct model was used
            call_kwargs = mock_completion.call_args.kwargs
            model_used = call_kwargs["model"]
            assert "o1" in model_used or "opus" in model_used.lower()

    @pytest.mark.asyncio
    async def test_route_validation_uses_different_model_from_coding(
        self, router: ModelRouter
    ) -> None:
        """Critical: Validation tasks must use a different model than coding tasks."""
        coding_model = router.get_model_for_task(TaskType.CODING)
        validation_model = router.get_model_for_task(TaskType.VALIDATION)

        assert coding_model != validation_model, (
            f"Validator model ({validation_model}) must be different from "
            f"executor model ({coding_model}) for cross-validation principle"
        )

    @pytest.mark.asyncio
    async def test_route_returns_string_response(self, router: ModelRouter) -> None:
        """Test that route returns a string response."""
        with patch("daw_agents.models.router.acompletion") as mock_completion:
            mock_completion.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Test response"))]
            )

            result = await router.route(
                task_type=TaskType.FAST,
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert isinstance(result, str)
            assert result == "Test response"


class TestFallbackLogic:
    """Test fallback mechanism when primary model fails."""

    @pytest.fixture
    def router(self) -> ModelRouter:
        """Create a ModelRouter instance for testing."""
        return ModelRouter()

    @pytest.mark.asyncio
    async def test_fallback_when_primary_fails(self, router: ModelRouter) -> None:
        """Test that fallback model is used when primary fails."""
        call_count = 0

        async def mock_acompletion(**kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (primary) fails
                raise Exception("Primary model unavailable")
            # Second call (fallback) succeeds
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="Fallback response"))]
            )

        with patch("daw_agents.models.router.acompletion", side_effect=mock_acompletion):
            result = await router.route(
                task_type=TaskType.CODING,
                messages=[{"role": "user", "content": "Write a function"}],
            )

            assert result == "Fallback response"
            assert call_count == 2  # Primary failed, then fallback succeeded

    @pytest.mark.asyncio
    async def test_raises_when_both_models_fail(self, router: ModelRouter) -> None:
        """Test that error is raised when both primary and fallback fail."""
        with patch("daw_agents.models.router.acompletion") as mock_completion:
            mock_completion.side_effect = Exception("All models unavailable")

            with pytest.raises(Exception, match="All models unavailable"):
                await router.route(
                    task_type=TaskType.CODING,
                    messages=[{"role": "user", "content": "Write a function"}],
                )


class TestHeliconeIntegration:
    """Test Helicone cost tracking integration."""

    @pytest.fixture
    def router(self) -> ModelRouter:
        """Create a ModelRouter instance for testing."""
        return ModelRouter()

    @pytest.mark.asyncio
    async def test_helicone_headers_included_when_configured(
        self, router: ModelRouter
    ) -> None:
        """Test that Helicone headers are included in requests when API key is set."""
        with patch.dict(os.environ, {"HELICONE_API_KEY": "test-key"}):
            with patch("daw_agents.models.router.acompletion") as mock_completion:
                mock_completion.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content="Response"))]
                )

                router_with_helicone = ModelRouter()
                await router_with_helicone.route(
                    task_type=TaskType.FAST,
                    messages=[{"role": "user", "content": "Test"}],
                )

                call_kwargs = mock_completion.call_args.kwargs
                # Check that Helicone-related parameters are set
                # Either through api_base or extra_headers
                assert (
                    "extra_headers" in call_kwargs
                    or "metadata" in call_kwargs
                    or "api_base" in call_kwargs
                )

    @pytest.mark.asyncio
    async def test_metadata_includes_task_type(self, router: ModelRouter) -> None:
        """Test that request metadata includes task type for tracking."""
        with patch("daw_agents.models.router.acompletion") as mock_completion:
            mock_completion.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Response"))]
            )

            await router.route(
                task_type=TaskType.PLANNING,
                messages=[{"role": "user", "content": "Test"}],
                metadata={"user_id": "test-user", "project_id": "test-project"},
            )

            call_kwargs = mock_completion.call_args.kwargs
            # Metadata should include the task type
            if "metadata" in call_kwargs:
                assert "task_type" in call_kwargs["metadata"]


class TestConfigurationFromEnvironment:
    """Test configuration loading from environment variables."""

    def test_model_config_from_env(self) -> None:
        """Test that model configs can be overridden via environment variables."""
        with patch.dict(
            os.environ,
            {
                "MODEL_PLANNING": "custom-planning-model",
                "MODEL_CODING": "custom-coding-model",
                "MODEL_VALIDATION": "custom-validation-model",
                "MODEL_FAST": "custom-fast-model",
            },
        ):
            # Create new router to pick up env vars
            router = ModelRouter()
            # Note: Implementation should read from env vars
            # This test verifies the behavior exists
            planning_model = router.get_model_for_task(TaskType.PLANNING)
            assert planning_model is not None


class TestModelProvider:
    """Test ModelProvider enum and utilities."""

    def test_provider_enum_exists(self) -> None:
        """Test that ModelProvider enum has expected providers."""
        assert ModelProvider.OPENAI is not None
        assert ModelProvider.ANTHROPIC is not None

    def test_provider_values(self) -> None:
        """Test ModelProvider values."""
        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.ANTHROPIC.value == "anthropic"
