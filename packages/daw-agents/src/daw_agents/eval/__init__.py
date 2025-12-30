"""Eval module for agent performance benchmarking.

This module provides the evaluation harness and metrics for measuring
agent performance against golden benchmarks.

Exports:
    - EvalHarness: Main class for running benchmarks
    - EvalConfig: Configuration for the harness
    - BenchmarkResult: Result from a single benchmark run
    - EvalMetrics: Aggregate metrics from evaluation runs
    - ComparisonResult: Result from baseline comparison
    - ThresholdCheck: Individual threshold check result
    - GateLevel: Enum for threshold gate levels
"""

from daw_agents.eval.harness import EvalConfig, EvalHarness
from daw_agents.eval.metrics import (
    BenchmarkResult,
    ComparisonResult,
    EvalMetrics,
    GateLevel,
    ThresholdCheck,
)

__all__ = [
    "EvalHarness",
    "EvalConfig",
    "BenchmarkResult",
    "EvalMetrics",
    "ComparisonResult",
    "ThresholdCheck",
    "GateLevel",
]
