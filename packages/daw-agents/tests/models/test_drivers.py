"""
Tests for Model Driver Abstraction Layer (DRIVER-001).

This test suite validates:
- ModelDriver interface contract
- All driver implementations (Claude, OpenAI, Gemini, Local)
- DriverRegistry config-based selection
- DriverWithFallback automatic recovery
- LLM agnosticism: same interface, different backends
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

# =============================================================================
# ModelDriver Interface Tests
# =============================================================================


class TestModelDriverInterface:
    """Test that ModelDriver interface is properly defined."""

    def test_model_driver_is_abstract(self) -> None:
        """ModelDriver cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            ModelDriver()  # type: ignore

    def test_all_drivers_implement_interface(self) -> None:
        """All driver implementations satisfy the interface."""
        drivers = [ClaudeDriver, OpenAIDriver, GeminiDriver, LocalDriver]

        for driver_class in drivers:
            # Should be instantiable
            driver = driver_class()

            # Should have required properties
            assert hasattr(driver, "driver_type")
            assert hasattr(driver, "supported_models")
            assert isinstance(driver.driver_type, DriverType)
            assert isinstance(driver.supported_models, list)

            # Should have required methods
            assert callable(driver.complete)
            assert callable(driver.stream)
            assert callable(driver.supports_model)


class TestCompletionResponse:
    """Test CompletionResponse data structure."""

    def test_completion_response_fields(self) -> None:
        """CompletionResponse has all required fields."""
        response = CompletionResponse(
            content="Hello, world!",
            model="test-model",
            usage={"input_tokens": 10, "output_tokens": 5},
            finish_reason="stop",
        )

        assert response.content == "Hello, world!"
        assert response.model == "test-model"
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}
        assert response.finish_reason == "stop"

    def test_completion_response_defaults(self) -> None:
        """CompletionResponse has sensible defaults."""
        response = CompletionResponse(content="test", model="test")

        assert response.usage == {}
        assert response.finish_reason == "stop"
        assert response.raw_response is None


class TestStreamChunk:
    """Test StreamChunk data structure."""

    def test_stream_chunk_fields(self) -> None:
        """StreamChunk has correct fields."""
        chunk = StreamChunk(content="Hello", finish_reason=None)
        assert chunk.content == "Hello"
        assert chunk.finish_reason is None

        final = StreamChunk(content="", finish_reason="stop")
        assert final.content == ""
        assert final.finish_reason == "stop"


# =============================================================================
# ClaudeDriver Tests
# =============================================================================


class TestClaudeDriver:
    """Test ClaudeDriver implementation."""

    def test_driver_type(self) -> None:
        """ClaudeDriver returns correct type."""
        driver = ClaudeDriver()
        assert driver.driver_type == DriverType.CLAUDE

    def test_supported_models(self) -> None:
        """ClaudeDriver supports expected model families."""
        driver = ClaudeDriver()
        models = driver.supported_models

        assert "claude-3-5-sonnet" in models
        assert "claude-3-opus" in models
        assert "claude-3-haiku" in models
        assert "claude-sonnet-4" in models
        assert "claude-opus-4" in models

    def test_supports_model_prefixes(self) -> None:
        """ClaudeDriver recognizes model by prefix."""
        driver = ClaudeDriver()

        assert driver.supports_model("claude-3-5-sonnet-20241022")
        assert driver.supports_model("claude-3-opus-20240229")
        assert driver.supports_model("claude-sonnet-4-20250514")
        assert not driver.supports_model("gpt-4o")
        assert not driver.supports_model("gemini-1.5-pro")

    @pytest.mark.asyncio
    async def test_complete_calls_anthropic(self) -> None:
        """ClaudeDriver.complete() calls Anthropic API correctly."""
        driver = ClaudeDriver(api_key="test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.stop_reason = "end_turn"

        with patch.object(driver, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            response = await driver.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                temperature=0.7,
            )

            assert response.content == "Hello from Claude"
            assert response.model == "claude-3-5-sonnet-20241022"
            assert response.usage["input_tokens"] == 10
            assert response.usage["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_complete_handles_system_message(self) -> None:
        """ClaudeDriver correctly converts system message."""
        driver = ClaudeDriver(api_key="test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.stop_reason = "end_turn"

        with patch.object(driver, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await driver.complete(
                messages=[
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
                model="claude-3-5-sonnet-20241022",
            )

            # Verify system was passed separately
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["system"] == "You are helpful"
            assert {"role": "user", "content": "Hello"} in call_args.kwargs["messages"]


# =============================================================================
# OpenAIDriver Tests
# =============================================================================


class TestOpenAIDriver:
    """Test OpenAIDriver implementation."""

    def test_driver_type(self) -> None:
        """OpenAIDriver returns correct type."""
        driver = OpenAIDriver()
        assert driver.driver_type == DriverType.OPENAI

    def test_supported_models(self) -> None:
        """OpenAIDriver supports expected model families."""
        driver = OpenAIDriver()
        models = driver.supported_models

        assert "gpt-4o" in models
        assert "gpt-4" in models
        assert "o1-preview" in models
        assert "o1-mini" in models

    def test_supports_model_prefixes(self) -> None:
        """OpenAIDriver recognizes model by prefix."""
        driver = OpenAIDriver()

        assert driver.supports_model("gpt-4o")
        assert driver.supports_model("gpt-4o-mini")
        assert driver.supports_model("o1-preview")
        assert not driver.supports_model("claude-3-5-sonnet")
        assert not driver.supports_model("gemini-1.5-pro")

    @pytest.mark.asyncio
    async def test_complete_calls_openai(self) -> None:
        """OpenAIDriver.complete() calls OpenAI API correctly."""
        driver = OpenAIDriver(api_key="test-key")

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from GPT"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = mock_usage

        with patch.object(driver, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            response = await driver.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
                max_tokens=1024,
                temperature=0.7,
            )

            assert response.content == "Hello from GPT"
            assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_o1_models_skip_temperature(self) -> None:
        """OpenAIDriver doesn't send temperature for o1 models."""
        driver = OpenAIDriver(api_key="test-key")

        mock_choice = MagicMock()
        mock_choice.message.content = "Thinking..."
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "o1-preview"
        mock_response.usage = None

        with patch.object(driver, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await driver.complete(
                messages=[{"role": "user", "content": "Think about this"}],
                model="o1-preview",
                temperature=0.7,  # Should be ignored
            )

            call_args = mock_client.chat.completions.create.call_args
            assert "temperature" not in call_args.kwargs

    def test_supports_helicone_proxy(self) -> None:
        """OpenAIDriver can use Helicone proxy."""
        driver = OpenAIDriver(
            api_key="test-key",
            api_base="https://oai.helicone.ai/v1",
        )
        assert driver._api_base == "https://oai.helicone.ai/v1"


# =============================================================================
# GeminiDriver Tests
# =============================================================================


class TestGeminiDriver:
    """Test GeminiDriver implementation."""

    def test_driver_type(self) -> None:
        """GeminiDriver returns correct type."""
        driver = GeminiDriver()
        assert driver.driver_type == DriverType.GEMINI

    def test_supported_models(self) -> None:
        """GeminiDriver supports expected model families."""
        driver = GeminiDriver()
        models = driver.supported_models

        assert "gemini-1.5-pro" in models
        assert "gemini-1.5-flash" in models
        assert "gemini-2.0" in models

    def test_supports_model_prefixes(self) -> None:
        """GeminiDriver recognizes model by prefix."""
        driver = GeminiDriver()

        assert driver.supports_model("gemini-1.5-pro")
        assert driver.supports_model("gemini-1.5-flash")
        assert driver.supports_model("gemini-2.0-flash-exp")
        assert not driver.supports_model("claude-3-5-sonnet")
        assert not driver.supports_model("gpt-4o")

    def test_message_conversion(self) -> None:
        """GeminiDriver correctly converts OpenAI message format."""
        driver = GeminiDriver()

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        system, history = driver._convert_messages(messages)

        assert system == "You are helpful"
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["parts"] == ["Hello"]
        assert history[1]["role"] == "model"  # assistant -> model
        assert history[1]["parts"] == ["Hi there"]


# =============================================================================
# LocalDriver Tests
# =============================================================================


class TestLocalDriver:
    """Test LocalDriver (Ollama/LM Studio) implementation."""

    def test_driver_type(self) -> None:
        """LocalDriver returns correct type."""
        driver = LocalDriver()
        assert driver.driver_type == DriverType.LOCAL

    def test_default_api_base(self) -> None:
        """LocalDriver uses Ollama default endpoint."""
        driver = LocalDriver()
        assert driver._api_base == "http://localhost:11434/v1"

    def test_custom_api_base(self) -> None:
        """LocalDriver accepts custom endpoint."""
        driver = LocalDriver(api_base="http://localhost:1234/v1")
        assert driver._api_base == "http://localhost:1234/v1"

    def test_supports_any_model(self) -> None:
        """LocalDriver accepts any model name."""
        driver = LocalDriver()

        # Should accept any model - Ollama handles validation
        assert driver.supports_model("llama3.2")
        assert driver.supports_model("mistral")
        assert driver.supports_model("custom-fine-tuned-model")
        assert driver.supports_model("anything-really")


# =============================================================================
# DriverRegistry Tests
# =============================================================================


class TestDriverRegistry:
    """Test DriverRegistry config-based selection."""

    def setup_method(self) -> None:
        """Clear registry cache before each test."""
        DriverRegistry.clear_cache()

    def test_get_driver_by_type(self) -> None:
        """DriverRegistry.get_driver() returns correct driver."""
        claude = DriverRegistry.get_driver(DriverType.CLAUDE)
        assert isinstance(claude, ClaudeDriver)

        openai = DriverRegistry.get_driver(DriverType.OPENAI)
        assert isinstance(openai, OpenAIDriver)

        gemini = DriverRegistry.get_driver(DriverType.GEMINI)
        assert isinstance(gemini, GeminiDriver)

        local = DriverRegistry.get_driver(DriverType.LOCAL)
        assert isinstance(local, LocalDriver)

    def test_get_driver_by_string(self) -> None:
        """DriverRegistry accepts string type names."""
        claude = DriverRegistry.get_driver("claude")
        assert isinstance(claude, ClaudeDriver)

        openai = DriverRegistry.get_driver("openai")
        assert isinstance(openai, OpenAIDriver)

    def test_get_driver_from_env(self) -> None:
        """DriverRegistry uses DAW_MODEL_DRIVER env var."""
        with patch.dict(os.environ, {"DAW_MODEL_DRIVER": "openai"}):
            DriverRegistry.clear_cache()
            driver = DriverRegistry.get_driver()
            assert isinstance(driver, OpenAIDriver)

    def test_default_driver_is_claude(self) -> None:
        """DriverRegistry defaults to Claude when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DAW_MODEL_DRIVER if set
            os.environ.pop("DAW_MODEL_DRIVER", None)
            DriverRegistry.clear_cache()
            driver = DriverRegistry.get_driver()
            assert isinstance(driver, ClaudeDriver)

    def test_get_driver_for_model_auto_detect(self) -> None:
        """DriverRegistry.get_driver_for_model() auto-detects driver."""
        claude = DriverRegistry.get_driver_for_model("claude-3-5-sonnet-20241022")
        assert isinstance(claude, ClaudeDriver)

        openai = DriverRegistry.get_driver_for_model("gpt-4o")
        assert isinstance(openai, OpenAIDriver)

        gemini = DriverRegistry.get_driver_for_model("gemini-1.5-pro")
        assert isinstance(gemini, GeminiDriver)

    def test_get_driver_for_unknown_model_falls_back(self) -> None:
        """Unknown models fall back to LocalDriver."""
        driver = DriverRegistry.get_driver_for_model("unknown-model-xyz")
        assert isinstance(driver, LocalDriver)

    def test_driver_instances_are_cached(self) -> None:
        """DriverRegistry caches driver instances."""
        d1 = DriverRegistry.get_driver(DriverType.CLAUDE)
        d2 = DriverRegistry.get_driver(DriverType.CLAUDE)
        assert d1 is d2

    def test_list_drivers(self) -> None:
        """DriverRegistry lists all registered drivers."""
        drivers = DriverRegistry.list_drivers()
        assert DriverType.CLAUDE in drivers
        assert DriverType.OPENAI in drivers
        assert DriverType.GEMINI in drivers
        assert DriverType.LOCAL in drivers

    def test_register_custom_driver(self) -> None:
        """DriverRegistry allows registering custom drivers."""

        class CustomDriver(ModelDriver):
            @property
            def driver_type(self) -> DriverType:
                return DriverType.LOCAL

            @property
            def supported_models(self) -> list[str]:
                return ["custom"]

            async def complete(self, **kwargs: Any) -> CompletionResponse:
                return CompletionResponse(content="custom", model="custom")

            async def stream(self, **kwargs: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(content="custom")

        # Note: In a real scenario, you'd add a new DriverType
        # This test just verifies the registration mechanism works
        DriverRegistry.register(DriverType.LOCAL, CustomDriver)
        DriverRegistry.clear_cache()  # Clear cache to get new driver
        driver = DriverRegistry.get_driver(DriverType.LOCAL)
        assert isinstance(driver, CustomDriver)

        # Restore original driver for other tests
        DriverRegistry.register(DriverType.LOCAL, LocalDriver)
        DriverRegistry.clear_cache()


# =============================================================================
# DriverWithFallback Tests
# =============================================================================


class TestDriverWithFallback:
    """Test DriverWithFallback automatic recovery."""

    @pytest.mark.asyncio
    async def test_uses_primary_when_successful(self) -> None:
        """Uses primary driver when it succeeds."""
        primary = AsyncMock(spec=ModelDriver)
        fallback = AsyncMock(spec=ModelDriver)

        primary.complete = AsyncMock(
            return_value=CompletionResponse(content="primary", model="test")
        )

        driver = DriverWithFallback(primary=primary, fallback=fallback)
        response = await driver.complete(
            messages=[{"role": "user", "content": "test"}],
            model="test",
        )

        assert response.content == "primary"
        primary.complete.assert_called_once()
        fallback.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_primary_failure(self) -> None:
        """Falls back to secondary when primary fails."""
        primary = AsyncMock(spec=ModelDriver)
        fallback = AsyncMock(spec=ModelDriver)

        primary.complete = AsyncMock(side_effect=Exception("Primary failed"))
        fallback.complete = AsyncMock(
            return_value=CompletionResponse(content="fallback", model="test")
        )

        driver = DriverWithFallback(primary=primary, fallback=fallback)
        response = await driver.complete(
            messages=[{"role": "user", "content": "test"}],
            model="test",
        )

        assert response.content == "fallback"

    @pytest.mark.asyncio
    async def test_raises_when_both_fail(self) -> None:
        """Raises original error when both drivers fail."""
        primary = AsyncMock(spec=ModelDriver)
        fallback = AsyncMock(spec=ModelDriver)

        primary.complete = AsyncMock(side_effect=ValueError("Primary error"))
        fallback.complete = AsyncMock(side_effect=RuntimeError("Fallback error"))

        driver = DriverWithFallback(primary=primary, fallback=fallback)

        with pytest.raises(ValueError, match="Primary error"):
            await driver.complete(
                messages=[{"role": "user", "content": "test"}],
                model="test",
            )

    @pytest.mark.asyncio
    async def test_uses_model_mapping_for_fallback(self) -> None:
        """Uses model mapping when falling back."""
        primary = AsyncMock(spec=ModelDriver)
        fallback = AsyncMock(spec=ModelDriver)

        primary.complete = AsyncMock(side_effect=Exception("Failed"))
        fallback.complete = AsyncMock(
            return_value=CompletionResponse(content="ok", model="gpt-4o")
        )

        driver = DriverWithFallback(
            primary=primary,
            fallback=fallback,
            fallback_models={"claude-3-5-sonnet": "gpt-4o"},
        )

        await driver.complete(
            messages=[{"role": "user", "content": "test"}],
            model="claude-3-5-sonnet",
        )

        # Verify fallback was called with mapped model
        call_args = fallback.complete.call_args
        assert call_args.kwargs["model"] == "gpt-4o"


# =============================================================================
# LLM Agnosticism Integration Tests
# =============================================================================


class TestLLMAgnosticism:
    """Integration tests verifying true LLM agnosticism."""

    def test_all_drivers_return_same_response_type(self) -> None:
        """All drivers return CompletionResponse."""
        drivers = [ClaudeDriver(), OpenAIDriver(), GeminiDriver(), LocalDriver()]

        for driver in drivers:
            # Type annotations should all match
            from typing import get_type_hints

            hints = get_type_hints(driver.complete)
            assert hints["return"] == CompletionResponse

    def test_driver_swap_requires_no_code_changes(self) -> None:
        """Switching drivers only requires config change."""
        # All drivers have identical signatures (check class method, not bound)
        driver_classes = [ClaudeDriver, OpenAIDriver, GeminiDriver, LocalDriver]
        import inspect

        for driver_class in driver_classes:
            # Get signature from class, not instance
            sig = inspect.signature(driver_class.complete)
            params = list(sig.parameters.keys())

            # All should have these core parameters (self is filtered out for methods)
            assert "messages" in params, f"{driver_class.__name__} missing 'messages'"
            assert "model" in params, f"{driver_class.__name__} missing 'model'"
            assert "max_tokens" in params, f"{driver_class.__name__} missing 'max_tokens'"
            assert "temperature" in params, f"{driver_class.__name__} missing 'temperature'"

    def test_env_based_driver_selection(self) -> None:
        """Driver can be selected purely from environment."""
        test_cases = [
            ("claude", ClaudeDriver),
            ("openai", OpenAIDriver),
            ("gemini", GeminiDriver),
            ("local", LocalDriver),
        ]

        for env_value, expected_class in test_cases:
            with patch.dict(os.environ, {"DAW_MODEL_DRIVER": env_value}):
                DriverRegistry.clear_cache()
                driver = DriverRegistry.get_driver()
                assert isinstance(driver, expected_class), f"Failed for {env_value}"
