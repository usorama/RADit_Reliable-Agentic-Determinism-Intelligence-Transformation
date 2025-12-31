"""
Tests for Helicone Observability module (OPS-001).

These tests verify:
1. HeliconeConfig - Configuration model with API key and proxy URL
2. HeliconeHeaders - Header builder for LLM requests with caching support
3. HeliconeTracker - Request tracking and cost aggregation
4. Integration with existing ModelRouter patterns

Based on Helicone SDK documentation for Python/LiteLLM integration.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from daw_agents.ops.helicone import (
    CacheConfig,
    HeliconeConfig,
    HeliconeHeaders,
    HeliconeTracker,
    RequestMetadata,
    TimeRange,
    TrackedRequest,
)


class TestHeliconeConfig:
    """Test HeliconeConfig Pydantic model."""

    def test_config_creation_with_all_fields(self) -> None:
        """Test creating HeliconeConfig with all fields specified."""
        config = HeliconeConfig(
            api_key="hlc_test_key_123",
            base_url="https://oai.helicone.ai/v1",
            enabled=True,
        )
        assert config.api_key == "hlc_test_key_123"
        assert config.base_url == "https://oai.helicone.ai/v1"
        assert config.enabled is True

    def test_config_default_values(self) -> None:
        """Test HeliconeConfig uses sensible defaults."""
        config = HeliconeConfig(api_key="hlc_test_key")
        assert config.base_url == "https://oai.helicone.ai/v1"
        assert config.enabled is True

    def test_config_disabled_when_no_api_key(self) -> None:
        """Test that config is disabled when api_key is None or empty."""
        config = HeliconeConfig(api_key=None)
        assert config.enabled is False

        config_empty = HeliconeConfig(api_key="")
        assert config_empty.enabled is False

    def test_config_from_environment(self) -> None:
        """Test loading config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "HELICONE_API_KEY": "env_test_key",
                "HELICONE_BASE_URL": "https://custom.helicone.ai/v1",
            },
        ):
            config = HeliconeConfig.from_env()
            assert config.api_key == "env_test_key"
            assert config.base_url == "https://custom.helicone.ai/v1"

    def test_config_from_environment_defaults(self) -> None:
        """Test loading config from environment with defaults."""
        with patch.dict(os.environ, {"HELICONE_API_KEY": "test_key"}, clear=True):
            config = HeliconeConfig.from_env()
            assert config.api_key == "test_key"
            assert config.base_url == "https://oai.helicone.ai/v1"


class TestCacheConfig:
    """Test CacheConfig for Helicone caching settings."""

    def test_cache_config_creation(self) -> None:
        """Test creating CacheConfig with all fields."""
        config = CacheConfig(
            enabled=True,
            max_age_seconds=3600,
            bucket_max_size=5,
            seed="user-123",
        )
        assert config.enabled is True
        assert config.max_age_seconds == 3600
        assert config.bucket_max_size == 5
        assert config.seed == "user-123"

    def test_cache_config_defaults(self) -> None:
        """Test CacheConfig default values."""
        config = CacheConfig()
        assert config.enabled is False
        assert config.max_age_seconds == 2592000  # 30 days default
        assert config.bucket_max_size == 1
        assert config.seed is None


class TestRequestMetadata:
    """Test RequestMetadata for tracking request context."""

    def test_request_metadata_creation(self) -> None:
        """Test creating RequestMetadata with all fields."""
        metadata = RequestMetadata(
            user_id="user-123",
            session_id="session-456",
            project_id="project-789",
            agent_type="planner",
            custom_properties={"feature": "chat", "version": "1.0"},
        )
        assert metadata.user_id == "user-123"
        assert metadata.session_id == "session-456"
        assert metadata.project_id == "project-789"
        assert metadata.agent_type == "planner"
        assert metadata.custom_properties["feature"] == "chat"

    def test_request_metadata_partial(self) -> None:
        """Test creating RequestMetadata with partial fields."""
        metadata = RequestMetadata(user_id="user-123")
        assert metadata.user_id == "user-123"
        assert metadata.session_id is None
        assert metadata.custom_properties == {}


class TestHeliconeHeaders:
    """Test HeliconeHeaders builder for LLM requests."""

    def test_build_auth_header(self) -> None:
        """Test building basic auth header."""
        config = HeliconeConfig(api_key="hlc_test_key")
        headers = HeliconeHeaders(config=config)
        result = headers.build()

        assert "Helicone-Auth" in result
        assert result["Helicone-Auth"] == "Bearer hlc_test_key"

    def test_build_with_metadata(self) -> None:
        """Test building headers with request metadata."""
        config = HeliconeConfig(api_key="hlc_test_key")
        metadata = RequestMetadata(
            user_id="user-123",
            session_id="session-456",
            project_id="project-789",
            agent_type="executor",
        )
        headers = HeliconeHeaders(config=config, metadata=metadata)
        result = headers.build()

        assert result["Helicone-User-Id"] == "user-123"
        assert result["Helicone-Session-Id"] == "session-456"
        assert result["Helicone-Property-Project"] == "project-789"
        assert result["Helicone-Property-Agent-Type"] == "executor"

    def test_build_with_custom_properties(self) -> None:
        """Test building headers with custom properties."""
        config = HeliconeConfig(api_key="hlc_test_key")
        metadata = RequestMetadata(
            user_id="user-123",
            custom_properties={
                "task_id": "CORE-001",
                "workflow_id": "wf-123",
            },
        )
        headers = HeliconeHeaders(config=config, metadata=metadata)
        result = headers.build()

        assert result["Helicone-Property-Task-Id"] == "CORE-001"
        assert result["Helicone-Property-Workflow-Id"] == "wf-123"

    def test_build_with_caching_enabled(self) -> None:
        """Test building headers with caching enabled."""
        config = HeliconeConfig(api_key="hlc_test_key")
        cache_config = CacheConfig(
            enabled=True,
            max_age_seconds=3600,
            bucket_max_size=3,
            seed="cache-seed-123",
        )
        headers = HeliconeHeaders(config=config, cache_config=cache_config)
        result = headers.build()

        assert result["Helicone-Cache-Enabled"] == "true"
        assert result["Cache-Control"] == "max-age=3600"
        assert result["Helicone-Cache-Bucket-Max-Size"] == "3"
        assert result["Helicone-Cache-Seed"] == "cache-seed-123"

    def test_build_with_caching_disabled(self) -> None:
        """Test that caching headers are not included when disabled."""
        config = HeliconeConfig(api_key="hlc_test_key")
        cache_config = CacheConfig(enabled=False)
        headers = HeliconeHeaders(config=config, cache_config=cache_config)
        result = headers.build()

        assert "Helicone-Cache-Enabled" not in result
        assert "Cache-Control" not in result

    def test_build_returns_empty_when_disabled(self) -> None:
        """Test that no headers are returned when Helicone is disabled."""
        config = HeliconeConfig(api_key=None)  # Disabled
        headers = HeliconeHeaders(config=config)
        result = headers.build()

        assert result == {}

    def test_property_name_normalization(self) -> None:
        """Test that custom property names are normalized correctly."""
        config = HeliconeConfig(api_key="hlc_test_key")
        metadata = RequestMetadata(
            custom_properties={
                "snake_case_name": "value1",
                "kebab-case-name": "value2",
                "CamelCaseName": "value3",
            },
        )
        headers = HeliconeHeaders(config=config, metadata=metadata)
        result = headers.build()

        # Property names should be normalized to Title-Case
        assert "Helicone-Property-Snake-Case-Name" in result
        assert "Helicone-Property-Kebab-Case-Name" in result
        assert "Helicone-Property-Camelcasename" in result


class TestTrackedRequest:
    """Test TrackedRequest model for storing request data."""

    def test_tracked_request_creation(self) -> None:
        """Test creating TrackedRequest with all fields."""
        now = datetime.now(timezone.utc)
        request = TrackedRequest(
            request_id="req-123",
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
            cached=False,
            timestamp=now,
            metadata={"user_id": "user-123"},
        )
        assert request.request_id == "req-123"
        assert request.model == "gpt-4o"
        assert request.tokens_prompt == 100
        assert request.tokens_completion == 50
        assert request.cost_usd == 0.015
        assert request.latency_ms == 1500
        assert request.cached is False

    def test_tracked_request_total_tokens(self) -> None:
        """Test total_tokens property."""
        request = TrackedRequest(
            request_id="req-123",
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
        )
        assert request.total_tokens == 150


class TestTimeRange:
    """Test TimeRange model for cost summary queries."""

    def test_time_range_creation(self) -> None:
        """Test creating TimeRange with start and end times."""
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        time_range = TimeRange(start=start, end=end)
        assert time_range.start == start
        assert time_range.end == end

    def test_time_range_last_hour(self) -> None:
        """Test creating TimeRange for last hour."""
        time_range = TimeRange.last_hour()
        now = datetime.now(timezone.utc)
        assert (now - time_range.end).total_seconds() < 2
        assert (now - time_range.start).total_seconds() >= 3598  # ~1 hour

    def test_time_range_last_day(self) -> None:
        """Test creating TimeRange for last 24 hours."""
        time_range = TimeRange.last_day()
        now = datetime.now(timezone.utc)
        assert (now - time_range.end).total_seconds() < 2
        assert (now - time_range.start).total_seconds() >= 86398  # ~24 hours


class TestHeliconeTracker:
    """Test HeliconeTracker for request tracking and cost aggregation."""

    @pytest.fixture
    def tracker(self) -> HeliconeTracker:
        """Create a HeliconeTracker instance for testing."""
        config = HeliconeConfig(api_key="hlc_test_key")
        return HeliconeTracker(config=config)

    def test_tracker_initialization(self, tracker: HeliconeTracker) -> None:
        """Test that tracker initializes correctly."""
        assert tracker.config.api_key == "hlc_test_key"
        assert tracker._requests == []

    def test_track_request(self, tracker: HeliconeTracker) -> None:
        """Test tracking a request."""
        request_id = tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
            metadata={"user_id": "user-123", "project_id": "proj-456"},
        )

        assert request_id is not None
        assert len(tracker._requests) == 1
        tracked = tracker._requests[0]
        assert tracked.model == "gpt-4o"
        assert tracked.tokens_prompt == 100
        assert tracked.cost_usd == 0.015

    def test_get_cost_summary_empty(self, tracker: HeliconeTracker) -> None:
        """Test getting cost summary with no requests."""
        time_range = TimeRange.last_hour()
        summary = tracker.get_cost_summary(time_range)

        assert summary.total_cost_usd == 0.0
        assert summary.total_requests == 0
        assert summary.total_tokens == 0

    def test_get_cost_summary_with_requests(self, tracker: HeliconeTracker) -> None:
        """Test getting cost summary with tracked requests."""
        # Track some requests
        tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
        )
        tracker.track_request(
            model="claude-3-5-sonnet",
            task_type="planning",
            tokens_prompt=200,
            tokens_completion=100,
            cost_usd=0.025,
            latency_ms=2000,
        )

        time_range = TimeRange.last_hour()
        summary = tracker.get_cost_summary(time_range)

        assert summary.total_cost_usd == 0.040  # 0.015 + 0.025
        assert summary.total_requests == 2
        assert summary.total_tokens == 450  # 150 + 300

    def test_get_cost_summary_by_model(self, tracker: HeliconeTracker) -> None:
        """Test getting cost summary grouped by model."""
        tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
        )
        tracker.track_request(
            model="gpt-4o",
            task_type="validation",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
        )
        tracker.track_request(
            model="claude-3-5-sonnet",
            task_type="planning",
            tokens_prompt=200,
            tokens_completion=100,
            cost_usd=0.025,
            latency_ms=2000,
        )

        time_range = TimeRange.last_hour()
        summary = tracker.get_cost_summary(time_range, group_by="model")

        assert "gpt-4o" in summary.breakdown
        assert "claude-3-5-sonnet" in summary.breakdown
        assert summary.breakdown["gpt-4o"]["cost_usd"] == 0.030
        assert summary.breakdown["claude-3-5-sonnet"]["cost_usd"] == 0.025

    def test_get_cost_summary_by_task_type(self, tracker: HeliconeTracker) -> None:
        """Test getting cost summary grouped by task type."""
        tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
        )
        tracker.track_request(
            model="claude-3-5-sonnet",
            task_type="coding",
            tokens_prompt=150,
            tokens_completion=75,
            cost_usd=0.020,
            latency_ms=1800,
        )
        tracker.track_request(
            model="gpt-4o",
            task_type="planning",
            tokens_prompt=200,
            tokens_completion=100,
            cost_usd=0.025,
            latency_ms=2000,
        )

        time_range = TimeRange.last_hour()
        summary = tracker.get_cost_summary(time_range, group_by="task_type")

        assert "coding" in summary.breakdown
        assert "planning" in summary.breakdown
        assert summary.breakdown["coding"]["cost_usd"] == 0.035
        assert summary.breakdown["planning"]["cost_usd"] == 0.025

    def test_get_cost_summary_time_filtering(self, tracker: HeliconeTracker) -> None:
        """Test that cost summary respects time range filtering."""
        now = datetime.now(timezone.utc)

        # Track a request from 2 hours ago (outside last hour)
        old_request = TrackedRequest(
            request_id="old-req",
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
            timestamp=now - timedelta(hours=2),
        )
        tracker._requests.append(old_request)

        # Track a recent request (within last hour)
        tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.020,
            latency_ms=1500,
        )

        time_range = TimeRange.last_hour()
        summary = tracker.get_cost_summary(time_range)

        # Only the recent request should be included
        assert summary.total_cost_usd == 0.020
        assert summary.total_requests == 1

    def test_get_cached_request_stats(self, tracker: HeliconeTracker) -> None:
        """Test getting statistics about cached requests."""
        tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.015,
            latency_ms=1500,
            cached=False,
        )
        tracker.track_request(
            model="gpt-4o",
            task_type="coding",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.0,  # Cached, no cost
            latency_ms=50,  # Much faster
            cached=True,
        )

        time_range = TimeRange.last_hour()
        summary = tracker.get_cost_summary(time_range)

        assert summary.cached_requests == 1
        assert summary.cache_hit_rate == 0.5  # 1 out of 2


class TestIntegrationWithModelRouter:
    """Test integration patterns with existing ModelRouter."""

    def test_headers_compatible_with_litellm_metadata(self) -> None:
        """Test that headers can be passed as LiteLLM metadata."""
        config = HeliconeConfig(api_key="hlc_test_key")
        metadata = RequestMetadata(
            user_id="user-123",
            agent_type="executor",
            custom_properties={"task_id": "CORE-001"},
        )
        headers = HeliconeHeaders(config=config, metadata=metadata)
        result = headers.build()

        # LiteLLM expects headers to be string keys/values
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_headers_compatible_with_openai_extra_headers(self) -> None:
        """Test that headers are compatible with OpenAI client extra_headers."""
        config = HeliconeConfig(api_key="hlc_test_key")
        cache_config = CacheConfig(enabled=True, max_age_seconds=3600)
        headers = HeliconeHeaders(config=config, cache_config=cache_config)
        result = headers.build()

        # OpenAI extra_headers expects dict[str, str]
        assert isinstance(result, dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
