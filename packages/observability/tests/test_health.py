"""Tests for the Health Check Framework.

Tests cover:
- HTTP, TCP, and exec probe types
- Probe configuration and validation
- HealthChecker with multiple probes
- Aggregate health status calculation
- Failure/success thresholds
- Timeout handling
- Graceful degradation
"""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from observability.collectors.health import (
    ExecProbe,
    HealthChecker,
    HealthStatus,
    HTTPProbe,
    ProbeConfig,
    ProbeResult,
    ProbeType,
    ServiceStatus,
    TCPProbe,
    create_http_health_probe,
    create_neo4j_probe,
    create_redis_probe,
)


# =============================================================================
# ProbeConfig Tests
# =============================================================================


class TestProbeConfig:
    """Tests for ProbeConfig model."""

    def test_http_probe_config_defaults(self) -> None:
        """Test HTTP probe config with defaults."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
        )
        assert config.name == "api"
        assert config.probe_type == ProbeType.HTTP
        assert config.enabled is True
        assert config.timeout_seconds == 5.0
        assert config.interval_seconds == 30.0
        assert config.failure_threshold == 3
        assert config.success_threshold == 1
        assert config.critical is False
        assert config.method == "GET"
        assert config.expected_status_codes == [200]

    def test_tcp_probe_config(self) -> None:
        """Test TCP probe config."""
        config = ProbeConfig(
            name="redis",
            probe_type=ProbeType.TCP,
            host="localhost",
            port=6379,
            critical=True,
        )
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.critical is True

    def test_exec_probe_config(self) -> None:
        """Test exec probe config."""
        config = ProbeConfig(
            name="disk-check",
            probe_type=ProbeType.EXEC,
            command=["df", "-h", "/"],
            expected_exit_code=0,
        )
        assert config.command == ["df", "-h", "/"]
        assert config.expected_exit_code == 0


# =============================================================================
# ProbeResult Tests
# =============================================================================


class TestProbeResult:
    """Tests for ProbeResult model."""

    def test_probe_result_defaults(self) -> None:
        """Test ProbeResult with defaults."""
        result = ProbeResult(
            name="test",
            status=ServiceStatus.HEALTHY,
            probe_type=ProbeType.HTTP,
            latency_ms=50.5,
        )
        assert result.name == "test"
        assert result.status == ServiceStatus.HEALTHY
        assert result.latency_ms == 50.5
        assert result.message == ""
        assert result.details == {}
        assert result.consecutive_failures == 0
        assert result.consecutive_successes == 0
        assert isinstance(result.timestamp, datetime)

    def test_probe_result_with_details(self) -> None:
        """Test ProbeResult with details."""
        result = ProbeResult(
            name="api",
            status=ServiceStatus.UNHEALTHY,
            probe_type=ProbeType.HTTP,
            latency_ms=5000.0,
            message="Timeout",
            details={"url": "http://localhost:8000/health", "error": "Connection timeout"},
        )
        assert result.message == "Timeout"
        assert result.details["url"] == "http://localhost:8000/health"


# =============================================================================
# HealthStatus Tests
# =============================================================================


class TestHealthStatus:
    """Tests for HealthStatus model."""

    def test_health_status_healthy(self) -> None:
        """Test healthy status."""
        status = HealthStatus(
            status=ServiceStatus.HEALTHY,
            checks={},
            healthy_services=["api", "redis"],
            total_checks=2,
            successful_checks=2,
        )
        assert status.status == ServiceStatus.HEALTHY
        assert len(status.healthy_services) == 2
        assert status.degraded_services == []
        assert status.unhealthy_services == []

    def test_health_status_degraded(self) -> None:
        """Test degraded status."""
        status = HealthStatus(
            status=ServiceStatus.DEGRADED,
            checks={},
            healthy_services=["api"],
            degraded_services=["redis"],
            total_checks=2,
            successful_checks=1,
        )
        assert status.status == ServiceStatus.DEGRADED
        assert "redis" in status.degraded_services


# =============================================================================
# HTTPProbe Tests
# =============================================================================


class TestHTTPProbe:
    """Tests for HTTPProbe."""

    @pytest.mark.asyncio
    async def test_http_probe_success(self) -> None:
        """Test successful HTTP probe."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
        )
        probe = HTTPProbe(config)

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            result = await probe.check()

        assert result.status == ServiceStatus.HEALTHY
        assert result.name == "api"
        assert result.probe_type == ProbeType.HTTP
        assert result.latency_ms > 0
        assert "200" in result.message

    @pytest.mark.asyncio
    async def test_http_probe_expected_status_codes(self) -> None:
        """Test HTTP probe with custom expected status codes."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
            expected_status_codes=[200, 201, 204],
        )
        probe = HTTPProbe(config)

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=201)
            result = await probe.check()

        assert result.status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_http_probe_unexpected_status(self) -> None:
        """Test HTTP probe with unexpected status code."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
        )
        probe = HTTPProbe(config)

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "500" in result.message
        assert result.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_http_probe_connection_error(self) -> None:
        """Test HTTP probe with connection error."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
        )
        probe = HTTPProbe(config)

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", exception=Exception("Connection refused"))
            result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "error" in result.message.lower() or "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_http_probe_timeout(self) -> None:
        """Test HTTP probe timeout."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
            timeout_seconds=0.1,
        )
        probe = HTTPProbe(config)

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", exception=asyncio.TimeoutError())
            result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "timeout" in result.message.lower()

    @pytest.mark.asyncio
    async def test_http_probe_no_url(self) -> None:
        """Test HTTP probe without URL configured."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
        )
        probe = HTTPProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "No URL configured" in result.message

    @pytest.mark.asyncio
    async def test_http_probe_post_method(self) -> None:
        """Test HTTP probe with POST method."""
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
            method="POST",
            body='{"check": "health"}',
        )
        probe = HTTPProbe(config)

        with aioresponses() as mocked:
            mocked.post("http://localhost:8000/health", status=200)
            result = await probe.check()

        assert result.status == ServiceStatus.HEALTHY


# =============================================================================
# TCPProbe Tests
# =============================================================================


class TestTCPProbe:
    """Tests for TCPProbe."""

    @pytest.mark.asyncio
    async def test_tcp_probe_success(self) -> None:
        """Test successful TCP probe."""
        config = ProbeConfig(
            name="redis",
            probe_type=ProbeType.TCP,
            host="localhost",
            port=6379,
        )
        probe = TCPProbe(config)

        # Mock the socket connection
        with patch.object(probe, "_tcp_connect") as mock_connect:
            mock_connect.return_value = None
            result = await probe.check()

        assert result.status == ServiceStatus.HEALTHY
        assert result.name == "redis"
        assert result.probe_type == ProbeType.TCP
        assert "successful" in result.message

    @pytest.mark.asyncio
    async def test_tcp_probe_connection_refused(self) -> None:
        """Test TCP probe with connection refused."""
        config = ProbeConfig(
            name="redis",
            probe_type=ProbeType.TCP,
            host="localhost",
            port=59999,  # Unlikely to be open
            timeout_seconds=0.5,
        )
        probe = TCPProbe(config)

        with patch.object(probe, "_tcp_connect", side_effect=OSError("Connection refused")):
            result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "Connection refused" in result.message or "failed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_tcp_probe_timeout(self) -> None:
        """Test TCP probe timeout."""
        config = ProbeConfig(
            name="redis",
            probe_type=ProbeType.TCP,
            host="10.255.255.1",  # Non-routable address for timeout
            port=6379,
            timeout_seconds=0.1,
        )
        probe = TCPProbe(config)

        # Create a mock that simulates timeout by sleeping longer than timeout
        async def slow_connect(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(1.0)

        with patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError()):
            result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "timeout" in result.message.lower()

    @pytest.mark.asyncio
    async def test_tcp_probe_no_host(self) -> None:
        """Test TCP probe without host configured."""
        config = ProbeConfig(
            name="redis",
            probe_type=ProbeType.TCP,
        )
        probe = TCPProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "No host/port configured" in result.message


# =============================================================================
# ExecProbe Tests
# =============================================================================


class TestExecProbe:
    """Tests for ExecProbe."""

    @pytest.mark.asyncio
    async def test_exec_probe_success(self) -> None:
        """Test successful exec probe."""
        config = ProbeConfig(
            name="disk-check",
            probe_type=ProbeType.EXEC,
            command=["echo", "healthy"],
        )
        probe = ExecProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.HEALTHY
        assert result.name == "disk-check"
        assert result.probe_type == ProbeType.EXEC
        assert "exited with code 0" in result.message

    @pytest.mark.asyncio
    async def test_exec_probe_failure(self) -> None:
        """Test exec probe with non-zero exit code."""
        config = ProbeConfig(
            name="false-check",
            probe_type=ProbeType.EXEC,
            command=["false"],  # Always exits with 1
        )
        probe = ExecProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "expected 0" in result.message

    @pytest.mark.asyncio
    async def test_exec_probe_custom_exit_code(self) -> None:
        """Test exec probe with custom expected exit code."""
        config = ProbeConfig(
            name="custom-check",
            probe_type=ProbeType.EXEC,
            command=["sh", "-c", "exit 42"],
            expected_exit_code=42,
        )
        probe = ExecProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_exec_probe_command_not_found(self) -> None:
        """Test exec probe with non-existent command."""
        config = ProbeConfig(
            name="missing-cmd",
            probe_type=ProbeType.EXEC,
            command=["nonexistent_command_xyz123"],
        )
        probe = ExecProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_exec_probe_timeout(self) -> None:
        """Test exec probe timeout."""
        config = ProbeConfig(
            name="slow-cmd",
            probe_type=ProbeType.EXEC,
            command=["sleep", "10"],
            timeout_seconds=0.1,
        )
        probe = ExecProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "timeout" in result.message.lower()

    @pytest.mark.asyncio
    async def test_exec_probe_no_command(self) -> None:
        """Test exec probe without command configured."""
        config = ProbeConfig(
            name="empty",
            probe_type=ProbeType.EXEC,
        )
        probe = ExecProbe(config)
        result = await probe.check()

        assert result.status == ServiceStatus.UNHEALTHY
        assert "No command configured" in result.message


# =============================================================================
# HealthChecker Tests
# =============================================================================


class TestHealthChecker:
    """Tests for HealthChecker."""

    def test_add_probe(self) -> None:
        """Test adding probes to checker."""
        checker = HealthChecker()
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
        )
        checker.add_probe(config)

        assert "api" in checker.list_probes()
        assert checker.get_probe_config("api") == config

    def test_add_disabled_probe(self) -> None:
        """Test adding disabled probe (should be skipped)."""
        checker = HealthChecker()
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
            enabled=False,
        )
        checker.add_probe(config)

        assert "api" not in checker.list_probes()

    def test_remove_probe(self) -> None:
        """Test removing probes from checker."""
        checker = HealthChecker()
        config = ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
        )
        checker.add_probe(config)
        checker.remove_probe("api")

        assert "api" not in checker.list_probes()

    def test_remove_nonexistent_probe(self) -> None:
        """Test removing non-existent probe (should not raise)."""
        checker = HealthChecker()
        checker.remove_probe("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_check_all_healthy(self) -> None:
        """Test check_all with all healthy probes."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
            )
        )
        checker.add_probe(
            ProbeConfig(
                name="echo",
                probe_type=ProbeType.EXEC,
                command=["echo", "ok"],
            )
        )

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            status = await checker.check_all()

        assert status.status == ServiceStatus.HEALTHY
        assert status.total_checks == 2
        assert status.successful_checks == 2
        assert len(status.healthy_services) == 2

    @pytest.mark.asyncio
    async def test_check_all_degraded(self) -> None:
        """Test check_all with degraded probes (non-critical failures)."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
                critical=True,
            )
        )
        checker.add_probe(
            ProbeConfig(
                name="non-critical",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8001/health",
                critical=False,
                failure_threshold=1,  # Fail immediately
            )
        )

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            mocked.get("http://localhost:8001/health", status=500)
            status = await checker.check_all()

        assert status.status == ServiceStatus.DEGRADED
        assert "api" in status.healthy_services
        assert "non-critical" in status.degraded_services

    @pytest.mark.asyncio
    async def test_check_all_unhealthy_critical(self) -> None:
        """Test check_all with critical probe failure."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="critical-api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
                critical=True,
                failure_threshold=1,
            )
        )

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            status = await checker.check_all()

        assert status.status == ServiceStatus.UNHEALTHY
        assert "critical-api" in status.unhealthy_services

    @pytest.mark.asyncio
    async def test_check_all_empty(self) -> None:
        """Test check_all with no probes."""
        checker = HealthChecker()
        status = await checker.check_all()

        assert status.status == ServiceStatus.HEALTHY
        assert status.total_checks == 0

    @pytest.mark.asyncio
    async def test_check_one(self) -> None:
        """Test checking a single probe."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
            )
        )

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            result = await checker.check_one("api")

        assert result is not None
        assert result.status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_one_nonexistent(self) -> None:
        """Test checking a non-existent probe."""
        checker = HealthChecker()
        result = await checker.check_one("nonexistent")

        assert result is None

    def test_from_config_dict(self) -> None:
        """Test creating checker from config dict."""
        config = {
            "probes": [
                {"name": "api", "probe_type": "http", "url": "http://localhost:8000/health"},
                {"name": "redis", "probe_type": "tcp", "host": "localhost", "port": 6379},
            ]
        }
        checker = HealthChecker.from_config(config)

        assert "api" in checker.list_probes()
        assert "redis" in checker.list_probes()

    def test_from_config_list(self) -> None:
        """Test creating checker from config list."""
        config = [
            {"name": "api", "probe_type": "http", "url": "http://localhost:8000/health"},
            {"name": "redis", "probe_type": "tcp", "host": "localhost", "port": 6379},
        ]
        checker = HealthChecker.from_config(config, version="2.0.0")

        assert "api" in checker.list_probes()
        assert "redis" in checker.list_probes()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test checker as context manager."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
            )
        )

        async with checker as cm:
            assert cm._session is not None
            with aioresponses() as mocked:
                mocked.get("http://localhost:8000/health", status=200)
                status = await cm.check_all()
            assert status.status == ServiceStatus.HEALTHY

        assert checker._session is None


# =============================================================================
# Threshold Tests
# =============================================================================


class TestThresholds:
    """Tests for failure/success thresholds."""

    @pytest.mark.asyncio
    async def test_failure_threshold(self) -> None:
        """Test that status changes after failure threshold is reached."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
                failure_threshold=3,
                critical=True,
            )
        )

        # First failure - should not be unhealthy yet
        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            status = await checker.check_all()
        # Not enough failures yet
        assert status.checks["api"].consecutive_failures == 1

        # Second failure
        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            status = await checker.check_all()
        assert status.checks["api"].consecutive_failures == 2

        # Third failure - threshold reached
        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            status = await checker.check_all()
        assert status.checks["api"].consecutive_failures == 3
        assert status.status == ServiceStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_success_resets_failures(self) -> None:
        """Test that success resets failure counter."""
        checker = HealthChecker()
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
                failure_threshold=3,
            )
        )

        # Two failures
        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            await checker.check_all()

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=500)
            status = await checker.check_all()
        assert status.checks["api"].consecutive_failures == 2

        # Success resets counter
        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            status = await checker.check_all()
        assert status.checks["api"].consecutive_failures == 0
        assert status.checks["api"].consecutive_successes == 1


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience probe creation functions."""

    def test_create_neo4j_probe(self) -> None:
        """Test Neo4j probe creation."""
        config = create_neo4j_probe(host="neo4j.local", port=7687)
        assert config.name == "neo4j"
        assert config.probe_type == ProbeType.TCP
        assert config.host == "neo4j.local"
        assert config.port == 7687
        assert config.critical is True

    def test_create_redis_probe(self) -> None:
        """Test Redis probe creation."""
        config = create_redis_probe(host="redis.local", port=6380, critical=False)
        assert config.name == "redis"
        assert config.probe_type == ProbeType.TCP
        assert config.host == "redis.local"
        assert config.port == 6380
        assert config.critical is False

    def test_create_http_health_probe(self) -> None:
        """Test HTTP health probe creation."""
        config = create_http_health_probe(
            url="http://api.local/health",
            name="main-api",
            expected_status_codes=[200, 201],
        )
        assert config.name == "main-api"
        assert config.probe_type == ProbeType.HTTP
        assert config.url == "http://api.local/health"
        assert config.expected_status_codes == [200, 201]


# =============================================================================
# Integration-like Tests (Mocked)
# =============================================================================


class TestIntegrationScenarios:
    """Integration-like scenarios with mocked services."""

    @pytest.mark.asyncio
    async def test_full_health_check_scenario(self) -> None:
        """Test a full health check scenario with multiple services."""
        checker = HealthChecker(version="1.2.3")

        # Add multiple probes
        checker.add_probe(create_http_health_probe("http://localhost:8000/health", name="api"))
        checker.add_probe(create_redis_probe())
        checker.add_probe(create_neo4j_probe())
        checker.add_probe(
            ProbeConfig(
                name="disk",
                probe_type=ProbeType.EXEC,
                command=["echo", "ok"],
            )
        )

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            # Mock TCP probes
            with patch.object(TCPProbe, "_tcp_connect"):
                status = await checker.check_all()

        assert status.version == "1.2.3"
        assert status.total_checks == 4
        assert len(status.checks) == 4
        assert isinstance(status.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_graceful_degradation_scenario(self) -> None:
        """Test graceful degradation when non-critical services fail."""
        checker = HealthChecker()

        # Critical API
        checker.add_probe(
            ProbeConfig(
                name="api",
                probe_type=ProbeType.HTTP,
                url="http://localhost:8000/health",
                critical=True,
            )
        )
        # Non-critical cache
        checker.add_probe(
            ProbeConfig(
                name="cache",
                probe_type=ProbeType.TCP,
                host="localhost",
                port=6379,
                critical=False,
                failure_threshold=1,
            )
        )

        with aioresponses() as mocked:
            mocked.get("http://localhost:8000/health", status=200)
            with patch.object(
                TCPProbe, "_tcp_connect", side_effect=OSError("Connection refused")
            ):
                status = await checker.check_all()

        # System is degraded but not unhealthy
        assert status.status == ServiceStatus.DEGRADED
        assert "api" in status.healthy_services
        assert "cache" in status.degraded_services

    @pytest.mark.asyncio
    async def test_concurrent_probes(self) -> None:
        """Test that probes run concurrently."""
        checker = HealthChecker()

        # Add multiple slow probes
        for i in range(5):
            checker.add_probe(
                ProbeConfig(
                    name=f"api-{i}",
                    probe_type=ProbeType.HTTP,
                    url=f"http://localhost:800{i}/health",
                )
            )

        import time

        start = time.time()

        with aioresponses() as mocked:
            for i in range(5):
                mocked.get(f"http://localhost:800{i}/health", status=200)
            await checker.check_all()

        elapsed = time.time() - start
        # If probes were sequential with 5s timeout each, this would take 25s
        # Concurrent execution should be much faster
        assert elapsed < 5.0  # Should complete much faster than sequential
