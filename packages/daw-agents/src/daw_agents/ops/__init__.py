"""
Operations and observability modules for DAW Agent Workbench.

This package provides:
- Helicone integration for LLM cost tracking and observability
- Request tracking and cost aggregation
- Caching configuration
- Drift detection for monitoring agent behavior
"""

from daw_agents.ops.drift_detector import (
    BaselineConfig,
    DriftAction,
    DriftDetector,
    DriftMetric,
    DriftSeverity,
    MetricType,
    TaskMetrics,
)
from daw_agents.ops.helicone import (
    CacheConfig,
    CostSummary,
    HeliconeConfig,
    HeliconeHeaders,
    HeliconeTracker,
    RequestMetadata,
    TimeRange,
    TrackedRequest,
)

__all__ = [
    # Drift Detection
    "BaselineConfig",
    "DriftAction",
    "DriftDetector",
    "DriftMetric",
    "DriftSeverity",
    "MetricType",
    "TaskMetrics",
    # Helicone
    "CacheConfig",
    "CostSummary",
    "HeliconeConfig",
    "HeliconeHeaders",
    "HeliconeTracker",
    "RequestMetadata",
    "TimeRange",
    "TrackedRequest",
]
