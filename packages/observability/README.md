# DAW Observability

Health checks, metrics collection, and self-healing framework for the Deterministic Agentic Workbench.

## Features

- **Unified Health Check Framework**: HTTP, TCP, and exec probe types
- **Configurable Probes**: Thresholds, intervals, and timeouts
- **Dependency Tracking**: Built-in support for Neo4j, Redis
- **Graceful Degradation**: Critical vs non-critical service classification
- **Aggregate Health Status**: Overall system health calculation

## Installation

```bash
poetry add daw-observability
```

## Quick Start

```python
from observability import HealthChecker, ProbeConfig, ProbeType

# Create checker
checker = HealthChecker()

# Add probes
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

# Run health check
status = await checker.check_all()
print(f"Status: {status.status}")
print(f"Healthy: {status.healthy_services}")
print(f"Degraded: {status.degraded_services}")
```

## Configuration

Probes can be configured from a dictionary:

```python
config = {
    "probes": [
        {"name": "api", "probe_type": "http", "url": "http://localhost:8000/health"},
        {"name": "redis", "probe_type": "tcp", "host": "localhost", "port": 6379},
        {"name": "disk", "probe_type": "exec", "command": ["df", "-h", "/"]},
    ]
}
checker = HealthChecker.from_config(config)
```

## License

MIT
