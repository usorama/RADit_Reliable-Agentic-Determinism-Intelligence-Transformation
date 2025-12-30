"""Metrics models for evaluation harness.

This module defines Pydantic models for:
- BenchmarkResult: Individual benchmark execution results
- EvalMetrics: Aggregate metrics from evaluation runs
- ThresholdCheck: Individual threshold verification results
- ComparisonResult: Baseline comparison results
- GateLevel: Enum for threshold gate levels
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class GateLevel(str, Enum):
    """Gate level for threshold checks.

    Attributes:
        RELEASE_BLOCKING: Failure blocks release
        WARNING: Failure triggers warning but allows release
        ADVISORY: Informational only
    """

    RELEASE_BLOCKING = "release_blocking"
    WARNING = "warning"
    ADVISORY = "advisory"


class ThresholdCheck(BaseModel):
    """Result of a threshold check.

    Attributes:
        metric_name: Name of the metric being checked
        current_value: Current value of the metric
        threshold_value: Threshold value to compare against
        passed: Whether the check passed
        gate_level: Level of the gate (release_blocking, warning, advisory)
    """

    metric_name: str
    current_value: float
    threshold_value: float
    passed: bool
    gate_level: GateLevel


class BenchmarkResult(BaseModel):
    """Result from running a single benchmark.

    Attributes:
        benchmark_id: Unique identifier for the benchmark
        success: Whether the benchmark passed
        tasks_completed: Number of tasks successfully completed
        total_tasks: Total number of tasks in the benchmark
        cost_usd: Total cost in USD for running the benchmark
        duration_ms: Duration in milliseconds
        retries: Number of retries needed
        test_coverage: Test coverage percentage (optional)
        lint_passed: Whether linting passed (optional)
        type_check_passed: Whether type checking passed (optional)
        error_message: Error message if failed (optional)
    """

    benchmark_id: str
    success: bool
    tasks_completed: int
    total_tasks: int
    cost_usd: float
    duration_ms: int
    retries: int
    test_coverage: float | None = None
    lint_passed: bool | None = None
    type_check_passed: bool | None = None
    error_message: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def task_completion_rate(self) -> float:
        """Calculate task completion rate.

        Returns:
            Task completion rate as a float between 0 and 1.
        """
        if self.total_tasks == 0:
            return 0.0
        return self.tasks_completed / self.total_tasks

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cost_per_task(self) -> float:
        """Calculate cost per task.

        Returns:
            Cost per task in USD.
        """
        if self.tasks_completed == 0:
            return 0.0
        return self.cost_usd / self.tasks_completed


class EvalMetrics(BaseModel):
    """Aggregate metrics from evaluation runs.

    Attributes:
        pass_at_1: First attempt success rate (0-1)
        task_completion_rate: Overall task completion rate (0-1)
        pass_8: Pass rate over 8 trials (0-1)
        cost_per_task: Average cost per task in USD
        avg_duration_ms: Average duration in milliseconds
        total_benchmarks: Total number of benchmarks run
        passed_benchmarks: Number of benchmarks that passed
        failed_benchmarks: Number of benchmarks that failed
    """

    pass_at_1: float
    task_completion_rate: float
    pass_8: float = 0.0
    cost_per_task: float
    avg_duration_ms: float
    total_benchmarks: int
    passed_benchmarks: int
    failed_benchmarks: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate.

        Returns:
            Success rate as a float between 0 and 1.
        """
        if self.total_benchmarks == 0:
            return 0.0
        return self.passed_benchmarks / self.total_benchmarks

    def passes_release_blocking(
        self,
        pass_at_1_threshold: float = 0.85,
        task_completion_threshold: float = 0.90,
    ) -> bool:
        """Check if metrics pass release blocking thresholds.

        Args:
            pass_at_1_threshold: Minimum pass@1 rate (default 0.85)
            task_completion_threshold: Minimum task completion rate (default 0.90)

        Returns:
            True if all release blocking thresholds are met.
        """
        return (
            self.pass_at_1 >= pass_at_1_threshold
            and self.task_completion_rate >= task_completion_threshold
        )

    def check_thresholds(
        self,
        pass_at_1_threshold: float = 0.85,
        task_completion_threshold: float = 0.90,
        pass_8_threshold: float = 0.60,
        cost_per_task_threshold: float = 0.50,
    ) -> list[ThresholdCheck]:
        """Check all thresholds and return results.

        Args:
            pass_at_1_threshold: Minimum pass@1 rate
            task_completion_threshold: Minimum task completion rate
            pass_8_threshold: Minimum pass^8 rate
            cost_per_task_threshold: Maximum cost per task

        Returns:
            List of ThresholdCheck results.
        """
        checks = []

        # Release blocking checks
        checks.append(
            ThresholdCheck(
                metric_name="pass_at_1",
                current_value=self.pass_at_1,
                threshold_value=pass_at_1_threshold,
                passed=self.pass_at_1 >= pass_at_1_threshold,
                gate_level=GateLevel.RELEASE_BLOCKING,
            )
        )

        checks.append(
            ThresholdCheck(
                metric_name="task_completion_rate",
                current_value=self.task_completion_rate,
                threshold_value=task_completion_threshold,
                passed=self.task_completion_rate >= task_completion_threshold,
                gate_level=GateLevel.RELEASE_BLOCKING,
            )
        )

        # Warning level checks
        checks.append(
            ThresholdCheck(
                metric_name="pass_8",
                current_value=self.pass_8,
                threshold_value=pass_8_threshold,
                passed=self.pass_8 >= pass_8_threshold,
                gate_level=GateLevel.WARNING,
            )
        )

        # Advisory checks (lower is better for cost)
        checks.append(
            ThresholdCheck(
                metric_name="cost_per_task",
                current_value=self.cost_per_task,
                threshold_value=cost_per_task_threshold,
                passed=self.cost_per_task <= cost_per_task_threshold,
                gate_level=GateLevel.ADVISORY,
            )
        )

        return checks


class ComparisonResult(BaseModel):
    """Result from comparing current metrics to baseline.

    Attributes:
        baseline_exists: Whether a baseline file was found
        has_regression: Whether any metric regressed beyond threshold
        requires_approval: Whether the regression requires human approval
        regressions: List of metrics that regressed
        improvements: List of metrics that improved
    """

    baseline_exists: bool = True
    has_regression: bool = False
    requires_approval: bool = False
    regressions: list[dict[str, Any]] = Field(default_factory=list)
    improvements: list[dict[str, Any]] = Field(default_factory=list)
