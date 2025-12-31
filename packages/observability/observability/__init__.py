"""
Observability Package for DAW (Deterministic Agentic Workbench).

This package provides comprehensive observability, monitoring, and self-healing
capabilities for the DAW system. It includes:

- Collectors: Metrics, logs, and health data collection
- Storage: Event and metrics storage abstraction (future)
- AI: Local SLM and cloud AI analysis (future)
- Actions: Remediation action registry and execution (future)
- Alerting: Multi-channel alert routing (future)

Part of Epic 13: Holistic Observability & Self-Healing System
See: docs/planning/epics/EPIC-13-OBSERVABILITY.md
"""

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

__version__ = "0.1.0"
__all__ = [
    "HealthChecker",
    "HealthStatus",
    "ProbeConfig",
    "ProbeResult",
    "ProbeType",
    "ServiceStatus",
    "HTTPProbe",
    "TCPProbe",
    "ExecProbe",
    "create_http_health_probe",
    "create_neo4j_probe",
    "create_redis_probe",
]
