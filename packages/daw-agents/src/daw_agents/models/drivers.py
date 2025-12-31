"""
Model Driver Abstraction Layer for DAW Agent Workbench.

This module implements FR-10.1 (Multi-Model Driver Support):
- ModelDriver: Abstract interface for LLM providers
- ClaudeDriver: Anthropic Claude models
- OpenAIDriver: OpenAI GPT/o1 models
- GeminiDriver: Google Gemini models
- LocalDriver: Local models via Ollama/LM Studio

Design Principles:
1. LLM as stateless reasoning unit, system as the OS
2. Hot-swappable drivers without code changes
3. Config-driven selection via YAML or environment
4. Automatic fallback on driver failure

Usage:
    ```python
    from daw_agents.models.drivers import DriverRegistry

    # Get driver from config
    driver = DriverRegistry.get_driver()

    # Or explicitly select
    driver = DriverRegistry.get_driver("claude")

    # All drivers have the same interface
    response = await driver.complete(
        messages=[{"role": "user", "content": "Hello"}],
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
    )
    ```
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DriverType(str, Enum):
    """Supported model driver types."""

    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    LOCAL = "local"


@dataclass
class CompletionResponse:
    """Standardized response from any model driver.

    All drivers return this same structure, enabling true agnosticism.
    """

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw_response: Any = None


@dataclass
class StreamChunk:
    """A chunk from streaming completion."""

    content: str
    finish_reason: str | None = None


class ModelDriver(ABC):
    """Abstract base class for LLM model drivers.

    All drivers must implement this interface to be swappable.
    The system treats LLMs as stateless reasoning units - the driver
    handles all provider-specific details.

    FR-10.1.1: ModelDriver abstract interface
    """

    @property
    @abstractmethod
    def driver_type(self) -> DriverType:
        """Return the driver type identifier."""
        ...

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Return list of model identifiers this driver supports."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Generate a completion from the model.

        Args:
            messages: Chat messages in OpenAI format [{"role": "...", "content": "..."}]
            model: Model identifier (driver-specific)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional driver-specific parameters

        Returns:
            CompletionResponse with standardized fields
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion from the model.

        Args:
            messages: Chat messages in OpenAI format
            model: Model identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional driver-specific parameters

        Yields:
            StreamChunk objects with content deltas
        """
        ...

    def supports_model(self, model: str) -> bool:
        """Check if this driver supports the given model."""
        return any(
            model.startswith(prefix) or model == prefix
            for prefix in self.supported_models
        )


class ClaudeDriver(ModelDriver):
    """Anthropic Claude model driver.

    FR-10.1.2: ClaudeDriver implementation

    Supports:
    - claude-3-5-sonnet-20241022
    - claude-3-opus-20240229
    - claude-3-haiku-20240307
    - claude-sonnet-4-20250514
    - claude-opus-4-5-20251101
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: Any = None

    @property
    def driver_type(self) -> DriverType:
        return DriverType.CLAUDE

    @property
    def supported_models(self) -> list[str]:
        return [
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-haiku",
            "claude-sonnet-4",
            "claude-opus-4",
        ]

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self._api_key)
            except ImportError as e:
                raise ImportError(
                    "anthropic package required for ClaudeDriver. "
                    "Install with: pip install anthropic"
                ) from e
        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> CompletionResponse:
        client = self._get_client()

        # Convert to Anthropic format (separate system message)
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_msg:
            params["system"] = system_msg

        response = await client.messages.create(**params)

        return CompletionResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "stop",
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_client()

        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_msg:
            params["system"] = system_msg

        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield StreamChunk(content=text)
            yield StreamChunk(content="", finish_reason="stop")


class OpenAIDriver(ModelDriver):
    """OpenAI model driver.

    FR-10.1.2: OpenAIDriver implementation

    Supports:
    - gpt-4o, gpt-4o-mini
    - gpt-4-turbo, gpt-4
    - o1-preview, o1-mini
    """

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._api_base = api_base  # For Helicone proxy
        self._client: Any = None

    @property
    def driver_type(self) -> DriverType:
        return DriverType.OPENAI

    @property
    def supported_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4", "o1-preview", "o1-mini", "o1"]

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                kwargs: dict[str, Any] = {"api_key": self._api_key}
                if self._api_base:
                    kwargs["base_url"] = self._api_base
                self._client = AsyncOpenAI(**kwargs)
            except ImportError as e:
                raise ImportError(
                    "openai package required for OpenAIDriver. "
                    "Install with: pip install openai"
                ) from e
        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> CompletionResponse:
        client = self._get_client()

        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        # o1 models don't support temperature
        if not model.startswith("o1"):
            params["temperature"] = temperature

        response = await client.chat.completions.create(**params)

        choice = response.choices[0]
        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_client()

        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if not model.startswith("o1"):
            params["temperature"] = temperature

        stream = await client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield StreamChunk(content=chunk.choices[0].delta.content)
            if chunk.choices and chunk.choices[0].finish_reason:
                yield StreamChunk(content="", finish_reason=chunk.choices[0].finish_reason)


class GeminiDriver(ModelDriver):
    """Google Gemini model driver.

    FR-10.1.2: GeminiDriver implementation

    Supports:
    - gemini-1.5-pro
    - gemini-1.5-flash
    - gemini-2.0-flash-exp
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._client: Any = None

    @property
    def driver_type(self) -> DriverType:
        return DriverType.GEMINI

    @property
    def supported_models(self) -> list[str]:
        return ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0"]

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._client = genai
            except ImportError as e:
                raise ImportError(
                    "google-generativeai package required for GeminiDriver. "
                    "Install with: pip install google-generativeai"
                ) from e
        return self._client

    def _convert_messages(self, messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert OpenAI format to Gemini format."""
        system_instruction = None
        history = []

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                history.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                history.append({"role": "model", "parts": [msg["content"]]})

        return system_instruction, history

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> CompletionResponse:
        genai = self._get_client()

        system_instruction, history = self._convert_messages(messages)

        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        model_kwargs: dict[str, Any] = {"model_name": model}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        gemini_model = genai.GenerativeModel(**model_kwargs)

        # Get last user message and previous history
        if history:
            last_msg = history[-1]["parts"][0] if history[-1]["role"] == "user" else ""
            chat_history = history[:-1] if len(history) > 1 else []
        else:
            last_msg = ""
            chat_history = []

        chat = gemini_model.start_chat(history=chat_history)
        response = await chat.send_message_async(
            last_msg,
            generation_config=generation_config,
        )

        return CompletionResponse(
            content=response.text,
            model=model,
            usage={
                "input_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                "output_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
            },
            finish_reason="stop",
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        genai = self._get_client()

        system_instruction, history = self._convert_messages(messages)

        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        model_kwargs: dict[str, Any] = {"model_name": model}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        gemini_model = genai.GenerativeModel(**model_kwargs)

        if history:
            last_msg = history[-1]["parts"][0] if history[-1]["role"] == "user" else ""
            chat_history = history[:-1] if len(history) > 1 else []
        else:
            last_msg = ""
            chat_history = []

        chat = gemini_model.start_chat(history=chat_history)
        response = await chat.send_message_async(
            last_msg,
            generation_config=generation_config,
            stream=True,
        )

        async for chunk in response:
            if chunk.text:
                yield StreamChunk(content=chunk.text)
        yield StreamChunk(content="", finish_reason="stop")


class LocalDriver(ModelDriver):
    """Local model driver via Ollama or LM Studio.

    FR-10.1.2: LocalDriver implementation
    FR-10.4: Local Model Support for offline capability

    Supports any model available in Ollama/LM Studio via OpenAI-compatible API.
    """

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str = "ollama",  # Ollama doesn't require a key
    ):
        self._api_base = api_base or os.environ.get(
            "LOCAL_MODEL_API_BASE", "http://localhost:11434/v1"
        )
        self._api_key = api_key
        self._client: Any = None

    @property
    def driver_type(self) -> DriverType:
        return DriverType.LOCAL

    @property
    def supported_models(self) -> list[str]:
        # Local models can be anything - we accept all
        return ["llama", "mistral", "codellama", "deepseek", "qwen", "phi"]

    def supports_model(self, model: str) -> bool:
        # Local driver accepts any model - Ollama will handle validation
        return True

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self._api_base,
                )
            except ImportError as e:
                raise ImportError(
                    "openai package required for LocalDriver (uses OpenAI-compatible API). "
                    "Install with: pip install openai"
                ) from e
        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> CompletionResponse:
        client = self._get_client()

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        choice = response.choices[0]
        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_client()

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield StreamChunk(content=chunk.choices[0].delta.content)
            if chunk.choices and chunk.choices[0].finish_reason:
                yield StreamChunk(content="", finish_reason=chunk.choices[0].finish_reason)


class DriverRegistry:
    """Registry for model drivers with config-based selection.

    FR-10.1.3: Config via environment or explicit selection
    FR-10.1.4: Driver switch without code changes

    Usage:
        # From environment (DAW_MODEL_DRIVER=claude)
        driver = DriverRegistry.get_driver()

        # Explicit selection
        driver = DriverRegistry.get_driver("openai")

        # Auto-detect from model name
        driver = DriverRegistry.get_driver_for_model("claude-3-5-sonnet-20241022")
    """

    _drivers: dict[DriverType, type[ModelDriver]] = {
        DriverType.CLAUDE: ClaudeDriver,
        DriverType.OPENAI: OpenAIDriver,
        DriverType.GEMINI: GeminiDriver,
        DriverType.LOCAL: LocalDriver,
    }

    _instances: dict[DriverType, ModelDriver] = {}

    @classmethod
    def register(cls, driver_type: DriverType, driver_class: type[ModelDriver]) -> None:
        """Register a custom driver."""
        cls._drivers[driver_type] = driver_class

    @classmethod
    def get_driver(cls, driver_type: str | DriverType | None = None) -> ModelDriver:
        """Get a driver instance by type.

        Args:
            driver_type: Driver type or None to use DAW_MODEL_DRIVER env var

        Returns:
            ModelDriver instance (cached)
        """
        if driver_type is None:
            driver_type = os.environ.get("DAW_MODEL_DRIVER", "claude")

        if isinstance(driver_type, str):
            driver_type = DriverType(driver_type.lower())

        if driver_type not in cls._instances:
            driver_class = cls._drivers.get(driver_type)
            if driver_class is None:
                raise ValueError(f"Unknown driver type: {driver_type}")
            cls._instances[driver_type] = driver_class()

        return cls._instances[driver_type]

    @classmethod
    def get_driver_for_model(cls, model: str) -> ModelDriver:
        """Auto-detect the appropriate driver for a model.

        Args:
            model: Model identifier (e.g., "claude-3-5-sonnet-20241022")

        Returns:
            Appropriate ModelDriver instance
        """
        # Try each driver to see which supports the model
        for driver_type in cls._drivers:
            driver = cls.get_driver(driver_type)
            if driver.supports_model(model):
                return driver

        # Default to local driver for unknown models
        logger.warning(
            f"No driver explicitly supports model '{model}', falling back to LocalDriver"
        )
        return cls.get_driver(DriverType.LOCAL)

    @classmethod
    def list_drivers(cls) -> list[DriverType]:
        """List all registered driver types."""
        return list(cls._drivers.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached driver instances."""
        cls._instances.clear()


class DriverWithFallback:
    """Wrapper that provides automatic fallback to another driver.

    FR-10.1.5: Automatic fallback on driver failure

    Usage:
        driver = DriverWithFallback(
            primary=ClaudeDriver(),
            fallback=OpenAIDriver(),
        )
        response = await driver.complete(...)  # Falls back if primary fails
    """

    def __init__(
        self,
        primary: ModelDriver,
        fallback: ModelDriver,
        fallback_models: dict[str, str] | None = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.fallback_models = fallback_models or {}

    def _get_fallback_model(self, model: str) -> str:
        """Get the fallback model for a given primary model."""
        return self.fallback_models.get(model, model)

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> CompletionResponse:
        try:
            return await self.primary.complete(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except Exception as primary_error:
            logger.warning(
                f"Primary driver failed: {primary_error}. Trying fallback..."
            )
            fallback_model = self._get_fallback_model(model)
            try:
                return await self.fallback.complete(
                    messages=messages,
                    model=fallback_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
            except Exception as fallback_error:
                logger.error(f"Fallback driver also failed: {fallback_error}")
                raise primary_error from fallback_error

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        try:
            async for chunk in self.primary.stream(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            ):
                yield chunk
        except Exception as primary_error:
            logger.warning(
                f"Primary driver failed: {primary_error}. Trying fallback..."
            )
            fallback_model = self._get_fallback_model(model)
            async for chunk in self.fallback.stream(
                messages=messages,
                model=fallback_model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            ):
                yield chunk
