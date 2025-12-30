"""
Helicone Observability Integration for DAW Agent Workbench.

This module provides:
- HeliconeConfig: Configuration model with API key and proxy URL
- HeliconeHeaders: Header builder for LLM requests with caching support
- HeliconeTracker: Request tracking and cost aggregation
- Integration with LiteLLM and OpenAI client patterns

Based on OPS-001 requirements and Helicone SDK documentation.
See: https://docs.helicone.ai/

Helicone provides:
- LLM cost tracking per request
- Request/response logging for debugging
- Latency and token usage monitoring
- Response caching with configurable TTL
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, model_validator


class HeliconeConfig(BaseModel):
    """Configuration for Helicone observability proxy.

    Helicone proxies LLM API calls to track costs, latency, and usage.

    Attributes:
        api_key: Helicone API key for authentication
        base_url: Helicone proxy base URL
        enabled: Whether Helicone tracking is enabled
    """

    api_key: str | None = None
    base_url: str = Field(default="https://oai.helicone.ai/v1")
    enabled: bool = True

    @model_validator(mode="after")
    def disable_if_no_api_key(self) -> HeliconeConfig:
        """Disable Helicone if no API key is provided."""
        if not self.api_key:
            object.__setattr__(self, "enabled", False)
        return self

    @classmethod
    def from_env(cls) -> HeliconeConfig:
        """Load configuration from environment variables.

        Reads:
        - HELICONE_API_KEY: Required for Helicone to be enabled
        - HELICONE_BASE_URL: Optional, defaults to https://oai.helicone.ai/v1

        Returns:
            HeliconeConfig instance loaded from environment
        """
        api_key = os.environ.get("HELICONE_API_KEY")
        base_url = os.environ.get("HELICONE_BASE_URL", "https://oai.helicone.ai/v1")
        return cls(api_key=api_key, base_url=base_url)


class CacheConfig(BaseModel):
    """Configuration for Helicone response caching.

    Caching helps reduce costs and latency by storing previous
    LLM responses for identical requests.

    Attributes:
        enabled: Whether caching is enabled
        max_age_seconds: Cache TTL in seconds (default: 30 days)
        bucket_max_size: Max variations to cache per request pattern
        seed: Optional deterministic seed for cache key
    """

    enabled: bool = False
    max_age_seconds: int = Field(default=2592000)  # 30 days
    bucket_max_size: int = Field(default=1, ge=1, le=10)
    seed: str | None = None


class RequestMetadata(BaseModel):
    """Metadata to attach to LLM requests for tracking.

    This metadata is used to:
    - Track costs per user/project
    - Group requests by session
    - Add custom properties for filtering

    Attributes:
        user_id: User ID for per-user cost tracking
        session_id: Session ID for grouping requests
        project_id: Project ID for project-level tracking
        agent_type: Agent type (planner, executor, validator, etc.)
        custom_properties: Additional key-value pairs for tracking
    """

    user_id: str | None = None
    session_id: str | None = None
    project_id: str | None = None
    agent_type: str | None = None
    custom_properties: dict[str, str] = Field(default_factory=dict)


class HeliconeHeaders:
    """Builder for Helicone HTTP headers.

    Creates the proper header format for:
    - Authentication (Helicone-Auth)
    - User tracking (Helicone-User-Id)
    - Session tracking (Helicone-Session-Id)
    - Custom properties (Helicone-Property-*)
    - Caching (Helicone-Cache-Enabled, Cache-Control, etc.)

    Usage:
        config = HeliconeConfig(api_key="hlc_...")
        metadata = RequestMetadata(user_id="user-123")
        headers = HeliconeHeaders(config=config, metadata=metadata)
        result = headers.build()  # Returns dict of headers
    """

    def __init__(
        self,
        config: HeliconeConfig,
        metadata: RequestMetadata | None = None,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """Initialize HeliconeHeaders builder.

        Args:
            config: Helicone configuration with API key
            metadata: Optional request metadata for tracking
            cache_config: Optional caching configuration
        """
        self.config = config
        self.metadata = metadata
        self.cache_config = cache_config

    def _normalize_property_name(self, name: str) -> str:
        """Normalize a property name to Title-Case format.

        Converts snake_case, kebab-case, or camelCase to Title-Case.

        Args:
            name: Property name to normalize

        Returns:
            Normalized property name (e.g., "snake_case" -> "Snake-Case")
        """
        # Replace underscores and hyphens with spaces for splitting
        parts = re.split(r"[_\-]", name)
        # Handle camelCase by keeping it as-is but title-casing
        return "-".join(part.capitalize() for part in parts if part)

    def build(self) -> dict[str, str]:
        """Build Helicone headers dictionary.

        Returns:
            Dictionary of HTTP headers for Helicone integration.
            Returns empty dict if Helicone is disabled.
        """
        if not self.config.enabled or not self.config.api_key:
            return {}

        headers: dict[str, str] = {
            "Helicone-Auth": f"Bearer {self.config.api_key}",
        }

        # Add metadata headers
        if self.metadata:
            if self.metadata.user_id:
                headers["Helicone-User-Id"] = self.metadata.user_id

            if self.metadata.session_id:
                headers["Helicone-Session-Id"] = self.metadata.session_id

            if self.metadata.project_id:
                headers["Helicone-Property-Project"] = self.metadata.project_id

            if self.metadata.agent_type:
                headers["Helicone-Property-Agent-Type"] = self.metadata.agent_type

            # Add custom properties
            for key, value in self.metadata.custom_properties.items():
                normalized_key = self._normalize_property_name(key)
                headers[f"Helicone-Property-{normalized_key}"] = value

        # Add caching headers
        if self.cache_config and self.cache_config.enabled:
            headers["Helicone-Cache-Enabled"] = "true"
            headers["Cache-Control"] = f"max-age={self.cache_config.max_age_seconds}"
            headers["Helicone-Cache-Bucket-Max-Size"] = str(
                self.cache_config.bucket_max_size
            )

            if self.cache_config.seed:
                headers["Helicone-Cache-Seed"] = self.cache_config.seed

        return headers


class TrackedRequest(BaseModel):
    """Model for a tracked LLM request.

    Stores data about a single LLM API call for cost tracking
    and analytics.

    Attributes:
        request_id: Unique identifier for the request
        model: Model used (e.g., "gpt-4o", "claude-3-5-sonnet")
        task_type: Type of task (planning, coding, validation, fast)
        tokens_prompt: Number of prompt tokens
        tokens_completion: Number of completion tokens
        cost_usd: Cost in USD
        latency_ms: Request latency in milliseconds
        cached: Whether the response was served from cache
        timestamp: When the request was made
        metadata: Additional metadata attached to the request
    """

    request_id: str
    model: str
    task_type: str
    tokens_prompt: int = Field(ge=0)
    tokens_completion: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    cached: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Get total token count (prompt + completion)."""
        return self.tokens_prompt + self.tokens_completion


class TimeRange(BaseModel):
    """Time range for cost summary queries.

    Attributes:
        start: Start of the time range
        end: End of the time range
    """

    start: datetime
    end: datetime

    @classmethod
    def last_hour(cls) -> TimeRange:
        """Create a TimeRange for the last hour."""
        now = datetime.now(UTC)
        return cls(start=now - timedelta(hours=1), end=now)

    @classmethod
    def last_day(cls) -> TimeRange:
        """Create a TimeRange for the last 24 hours."""
        now = datetime.now(UTC)
        return cls(start=now - timedelta(days=1), end=now)


@dataclass
class CostSummary:
    """Summary of costs for a time period.

    Attributes:
        total_cost_usd: Total cost in USD
        total_requests: Total number of requests
        total_tokens: Total token count
        cached_requests: Number of cached requests
        cache_hit_rate: Ratio of cached to total requests
        breakdown: Optional breakdown by model or task type
    """

    total_cost_usd: float = 0.0
    total_requests: int = 0
    total_tokens: int = 0
    cached_requests: int = 0
    cache_hit_rate: float = 0.0
    breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)


class HeliconeTracker:
    """Tracker for LLM request costs and usage.

    Provides:
    - Request tracking with metadata
    - Cost aggregation over time ranges
    - Breakdown by model or task type
    - Cache hit rate statistics

    Usage:
        config = HeliconeConfig(api_key="hlc_...")
        tracker = HeliconeTracker(config=config)

        # Track a request
        request_id = tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
        )

        # Get cost summary
        summary = tracker.get_cost_summary(TimeRange.last_hour())
    """

    def __init__(self, config: HeliconeConfig) -> None:
        """Initialize HeliconeTracker.

        Args:
            config: Helicone configuration
        """
        self.config = config
        self._requests: list[TrackedRequest] = []

    def track_request(
        self,
        model: str,
        task_type: str,
        tokens_prompt: int,
        tokens_completion: int,
        cost_usd: float,
        latency_ms: int,
        cached: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Track an LLM request.

        Args:
            model: Model used for the request
            task_type: Type of task (planning, coding, etc.)
            tokens_prompt: Number of prompt tokens
            tokens_completion: Number of completion tokens
            cost_usd: Cost in USD
            latency_ms: Request latency in milliseconds
            cached: Whether response was from cache
            metadata: Additional metadata

        Returns:
            Unique request ID
        """
        request_id = str(uuid.uuid4())
        request = TrackedRequest(
            request_id=request_id,
            model=model,
            task_type=task_type,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            cached=cached,
            metadata=metadata or {},
        )
        self._requests.append(request)
        return request_id

    def get_cost_summary(
        self,
        time_range: TimeRange,
        group_by: str | None = None,
    ) -> CostSummary:
        """Get cost summary for a time range.

        Args:
            time_range: Time range to summarize
            group_by: Optional grouping ("model" or "task_type")

        Returns:
            CostSummary with aggregated data
        """
        # Filter requests within time range
        filtered = [
            r
            for r in self._requests
            if time_range.start <= r.timestamp <= time_range.end
        ]

        if not filtered:
            return CostSummary()

        # Calculate totals
        total_cost = sum(r.cost_usd for r in filtered)
        total_tokens = sum(r.total_tokens for r in filtered)
        cached_count = sum(1 for r in filtered if r.cached)
        cache_hit_rate = cached_count / len(filtered) if filtered else 0.0

        summary = CostSummary(
            total_cost_usd=total_cost,
            total_requests=len(filtered),
            total_tokens=total_tokens,
            cached_requests=cached_count,
            cache_hit_rate=cache_hit_rate,
        )

        # Build breakdown if requested
        if group_by:
            breakdown: dict[str, dict[str, Any]] = {}

            for request in filtered:
                key = getattr(request, group_by, None)
                if key is None:
                    continue

                if key not in breakdown:
                    breakdown[key] = {
                        "cost_usd": 0.0,
                        "requests": 0,
                        "tokens": 0,
                    }

                breakdown[key]["cost_usd"] += request.cost_usd
                breakdown[key]["requests"] += 1
                breakdown[key]["tokens"] += request.total_tokens

            summary.breakdown = breakdown

        return summary
