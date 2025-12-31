"""Health Check Framework - Unified health probe system.

This module provides:
- Unified HealthChecker class with configurable probes
- HTTP, TCP, and exec probe types
- Aggregate health status calculation
- Dependency health tracking (Neo4j, Redis)
- Graceful degradation indicators
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp
from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    """Status of a service or probe check."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ProbeType(str, Enum):
    """Type of health probe."""

    HTTP = "http"
    TCP = "tcp"
    EXEC = "exec"


class ProbeResult(BaseModel):
    """Result of a single probe check."""

    name: str
    status: ServiceStatus
    probe_type: ProbeType
    latency_ms: float
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class HealthStatus(BaseModel):
    """Aggregate health status of all probes."""

    status: ServiceStatus
    checks: dict[str, ProbeResult]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    degraded_services: list[str] = Field(default_factory=list)
    unhealthy_services: list[str] = Field(default_factory=list)
    healthy_services: list[str] = Field(default_factory=list)
    total_checks: int = 0
    successful_checks: int = 0
    version: str = "1.0.0"


class ProbeConfig(BaseModel):
    """Configuration for a health probe."""

    name: str
    probe_type: ProbeType
    enabled: bool = True
    timeout_seconds: float = 5.0
    interval_seconds: float = 30.0
    failure_threshold: int = 3
    success_threshold: int = 1
    critical: bool = False  # If critical, failure = UNHEALTHY; else DEGRADED

    # HTTP probe settings
    url: str | None = None
    method: str = "GET"
    expected_status_codes: list[int] = Field(default_factory=lambda: [200])
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None

    # TCP probe settings
    host: str | None = None
    port: int | None = None

    # Exec probe settings
    command: list[str] | None = None
    expected_exit_code: int = 0


class Probe(ABC):
    """Abstract base class for health probes."""

    def __init__(self, config: ProbeConfig) -> None:
        self.config = config
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_result: ProbeResult | None = None

    @abstractmethod
    async def check(self) -> ProbeResult:
        """Execute the probe check and return result."""
        pass

    def _create_result(
        self,
        status: ServiceStatus,
        latency_ms: float,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> ProbeResult:
        """Create a probe result and update failure/success counters."""
        if status == ServiceStatus.HEALTHY:
            self._consecutive_successes += 1
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            self._consecutive_successes = 0

        return ProbeResult(
            name=self.config.name,
            status=status,
            probe_type=self.config.probe_type,
            latency_ms=latency_ms,
            message=message,
            details=details or {},
            consecutive_failures=self._consecutive_failures,
            consecutive_successes=self._consecutive_successes,
        )

    def get_effective_status(self) -> ServiceStatus:
        """Get the effective status based on thresholds."""
        if self._consecutive_failures >= self.config.failure_threshold:
            return ServiceStatus.UNHEALTHY if self.config.critical else ServiceStatus.DEGRADED
        if self._consecutive_successes >= self.config.success_threshold:
            return ServiceStatus.HEALTHY
        # In transition state - keep last known status
        if self._last_result:
            return self._last_result.status
        return ServiceStatus.UNKNOWN


class HTTPProbe(Probe):
    """HTTP health probe."""

    def __init__(
        self, config: ProbeConfig, session: aiohttp.ClientSession | None = None
    ) -> None:
        super().__init__(config)
        self._session = session
        self._owns_session = session is None

    async def check(self) -> ProbeResult:
        """Execute HTTP health check."""
        if not self.config.url:
            return self._create_result(
                ServiceStatus.UNHEALTHY,
                0.0,
                "No URL configured for HTTP probe",
            )

        session = self._session
        should_close = False
        if session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            session = aiohttp.ClientSession(timeout=timeout)
            should_close = True

        start_time = asyncio.get_event_loop().time()

        try:
            async with session.request(
                method=self.config.method,
                url=self.config.url,
                headers=self.config.headers,
                data=self.config.body,
            ) as response:
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                if response.status in self.config.expected_status_codes:
                    result = self._create_result(
                        ServiceStatus.HEALTHY,
                        latency_ms,
                        f"HTTP {response.status}",
                        {"status_code": response.status, "url": self.config.url},
                    )
                else:
                    result = self._create_result(
                        ServiceStatus.UNHEALTHY,
                        latency_ms,
                        f"Unexpected status {response.status}, expected {self.config.expected_status_codes}",
                        {"status_code": response.status, "url": self.config.url},
                    )
        except TimeoutError:
            latency_ms = self.config.timeout_seconds * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Timeout after {self.config.timeout_seconds}s",
                {"url": self.config.url},
            )
        except aiohttp.ClientError as e:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Connection error: {e}",
                {"url": self.config.url, "error": str(e)},
            )
        except Exception as e:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Unexpected error: {e}",
                {"url": self.config.url, "error": str(e)},
            )
        finally:
            if should_close and session:
                await session.close()

        self._last_result = result
        return result


class TCPProbe(Probe):
    """TCP socket health probe."""

    async def check(self) -> ProbeResult:
        """Execute TCP health check."""
        if not self.config.host or not self.config.port:
            return self._create_result(
                ServiceStatus.UNHEALTHY,
                0.0,
                "No host/port configured for TCP probe",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Run socket connection in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._tcp_connect,
                    self.config.host,
                    self.config.port,
                ),
                timeout=self.config.timeout_seconds,
            )

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.HEALTHY,
                latency_ms,
                f"TCP connection to {self.config.host}:{self.config.port} successful",
                {"host": self.config.host, "port": self.config.port},
            )
        except TimeoutError:
            latency_ms = self.config.timeout_seconds * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Timeout connecting to {self.config.host}:{self.config.port}",
                {"host": self.config.host, "port": self.config.port},
            )
        except OSError as e:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Connection failed: {e}",
                {"host": self.config.host, "port": self.config.port, "error": str(e)},
            )
        except Exception as e:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Unexpected error: {e}",
                {"host": self.config.host, "port": self.config.port, "error": str(e)},
            )

        self._last_result = result
        return result

    def _tcp_connect(self, host: str, port: int) -> None:
        """Synchronous TCP connection (runs in thread pool)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.config.timeout_seconds)
            sock.connect((host, port))
        finally:
            sock.close()


class ExecProbe(Probe):
    """Execute command health probe."""

    async def check(self) -> ProbeResult:
        """Execute command health check."""
        if not self.config.command:
            return self._create_result(
                ServiceStatus.UNHEALTHY,
                0.0,
                "No command configured for exec probe",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                latency_ms = self.config.timeout_seconds * 1000
                result = self._create_result(
                    ServiceStatus.UNHEALTHY,
                    latency_ms,
                    f"Command timeout after {self.config.timeout_seconds}s",
                    {"command": self.config.command},
                )
                self._last_result = result
                return result

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            if process.returncode == self.config.expected_exit_code:
                result = self._create_result(
                    ServiceStatus.HEALTHY,
                    latency_ms,
                    f"Command exited with code {process.returncode}",
                    {
                        "command": self.config.command,
                        "exit_code": process.returncode,
                        "stdout": stdout.decode("utf-8", errors="replace")[:1000],
                    },
                )
            else:
                result = self._create_result(
                    ServiceStatus.UNHEALTHY,
                    latency_ms,
                    f"Command exited with code {process.returncode}, expected {self.config.expected_exit_code}",
                    {
                        "command": self.config.command,
                        "exit_code": process.returncode,
                        "stdout": stdout.decode("utf-8", errors="replace")[:1000],
                        "stderr": stderr.decode("utf-8", errors="replace")[:1000],
                    },
                )
        except FileNotFoundError:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Command not found: {self.config.command[0]}",
                {"command": self.config.command},
            )
        except Exception as e:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            result = self._create_result(
                ServiceStatus.UNHEALTHY,
                latency_ms,
                f"Unexpected error: {e}",
                {"command": self.config.command, "error": str(e)},
            )

        self._last_result = result
        return result


class HealthChecker:
    """Unified health checker managing multiple probes.

    Example usage:
        ```python
        checker = HealthChecker()
        checker.add_probe(ProbeConfig(
            name="api",
            probe_type=ProbeType.HTTP,
            url="http://localhost:8000/health",
            critical=True,
        ))
        checker.add_probe(ProbeConfig(
            name="redis",
            probe_type=ProbeType.TCP,
            host="localhost",
            port=6379,
        ))

        # Run all probes
        status = await checker.check_all()
        print(status.status)  # healthy, degraded, or unhealthy
        ```
    """

    def __init__(self, version: str = "1.0.0") -> None:
        self._probes: dict[str, Probe] = {}
        self._configs: dict[str, ProbeConfig] = {}
        self._session: aiohttp.ClientSession | None = None
        self._version = version

    def add_probe(self, config: ProbeConfig) -> None:
        """Add a probe with the given configuration."""
        if not config.enabled:
            return

        probe: Probe
        if config.probe_type == ProbeType.HTTP:
            probe = HTTPProbe(config, self._session)
        elif config.probe_type == ProbeType.TCP:
            probe = TCPProbe(config)
        elif config.probe_type == ProbeType.EXEC:
            probe = ExecProbe(config)
        else:
            raise ValueError(f"Unknown probe type: {config.probe_type}")

        self._probes[config.name] = probe
        self._configs[config.name] = config

    def remove_probe(self, name: str) -> None:
        """Remove a probe by name."""
        self._probes.pop(name, None)
        self._configs.pop(name, None)

    def get_probe_config(self, name: str) -> ProbeConfig | None:
        """Get configuration for a probe by name."""
        return self._configs.get(name)

    def list_probes(self) -> list[str]:
        """List all registered probe names."""
        return list(self._probes.keys())

    async def check_one(self, name: str) -> ProbeResult | None:
        """Check a single probe by name."""
        probe = self._probes.get(name)
        if probe is None:
            return None
        return await probe.check()

    async def check_all(self) -> HealthStatus:
        """Execute all probe checks and return aggregate status."""
        if not self._probes:
            return HealthStatus(
                status=ServiceStatus.HEALTHY,
                checks={},
                version=self._version,
            )

        # Run all probes concurrently
        tasks = {name: asyncio.create_task(probe.check()) for name, probe in self._probes.items()}

        results: dict[str, ProbeResult] = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                # If a probe raises unexpectedly, mark it as unhealthy
                config = self._configs[name]
                results[name] = ProbeResult(
                    name=name,
                    status=ServiceStatus.UNHEALTHY,
                    probe_type=config.probe_type,
                    latency_ms=0.0,
                    message=f"Probe execution failed: {e}",
                    details={"error": str(e)},
                )

        # Calculate aggregate status
        healthy_services: list[str] = []
        degraded_services: list[str] = []
        unhealthy_services: list[str] = []
        successful_checks = 0

        for name, result in results.items():
            probe = self._probes[name]
            effective_status = probe.get_effective_status()

            # Update result status based on threshold
            result.status = effective_status

            if effective_status == ServiceStatus.HEALTHY:
                healthy_services.append(name)
                successful_checks += 1
            elif effective_status == ServiceStatus.DEGRADED:
                degraded_services.append(name)
            else:
                unhealthy_services.append(name)

        # Determine overall status
        overall_status = self._calculate_overall_status(
            healthy_services, degraded_services, unhealthy_services
        )

        return HealthStatus(
            status=overall_status,
            checks=results,
            healthy_services=healthy_services,
            degraded_services=degraded_services,
            unhealthy_services=unhealthy_services,
            total_checks=len(results),
            successful_checks=successful_checks,
            version=self._version,
        )

    def _calculate_overall_status(
        self,
        healthy: list[str],
        degraded: list[str],
        unhealthy: list[str],
    ) -> ServiceStatus:
        """Calculate overall health status from individual results."""
        # Check for critical unhealthy services
        for name in unhealthy:
            config = self._configs.get(name)
            if config and config.critical:
                return ServiceStatus.UNHEALTHY

        # Any unhealthy service (non-critical) = degraded
        if unhealthy:
            return ServiceStatus.DEGRADED

        # Any degraded service = degraded
        if degraded:
            return ServiceStatus.DEGRADED

        # All healthy
        if healthy:
            return ServiceStatus.HEALTHY

        return ServiceStatus.UNKNOWN

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any] | list[dict[str, Any]],
        version: str = "1.0.0",
    ) -> HealthChecker:
        """Create a HealthChecker from configuration dict or list.

        Args:
            config: Either a dict with "probes" key containing list of probe configs,
                   or a list of probe configs directly.
            version: Version string for the health status.

        Returns:
            Configured HealthChecker instance.

        Example:
            ```python
            config = {
                "probes": [
                    {"name": "api", "probe_type": "http", "url": "http://localhost:8000/health"},
                    {"name": "redis", "probe_type": "tcp", "host": "localhost", "port": 6379},
                ]
            }
            checker = HealthChecker.from_config(config)
            ```
        """
        checker = cls(version=version)

        if isinstance(config, dict):
            probes_list = config.get("probes", [])
        else:
            probes_list = config

        for probe_config in probes_list:
            checker.add_probe(ProbeConfig(**probe_config))

        return checker

    async def __aenter__(self) -> HealthChecker:
        """Async context manager entry - creates shared HTTP session."""
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        # Update existing HTTP probes with the session
        for probe in self._probes.values():
            if isinstance(probe, HTTPProbe):
                probe._session = self._session
                probe._owns_session = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - closes shared HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None


# Convenience functions for common dependency checks


def create_neo4j_probe(
    host: str = "localhost",
    port: int = 7687,
    name: str = "neo4j",
    critical: bool = True,
    timeout_seconds: float = 5.0,
) -> ProbeConfig:
    """Create a probe configuration for Neo4j health check."""
    return ProbeConfig(
        name=name,
        probe_type=ProbeType.TCP,
        host=host,
        port=port,
        critical=critical,
        timeout_seconds=timeout_seconds,
    )


def create_redis_probe(
    host: str = "localhost",
    port: int = 6379,
    name: str = "redis",
    critical: bool = True,
    timeout_seconds: float = 5.0,
) -> ProbeConfig:
    """Create a probe configuration for Redis health check."""
    return ProbeConfig(
        name=name,
        probe_type=ProbeType.TCP,
        host=host,
        port=port,
        critical=critical,
        timeout_seconds=timeout_seconds,
    )


def create_http_health_probe(
    url: str,
    name: str = "api",
    critical: bool = True,
    timeout_seconds: float = 5.0,
    expected_status_codes: list[int] | None = None,
) -> ProbeConfig:
    """Create a probe configuration for HTTP health endpoint."""
    return ProbeConfig(
        name=name,
        probe_type=ProbeType.HTTP,
        url=url,
        critical=critical,
        timeout_seconds=timeout_seconds,
        expected_status_codes=expected_status_codes or [200],
    )
