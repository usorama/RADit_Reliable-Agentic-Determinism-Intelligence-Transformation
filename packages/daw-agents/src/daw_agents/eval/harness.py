"""Evaluation harness for running benchmarks and calculating metrics.

This module provides the EvalHarness class for:
- Loading benchmarks from the benchmark index
- Running individual and batch benchmarks
- Calculating aggregate metrics
- Comparing results to baseline
- Generating reports
- Saving timestamped results
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from daw_agents.eval.metrics import (
    BenchmarkResult,
    ComparisonResult,
    EvalMetrics,
)

logger = logging.getLogger(__name__)


class EvalConfig(BaseModel):
    """Configuration for the evaluation harness.

    Attributes:
        benchmarks_path: Path to the benchmarks directory
        results_path: Path to store evaluation results
        default_trials: Default number of trials for pass^8 calculation
        regression_threshold: Threshold for detecting regression (5% = 0.05)
        pass_at_1_threshold: Release blocking threshold for pass@1
        task_completion_threshold: Release blocking threshold for task completion
        pass_8_threshold: Warning threshold for pass^8
        cost_per_task_threshold: Advisory threshold for cost per task
    """

    benchmarks_path: Path = Field(default=Path("eval/benchmarks"))
    results_path: Path = Field(default=Path("eval/results"))
    default_trials: int = Field(default=8, ge=1)
    regression_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    pass_at_1_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    task_completion_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    pass_8_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    cost_per_task_threshold: float = Field(default=0.50, ge=0.0)

    @classmethod
    def from_file(cls, config_path: Path) -> EvalConfig:
        """Load configuration from a JSON file.

        Args:
            config_path: Path to the configuration file.

        Returns:
            EvalConfig instance with loaded values.
        """
        with open(config_path) as f:
            data = json.load(f)

        # Convert path strings to Path objects
        if "benchmarks_path" in data:
            data["benchmarks_path"] = Path(data["benchmarks_path"])
        if "results_path" in data:
            data["results_path"] = Path(data["results_path"])

        return cls(**data)


class EvalHarness:
    """Evaluation harness for running agent benchmarks.

    This class manages the complete evaluation workflow:
    1. Load benchmarks from the index
    2. Execute benchmarks against agents
    3. Calculate aggregate metrics
    4. Compare to baseline for regression detection
    5. Generate reports
    6. Save timestamped results
    """

    def __init__(self, config: EvalConfig | None = None) -> None:
        """Initialize the evaluation harness.

        Args:
            config: Configuration for the harness. Uses defaults if not provided.
        """
        self.config = config or EvalConfig()
        self.results: list[BenchmarkResult] = []

    def load_benchmarks(
        self, benchmark_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Load benchmarks from the index file.

        Only returns enabled benchmarks by default.

        Args:
            benchmark_ids: Optional list of specific benchmark IDs to load.
                          If None, loads all enabled benchmarks.

        Returns:
            List of benchmark definitions.
        """
        index_path = self.config.benchmarks_path / "index.json"

        if not index_path.exists():
            logger.warning(f"Benchmark index not found at {index_path}")
            return []

        with open(index_path) as f:
            index = json.load(f)

        benchmarks = index.get("benchmarks", [])

        # Filter to enabled benchmarks
        benchmarks = [b for b in benchmarks if b.get("enabled", True)]

        # Filter by IDs if specified
        if benchmark_ids:
            benchmarks = [b for b in benchmarks if b.get("id") in benchmark_ids]

        return benchmarks

    async def run_benchmark(
        self, benchmark: dict[str, Any]
    ) -> BenchmarkResult:
        """Run a single benchmark.

        Args:
            benchmark: Benchmark definition from the index.

        Returns:
            BenchmarkResult with execution results.
        """
        benchmark_id = benchmark.get("id", "unknown")
        logger.info(f"Running benchmark: {benchmark_id}")

        try:
            result = await self._execute_agent_pipeline(benchmark)
            return result
        except Exception as e:
            logger.error(f"Benchmark {benchmark_id} failed: {e}")
            return BenchmarkResult(
                benchmark_id=benchmark_id,
                success=False,
                tasks_completed=0,
                total_tasks=0,
                cost_usd=0.0,
                duration_ms=0,
                retries=0,
                error_message=str(e),
            )

    async def run_all_benchmarks(
        self, benchmark_ids: list[str] | None = None
    ) -> list[BenchmarkResult]:
        """Run all enabled benchmarks.

        Args:
            benchmark_ids: Optional list of specific benchmark IDs to run.

        Returns:
            List of BenchmarkResult for each benchmark.
        """
        benchmarks = self.load_benchmarks(benchmark_ids)
        results = []

        for benchmark in benchmarks:
            result = await self.run_benchmark(benchmark)
            results.append(result)
            self.results.append(result)

        return results

    async def run_benchmark_with_trials(
        self, benchmark: dict[str, Any], trials: int | None = None
    ) -> list[BenchmarkResult]:
        """Run a benchmark multiple times for pass^8 calculation.

        Args:
            benchmark: Benchmark definition from the index.
            trials: Number of trials to run. Defaults to config.default_trials.

        Returns:
            List of BenchmarkResult for each trial.
        """
        num_trials = trials or self.config.default_trials
        results = []

        for trial in range(num_trials):
            logger.info(
                f"Running trial {trial + 1}/{num_trials} "
                f"for benchmark {benchmark.get('id')}"
            )
            result = await self._execute_agent_pipeline(benchmark)
            results.append(result)

        return results

    async def _execute_agent_pipeline(
        self, benchmark: dict[str, Any]
    ) -> BenchmarkResult:
        """Execute the agent pipeline for a benchmark.

        This method should be overridden or mocked in tests.
        In production, this would invoke the Planner -> Executor -> Validator
        pipeline.

        Args:
            benchmark: Benchmark definition.

        Returns:
            BenchmarkResult from the pipeline execution.
        """
        # Default implementation - should be overridden
        raise NotImplementedError(
            "_execute_agent_pipeline must be implemented or mocked"
        )

    def calculate_metrics(
        self, results: list[BenchmarkResult]
    ) -> EvalMetrics:
        """Calculate aggregate metrics from benchmark results.

        Args:
            results: List of benchmark results.

        Returns:
            EvalMetrics with aggregate statistics.
        """
        if not results:
            return EvalMetrics(
                pass_at_1=0.0,
                task_completion_rate=0.0,
                pass_8=0.0,
                cost_per_task=0.0,
                avg_duration_ms=0.0,
                total_benchmarks=0,
                passed_benchmarks=0,
                failed_benchmarks=0,
            )

        # Calculate pass@1 (first attempt success rate)
        passed = sum(1 for r in results if r.success)
        pass_at_1 = passed / len(results)

        # Calculate task completion rate
        total_tasks = sum(r.total_tasks for r in results)
        completed_tasks = sum(r.tasks_completed for r in results)
        task_completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0

        # Calculate cost per task
        total_cost = sum(r.cost_usd for r in results)
        cost_per_task = total_cost / completed_tasks if completed_tasks > 0 else 0.0

        # Calculate average duration
        avg_duration = sum(r.duration_ms for r in results) / len(results)

        return EvalMetrics(
            pass_at_1=pass_at_1,
            task_completion_rate=task_completion_rate,
            pass_8=0.0,  # Will be calculated separately from trial data
            cost_per_task=cost_per_task,
            avg_duration_ms=avg_duration,
            total_benchmarks=len(results),
            passed_benchmarks=passed,
            failed_benchmarks=len(results) - passed,
        )

    def calculate_pass_8(
        self, trial_results: dict[str, list[BenchmarkResult]]
    ) -> float:
        """Calculate pass^8 metric from trial results.

        Pass^8 is the average success rate across all benchmarks over
        multiple trials. It measures consistency.

        Args:
            trial_results: Dictionary mapping benchmark_id to list of trial results.

        Returns:
            Average pass rate across all benchmarks and trials.
        """
        if not trial_results:
            return 0.0

        pass_rates = []
        for _benchmark_id, trials in trial_results.items():
            if not trials:
                continue
            success_count = sum(1 for t in trials if t.success)
            pass_rates.append(success_count / len(trials))

        if not pass_rates:
            return 0.0

        return sum(pass_rates) / len(pass_rates)

    def compare_to_baseline(
        self, current_metrics: EvalMetrics
    ) -> ComparisonResult:
        """Compare current metrics to baseline for regression detection.

        Args:
            current_metrics: Current evaluation metrics.

        Returns:
            ComparisonResult with regression analysis.
        """
        baseline_path = self.config.results_path / "baseline.json"

        if not baseline_path.exists():
            logger.info("No baseline found, skipping comparison")
            return ComparisonResult(
                baseline_exists=False,
                has_regression=False,
                requires_approval=False,
            )

        with open(baseline_path) as f:
            baseline_data = json.load(f)

        baseline_metrics = baseline_data.get("metrics", {})
        regressions = []
        improvements = []

        # Check each metric
        metrics_to_check = [
            ("pass_at_1", current_metrics.pass_at_1, True),  # higher is better
            ("task_completion_rate", current_metrics.task_completion_rate, True),
            ("pass_8", current_metrics.pass_8, True),
            ("cost_per_task", current_metrics.cost_per_task, False),  # lower is better
        ]

        for metric_name, current_value, higher_is_better in metrics_to_check:
            baseline_value = baseline_metrics.get(metric_name)
            if baseline_value is None:
                continue

            if higher_is_better:
                change = current_value - baseline_value
                change_pct = (
                    (current_value - baseline_value) / baseline_value
                    if baseline_value > 0
                    else 0
                )
            else:
                change = baseline_value - current_value
                change_pct = (
                    (baseline_value - current_value) / baseline_value
                    if baseline_value > 0
                    else 0
                )

            if change_pct < -self.config.regression_threshold:
                regressions.append({
                    "metric": metric_name,
                    "baseline": baseline_value,
                    "current": current_value,
                    "change": change,
                    "change_pct": change_pct,
                    "threshold": self.config.regression_threshold,
                })
            elif change_pct > 0:
                improvements.append({
                    "metric": metric_name,
                    "baseline": baseline_value,
                    "current": current_value,
                    "change": change,
                })

        has_regression = len(regressions) > 0

        # Require approval if any regression exceeds 10%
        requires_approval = any(
            abs(r.get("change_pct", 0)) > 0.10 for r in regressions
        )

        return ComparisonResult(
            baseline_exists=True,
            has_regression=has_regression,
            requires_approval=requires_approval,
            regressions=regressions,
            improvements=improvements,
        )

    def save_results(
        self,
        results: list[BenchmarkResult],
        metrics: EvalMetrics,
        run_id: str | None = None,
    ) -> Path:
        """Save evaluation results to a timestamped file.

        Args:
            results: List of benchmark results.
            metrics: Aggregate metrics.
            run_id: Optional custom run ID. Auto-generated if not provided.

        Returns:
            Path to the saved results file.
        """
        # Ensure results directory exists
        self.config.results_path.mkdir(parents=True, exist_ok=True)

        # Generate run ID if not provided
        if run_id is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            run_id = f"eval_{timestamp}_{uuid4().hex[:8]}"

        # Build results data
        results_data = {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": metrics.model_dump(),
            "benchmark_results": [r.model_dump() for r in results],
        }

        # Save to file
        filename = f"eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        result_path = self.config.results_path / filename

        with open(result_path, "w") as f:
            json.dump(results_data, f, indent=2, default=str)

        logger.info(f"Results saved to {result_path}")
        return result_path

    def generate_report(
        self,
        results: list[BenchmarkResult],
        metrics: EvalMetrics,
        comparison: ComparisonResult | None = None,
    ) -> str:
        """Generate a markdown evaluation report.

        Args:
            results: List of benchmark results.
            metrics: Aggregate metrics.
            comparison: Optional baseline comparison results.

        Returns:
            Markdown formatted report string.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

        report_lines = [
            "# Evaluation Report",
            "",
            f"**Generated**: {timestamp}",
            "",
            "## Summary",
            "",
            f"- **Total Benchmarks**: {metrics.total_benchmarks}",
            f"- **Passed**: {metrics.passed_benchmarks}",
            f"- **Failed**: {metrics.failed_benchmarks}",
            f"- **Success Rate**: {metrics.success_rate:.1%}",
            "",
            "## Metrics",
            "",
            "| Metric | Value | Threshold | Status |",
            "|--------|-------|-----------|--------|",
        ]

        # Add threshold checks
        checks = metrics.check_thresholds(
            pass_at_1_threshold=self.config.pass_at_1_threshold,
            task_completion_threshold=self.config.task_completion_threshold,
            pass_8_threshold=self.config.pass_8_threshold,
            cost_per_task_threshold=self.config.cost_per_task_threshold,
        )

        for check in checks:
            status = "PASS" if check.passed else "FAIL"
            status_emoji = "PASS" if check.passed else "FAIL"
            gate_suffix = f" ({check.gate_level.value})"

            # Format value appropriately
            if check.metric_name == "cost_per_task":
                value_str = f"${check.current_value:.3f}"
                threshold_str = f"<= ${check.threshold_value:.2f}"
            else:
                value_str = f"{check.current_value:.1%}"
                threshold_str = f">= {check.threshold_value:.0%}"

            report_lines.append(
                f"| {check.metric_name} | {value_str} | {threshold_str} | "
                f"{status_emoji}{gate_suffix} |"
            )

        report_lines.extend([
            "",
            f"**Average Duration**: {metrics.avg_duration_ms / 1000:.1f}s",
            "",
        ])

        # Add comparison section if available
        if comparison and comparison.baseline_exists:
            report_lines.extend([
                "## Baseline Comparison",
                "",
            ])

            if comparison.has_regression:
                report_lines.append("**WARNING: Regressions detected!**")
                report_lines.append("")
                report_lines.append("| Metric | Baseline | Current | Change |")
                report_lines.append("|--------|----------|---------|--------|")

                for reg in comparison.regressions:
                    change_pct = reg.get("change_pct", 0) * 100
                    report_lines.append(
                        f"| {reg['metric']} | {reg['baseline']:.2f} | "
                        f"{reg['current']:.2f} | {change_pct:+.1f}% |"
                    )

                if comparison.requires_approval:
                    report_lines.extend([
                        "",
                        "**ACTION REQUIRED: Regression exceeds 10%, "
                        "approval needed for release.**",
                    ])
            else:
                report_lines.append("No regressions detected.")

            if comparison.improvements:
                report_lines.extend([
                    "",
                    "### Improvements",
                    "",
                ])
                for imp in comparison.improvements:
                    report_lines.append(
                        f"- **{imp['metric']}**: {imp['baseline']:.2f} -> "
                        f"{imp['current']:.2f} ({imp['change']:+.3f})"
                    )

            report_lines.append("")

        # Add benchmark results section
        report_lines.extend([
            "## Benchmark Results",
            "",
            "| Benchmark | Status | Tasks | Cost | Duration |",
            "|-----------|--------|-------|------|----------|",
        ])

        for result in results:
            status = "PASS" if result.success else "FAIL"
            tasks = f"{result.tasks_completed}/{result.total_tasks}"
            cost = f"${result.cost_usd:.2f}"
            duration = f"{result.duration_ms / 1000:.1f}s"

            report_lines.append(
                f"| {result.benchmark_id} | {status} | {tasks} | {cost} | {duration} |"
            )

        # Add failed benchmark details
        failed_results = [r for r in results if not r.success]
        if failed_results:
            report_lines.extend([
                "",
                "### Failed Benchmarks",
                "",
            ])
            for result in failed_results:
                report_lines.append(f"**{result.benchmark_id}**:")
                if result.error_message:
                    report_lines.append(f"- Error: {result.error_message}")
                report_lines.append(
                    f"- Tasks Completed: {result.tasks_completed}/{result.total_tasks}"
                )
                report_lines.append(f"- Retries: {result.retries}")
                report_lines.append("")

        report_lines.extend([
            "",
            "---",
            "",
            "*Generated by DAW Eval Harness*",
        ])

        return "\n".join(report_lines)
