"""Test suite for the Eval Harness with Performance Metrics (EVAL-002).

This test module validates the evaluation harness implementation that measures
agent performance against golden benchmarks. The harness tracks metrics like
pass@1, task completion rate, pass^8, and cost per task.

Tests cover:
- BenchmarkResult Pydantic model for individual benchmark results
- EvalMetrics Pydantic model for aggregate metrics
- EvalConfig for harness configuration
- EvalHarness class for running benchmarks
- run_benchmark() for single benchmark execution
- run_all_benchmarks() for suite execution
- calculate_metrics() for computing aggregate metrics
- compare_to_baseline() for regression detection
- generate_report() for creating evaluation reports
- save_results() for persisting timestamped results

TDD Phase: RED - These tests define expected behavior before implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from daw_agents.eval.harness import (
    EvalConfig,
    EvalHarness,
)
from daw_agents.eval.metrics import (
    BenchmarkResult,
    ComparisonResult,
    EvalMetrics,
    GateLevel,
    ThresholdCheck,
)

if TYPE_CHECKING:
    pass


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def eval_config() -> EvalConfig:
    """Create a test EvalConfig with default values."""
    return EvalConfig(
        benchmarks_path=Path("eval/benchmarks"),
        results_path=Path("eval/results"),
        default_trials=8,
        regression_threshold=0.05,
        pass_at_1_threshold=0.85,
        task_completion_threshold=0.90,
        pass_8_threshold=0.60,
        cost_per_task_threshold=0.50,
    )


@pytest.fixture
def sample_benchmark_result() -> BenchmarkResult:
    """Create a sample successful benchmark result."""
    return BenchmarkResult(
        benchmark_id="calculator",
        success=True,
        tasks_completed=7,
        total_tasks=7,
        cost_usd=0.23,
        duration_ms=180000,
        retries=1,
        test_coverage=0.92,
        lint_passed=True,
        type_check_passed=True,
    )


@pytest.fixture
def sample_failed_benchmark_result() -> BenchmarkResult:
    """Create a sample failed benchmark result."""
    return BenchmarkResult(
        benchmark_id="todo_app",
        success=False,
        tasks_completed=10,
        total_tasks=12,
        cost_usd=0.85,
        duration_ms=420000,
        retries=3,
        test_coverage=0.65,
        lint_passed=False,
        type_check_passed=True,
        error_message="Test coverage below threshold",
    )


@pytest.fixture
def sample_eval_metrics() -> EvalMetrics:
    """Create sample evaluation metrics."""
    return EvalMetrics(
        pass_at_1=0.87,
        task_completion_rate=0.92,
        pass_8=0.65,
        cost_per_task=0.35,
        avg_duration_ms=250000,
        total_benchmarks=3,
        passed_benchmarks=2,
        failed_benchmarks=1,
    )


@pytest.fixture
def mock_benchmark_index() -> dict:
    """Create a mock benchmark index."""
    return {
        "version": "1.0.0",
        "benchmarks": [
            {
                "id": "calculator",
                "name": "Calculator",
                "complexity": "low",
                "enabled": True,
                "expected_metrics": {
                    "task_count_min": 6,
                    "task_count_max": 8,
                },
            },
            {
                "id": "todo_app",
                "name": "ToDo App",
                "complexity": "low-medium",
                "enabled": True,
                "expected_metrics": {
                    "task_count_min": 12,
                    "task_count_max": 15,
                },
            },
            {
                "id": "rest_api",
                "name": "REST API",
                "complexity": "medium",
                "enabled": False,  # Disabled benchmark
                "expected_metrics": {
                    "task_count_min": 15,
                    "task_count_max": 20,
                },
            },
        ],
        "thresholds": {
            "release_blocking": {
                "pass_at_1": 0.85,
                "task_completion_rate": 0.90,
            },
            "warning": {
                "pass_at_8": 0.60,
            },
            "advisory": {
                "cost_per_task_max_usd": 0.50,
            },
            "regression": {
                "threshold": 0.05,
            },
        },
    }


# ============================================================================
# BenchmarkResult Model Tests
# ============================================================================


class TestBenchmarkResult:
    """Tests for BenchmarkResult Pydantic model."""

    def test_create_benchmark_result_success(self) -> None:
        """Test creating a successful benchmark result."""
        result = BenchmarkResult(
            benchmark_id="calculator",
            success=True,
            tasks_completed=7,
            total_tasks=7,
            cost_usd=0.23,
            duration_ms=180000,
            retries=1,
        )

        assert result.benchmark_id == "calculator"
        assert result.success is True
        assert result.tasks_completed == 7
        assert result.total_tasks == 7
        assert result.cost_usd == 0.23
        assert result.duration_ms == 180000
        assert result.retries == 1

    def test_create_benchmark_result_failure(self) -> None:
        """Test creating a failed benchmark result with error message."""
        result = BenchmarkResult(
            benchmark_id="todo_app",
            success=False,
            tasks_completed=10,
            total_tasks=12,
            cost_usd=0.85,
            duration_ms=420000,
            retries=3,
            error_message="Test coverage below threshold",
        )

        assert result.success is False
        assert result.error_message == "Test coverage below threshold"
        assert result.tasks_completed < result.total_tasks

    def test_benchmark_result_task_completion_rate(
        self, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test calculating task completion rate from result."""
        rate = sample_benchmark_result.task_completion_rate
        assert rate == 1.0  # 7/7 = 100%

    def test_benchmark_result_task_completion_rate_partial(
        self, sample_failed_benchmark_result: BenchmarkResult
    ) -> None:
        """Test task completion rate with partial completion."""
        rate = sample_failed_benchmark_result.task_completion_rate
        assert rate == pytest.approx(0.833, rel=0.01)  # 10/12

    def test_benchmark_result_cost_per_task(
        self, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test calculating cost per task."""
        cpt = sample_benchmark_result.cost_per_task
        assert cpt == pytest.approx(0.0329, rel=0.01)  # 0.23/7

    def test_benchmark_result_default_values(self) -> None:
        """Test default values for optional fields."""
        result = BenchmarkResult(
            benchmark_id="test",
            success=True,
            tasks_completed=5,
            total_tasks=5,
            cost_usd=0.10,
            duration_ms=60000,
            retries=0,
        )

        assert result.test_coverage is None
        assert result.lint_passed is None
        assert result.type_check_passed is None
        assert result.error_message is None

    def test_benchmark_result_serialization(
        self, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test serialization to dict/JSON."""
        data = sample_benchmark_result.model_dump()
        assert "benchmark_id" in data
        assert "success" in data
        assert data["benchmark_id"] == "calculator"

        # Test JSON serialization
        json_str = sample_benchmark_result.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["benchmark_id"] == "calculator"


# ============================================================================
# EvalMetrics Model Tests
# ============================================================================


class TestEvalMetrics:
    """Tests for EvalMetrics Pydantic model."""

    def test_create_eval_metrics(self) -> None:
        """Test creating EvalMetrics with all fields."""
        metrics = EvalMetrics(
            pass_at_1=0.87,
            task_completion_rate=0.92,
            pass_8=0.65,
            cost_per_task=0.35,
            avg_duration_ms=250000,
            total_benchmarks=3,
            passed_benchmarks=2,
            failed_benchmarks=1,
        )

        assert metrics.pass_at_1 == 0.87
        assert metrics.task_completion_rate == 0.92
        assert metrics.pass_8 == 0.65
        assert metrics.cost_per_task == 0.35
        assert metrics.avg_duration_ms == 250000
        assert metrics.total_benchmarks == 3
        assert metrics.passed_benchmarks == 2
        assert metrics.failed_benchmarks == 1

    def test_eval_metrics_success_rate(self, sample_eval_metrics: EvalMetrics) -> None:
        """Test calculating overall success rate."""
        success_rate = sample_eval_metrics.success_rate
        assert success_rate == pytest.approx(0.667, rel=0.01)  # 2/3

    def test_eval_metrics_is_release_blocking_pass(self) -> None:
        """Test checking if metrics pass release blocking thresholds."""
        metrics = EvalMetrics(
            pass_at_1=0.90,  # >= 0.85
            task_completion_rate=0.95,  # >= 0.90
            pass_8=0.70,
            cost_per_task=0.30,
            avg_duration_ms=200000,
            total_benchmarks=3,
            passed_benchmarks=3,
            failed_benchmarks=0,
        )

        assert metrics.passes_release_blocking(
            pass_at_1_threshold=0.85, task_completion_threshold=0.90
        )

    def test_eval_metrics_is_release_blocking_fail(self) -> None:
        """Test metrics that fail release blocking thresholds."""
        metrics = EvalMetrics(
            pass_at_1=0.80,  # < 0.85 - FAIL
            task_completion_rate=0.85,  # < 0.90 - FAIL
            pass_8=0.50,
            cost_per_task=0.60,
            avg_duration_ms=300000,
            total_benchmarks=3,
            passed_benchmarks=1,
            failed_benchmarks=2,
        )

        assert not metrics.passes_release_blocking(
            pass_at_1_threshold=0.85, task_completion_threshold=0.90
        )

    def test_eval_metrics_check_thresholds(
        self, sample_eval_metrics: EvalMetrics
    ) -> None:
        """Test checking all threshold levels."""
        checks = sample_eval_metrics.check_thresholds(
            pass_at_1_threshold=0.85,
            task_completion_threshold=0.90,
            pass_8_threshold=0.60,
            cost_per_task_threshold=0.50,
        )

        assert isinstance(checks, list)
        assert len(checks) >= 4
        assert all(isinstance(c, ThresholdCheck) for c in checks)

    def test_eval_metrics_serialization(
        self, sample_eval_metrics: EvalMetrics
    ) -> None:
        """Test serialization to dict/JSON."""
        data = sample_eval_metrics.model_dump()
        assert "pass_at_1" in data
        assert "task_completion_rate" in data

        json_str = sample_eval_metrics.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["pass_at_1"] == 0.87


class TestThresholdCheck:
    """Tests for ThresholdCheck model."""

    def test_create_threshold_check_pass(self) -> None:
        """Test creating a passing threshold check."""
        check = ThresholdCheck(
            metric_name="pass_at_1",
            current_value=0.90,
            threshold_value=0.85,
            passed=True,
            gate_level=GateLevel.RELEASE_BLOCKING,
        )

        assert check.metric_name == "pass_at_1"
        assert check.passed is True
        assert check.gate_level == GateLevel.RELEASE_BLOCKING

    def test_create_threshold_check_fail(self) -> None:
        """Test creating a failing threshold check."""
        check = ThresholdCheck(
            metric_name="task_completion_rate",
            current_value=0.85,
            threshold_value=0.90,
            passed=False,
            gate_level=GateLevel.RELEASE_BLOCKING,
        )

        assert check.passed is False
        assert check.current_value < check.threshold_value


class TestGateLevel:
    """Tests for GateLevel enum."""

    def test_gate_level_values(self) -> None:
        """Test all gate level values exist."""
        assert GateLevel.RELEASE_BLOCKING.value == "release_blocking"
        assert GateLevel.WARNING.value == "warning"
        assert GateLevel.ADVISORY.value == "advisory"


# ============================================================================
# EvalConfig Tests
# ============================================================================


class TestEvalConfig:
    """Tests for EvalConfig configuration model."""

    def test_create_eval_config_defaults(self) -> None:
        """Test creating EvalConfig with default values."""
        config = EvalConfig()

        assert config.benchmarks_path == Path("eval/benchmarks")
        assert config.results_path == Path("eval/results")
        assert config.default_trials == 8
        assert config.regression_threshold == 0.05
        assert config.pass_at_1_threshold == 0.85
        assert config.task_completion_threshold == 0.90
        assert config.pass_8_threshold == 0.60
        assert config.cost_per_task_threshold == 0.50

    def test_create_eval_config_custom(self) -> None:
        """Test creating EvalConfig with custom values."""
        config = EvalConfig(
            benchmarks_path=Path("/custom/benchmarks"),
            results_path=Path("/custom/results"),
            default_trials=16,
            regression_threshold=0.10,
            pass_at_1_threshold=0.90,
        )

        assert config.benchmarks_path == Path("/custom/benchmarks")
        assert config.results_path == Path("/custom/results")
        assert config.default_trials == 16
        assert config.regression_threshold == 0.10
        assert config.pass_at_1_threshold == 0.90

    def test_eval_config_from_file(self, tmp_path: Path) -> None:
        """Test loading EvalConfig from JSON file."""
        config_file = tmp_path / "eval_config.json"
        config_data = {
            "benchmarks_path": "eval/benchmarks",
            "results_path": "eval/results",
            "default_trials": 4,
            "regression_threshold": 0.03,
        }
        config_file.write_text(json.dumps(config_data))

        config = EvalConfig.from_file(config_file)

        assert config.default_trials == 4
        assert config.regression_threshold == 0.03


# ============================================================================
# EvalHarness Tests
# ============================================================================


class TestEvalHarness:
    """Tests for EvalHarness class."""

    def test_create_eval_harness(self, eval_config: EvalConfig) -> None:
        """Test creating an EvalHarness instance."""
        harness = EvalHarness(config=eval_config)

        assert harness.config == eval_config
        assert harness.results == []

    def test_eval_harness_default_config(self) -> None:
        """Test creating EvalHarness with default config."""
        harness = EvalHarness()

        assert harness.config is not None
        assert isinstance(harness.config, EvalConfig)

    def test_load_benchmarks(
        self, eval_config: EvalConfig, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test loading benchmarks from index file."""
        # Setup mock benchmark index
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        config = EvalConfig(benchmarks_path=benchmarks_path)
        harness = EvalHarness(config=config)

        benchmarks = harness.load_benchmarks()

        # Should only load enabled benchmarks
        assert len(benchmarks) == 2
        assert benchmarks[0]["id"] == "calculator"
        assert benchmarks[1]["id"] == "todo_app"

    def test_load_benchmarks_filter_by_id(
        self, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test loading specific benchmarks by ID."""
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        config = EvalConfig(benchmarks_path=benchmarks_path)
        harness = EvalHarness(config=config)

        benchmarks = harness.load_benchmarks(benchmark_ids=["calculator"])

        assert len(benchmarks) == 1
        assert benchmarks[0]["id"] == "calculator"


class TestEvalHarnessRunBenchmark:
    """Tests for EvalHarness.run_benchmark() method."""

    @pytest.mark.asyncio
    async def test_run_benchmark_success(
        self, eval_config: EvalConfig, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test running a single benchmark successfully."""
        # Setup
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        config = EvalConfig(benchmarks_path=benchmarks_path)
        harness = EvalHarness(config=config)

        benchmark = {"id": "calculator", "name": "Calculator", "complexity": "low"}

        # Mock the agent execution
        with patch.object(
            harness, "_execute_agent_pipeline", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.23,
                duration_ms=180000,
                retries=1,
            )

            result = await harness.run_benchmark(benchmark)

        assert result.success is True
        assert result.benchmark_id == "calculator"
        mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_benchmark_failure(
        self, eval_config: EvalConfig, tmp_path: Path
    ) -> None:
        """Test running a benchmark that fails."""
        config = EvalConfig(benchmarks_path=tmp_path)
        harness = EvalHarness(config=config)

        benchmark = {"id": "todo_app", "name": "ToDo App", "complexity": "low-medium"}

        with patch.object(
            harness, "_execute_agent_pipeline", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = BenchmarkResult(
                benchmark_id="todo_app",
                success=False,
                tasks_completed=10,
                total_tasks=12,
                cost_usd=0.85,
                duration_ms=420000,
                retries=3,
                error_message="Test coverage below threshold",
            )

            result = await harness.run_benchmark(benchmark)

        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_run_benchmark_with_retries(
        self, eval_config: EvalConfig, tmp_path: Path
    ) -> None:
        """Test benchmark execution with retry tracking."""
        config = EvalConfig(benchmarks_path=tmp_path)
        harness = EvalHarness(config=config)

        benchmark = {"id": "calculator", "name": "Calculator"}

        with patch.object(
            harness, "_execute_agent_pipeline", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.35,
                duration_ms=200000,
                retries=2,  # Required 2 retries
            )

            result = await harness.run_benchmark(benchmark)

        assert result.retries == 2


class TestEvalHarnessRunAllBenchmarks:
    """Tests for EvalHarness.run_all_benchmarks() method."""

    @pytest.mark.asyncio
    async def test_run_all_benchmarks(
        self, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test running all enabled benchmarks."""
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        config = EvalConfig(benchmarks_path=benchmarks_path)
        harness = EvalHarness(config=config)

        with patch.object(
            harness, "run_benchmark", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                BenchmarkResult(
                    benchmark_id="calculator",
                    success=True,
                    tasks_completed=7,
                    total_tasks=7,
                    cost_usd=0.23,
                    duration_ms=180000,
                    retries=1,
                ),
                BenchmarkResult(
                    benchmark_id="todo_app",
                    success=True,
                    tasks_completed=12,
                    total_tasks=12,
                    cost_usd=0.65,
                    duration_ms=350000,
                    retries=0,
                ),
            ]

            results = await harness.run_all_benchmarks()

        assert len(results) == 2
        assert results[0].benchmark_id == "calculator"
        assert results[1].benchmark_id == "todo_app"
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_run_all_benchmarks_partial_failure(
        self, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test running benchmarks with some failures."""
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        config = EvalConfig(benchmarks_path=benchmarks_path)
        harness = EvalHarness(config=config)

        with patch.object(
            harness, "run_benchmark", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                BenchmarkResult(
                    benchmark_id="calculator",
                    success=True,
                    tasks_completed=7,
                    total_tasks=7,
                    cost_usd=0.23,
                    duration_ms=180000,
                    retries=1,
                ),
                BenchmarkResult(
                    benchmark_id="todo_app",
                    success=False,
                    tasks_completed=8,
                    total_tasks=12,
                    cost_usd=0.85,
                    duration_ms=420000,
                    retries=3,
                    error_message="Test failures",
                ),
            ]

            results = await harness.run_all_benchmarks()

        assert len(results) == 2
        passed = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(passed) == 1
        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_run_benchmarks_with_trials(
        self, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test running benchmarks with multiple trials for pass^8."""
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        config = EvalConfig(benchmarks_path=benchmarks_path, default_trials=8)
        harness = EvalHarness(config=config)

        # Mock 8 trial results (6 success, 2 failure = 75% pass^8)
        trial_results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=i < 6,  # First 6 succeed, last 2 fail
                tasks_completed=7 if i < 6 else 5,
                total_tasks=7,
                cost_usd=0.23,
                duration_ms=180000,
                retries=0 if i < 6 else 2,
            )
            for i in range(8)
        ]

        with patch.object(
            harness, "_execute_agent_pipeline", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = trial_results

            results = await harness.run_benchmark_with_trials(
                {"id": "calculator", "name": "Calculator"}, trials=8
            )

        assert len(results) == 8
        assert mock_exec.call_count == 8
        pass_rate = sum(1 for r in results if r.success) / len(results)
        assert pass_rate == 0.75


class TestEvalHarnessCalculateMetrics:
    """Tests for EvalHarness.calculate_metrics() method."""

    def test_calculate_metrics_all_success(self, eval_config: EvalConfig) -> None:
        """Test calculating metrics when all benchmarks pass."""
        harness = EvalHarness(config=eval_config)
        results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.23,
                duration_ms=180000,
                retries=1,
            ),
            BenchmarkResult(
                benchmark_id="todo_app",
                success=True,
                tasks_completed=12,
                total_tasks=12,
                cost_usd=0.65,
                duration_ms=350000,
                retries=0,
            ),
        ]

        metrics = harness.calculate_metrics(results)

        assert metrics.pass_at_1 == 1.0  # 2/2 passed
        assert metrics.task_completion_rate == 1.0
        assert metrics.total_benchmarks == 2
        assert metrics.passed_benchmarks == 2
        assert metrics.failed_benchmarks == 0

    def test_calculate_metrics_partial_success(self, eval_config: EvalConfig) -> None:
        """Test calculating metrics with partial success."""
        harness = EvalHarness(config=eval_config)
        results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.23,
                duration_ms=180000,
                retries=1,
            ),
            BenchmarkResult(
                benchmark_id="todo_app",
                success=False,
                tasks_completed=10,
                total_tasks=12,
                cost_usd=0.85,
                duration_ms=420000,
                retries=3,
            ),
        ]

        metrics = harness.calculate_metrics(results)

        assert metrics.pass_at_1 == 0.5  # 1/2 passed
        assert metrics.passed_benchmarks == 1
        assert metrics.failed_benchmarks == 1

    def test_calculate_metrics_avg_cost(self, eval_config: EvalConfig) -> None:
        """Test calculating average cost per task."""
        harness = EvalHarness(config=eval_config)
        results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.28,  # 0.04/task
                duration_ms=180000,
                retries=0,
            ),
            BenchmarkResult(
                benchmark_id="todo_app",
                success=True,
                tasks_completed=12,
                total_tasks=12,
                cost_usd=0.60,  # 0.05/task
                duration_ms=300000,
                retries=0,
            ),
        ]

        metrics = harness.calculate_metrics(results)

        # Total cost: 0.88, Total tasks: 19
        # Avg cost per task = 0.88 / 19 = 0.0463
        assert metrics.cost_per_task == pytest.approx(0.046, rel=0.1)

    def test_calculate_metrics_avg_duration(self, eval_config: EvalConfig) -> None:
        """Test calculating average duration."""
        harness = EvalHarness(config=eval_config)
        results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.20,
                duration_ms=180000,  # 3 min
                retries=0,
            ),
            BenchmarkResult(
                benchmark_id="todo_app",
                success=True,
                tasks_completed=12,
                total_tasks=12,
                cost_usd=0.50,
                duration_ms=300000,  # 5 min
                retries=0,
            ),
        ]

        metrics = harness.calculate_metrics(results)

        # Average duration = (180000 + 300000) / 2 = 240000
        assert metrics.avg_duration_ms == 240000

    def test_calculate_metrics_empty_results(self, eval_config: EvalConfig) -> None:
        """Test calculating metrics with no results."""
        harness = EvalHarness(config=eval_config)

        metrics = harness.calculate_metrics([])

        assert metrics.pass_at_1 == 0.0
        assert metrics.total_benchmarks == 0
        assert metrics.passed_benchmarks == 0

    def test_calculate_pass_8_metric(self, eval_config: EvalConfig) -> None:
        """Test calculating pass^8 from trial results."""
        harness = EvalHarness(config=eval_config)

        # Simulate 8 trials per benchmark, 2 benchmarks
        # Calculator: 7/8 success = 0.875
        # ToDo: 5/8 success = 0.625
        trial_results = {
            "calculator": [
                BenchmarkResult(
                    benchmark_id="calculator",
                    success=i < 7,
                    tasks_completed=7 if i < 7 else 5,
                    total_tasks=7,
                    cost_usd=0.20,
                    duration_ms=180000,
                    retries=0,
                )
                for i in range(8)
            ],
            "todo_app": [
                BenchmarkResult(
                    benchmark_id="todo_app",
                    success=i < 5,
                    tasks_completed=12 if i < 5 else 8,
                    total_tasks=12,
                    cost_usd=0.50,
                    duration_ms=350000,
                    retries=0,
                )
                for i in range(8)
            ],
        }

        pass_8 = harness.calculate_pass_8(trial_results)

        # Average of (0.875 + 0.625) / 2 = 0.75
        assert pass_8 == pytest.approx(0.75, rel=0.01)


class TestEvalHarnessCompareToBaseline:
    """Tests for EvalHarness.compare_to_baseline() method."""

    def test_compare_to_baseline_no_regression(
        self, eval_config: EvalConfig, tmp_path: Path
    ) -> None:
        """Test comparison with no regression."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        # Create baseline file
        baseline = {
            "metrics": {
                "pass_at_1": 0.85,
                "task_completion_rate": 0.90,
                "pass_8": 0.60,
                "cost_per_task": 0.40,
            }
        }
        baseline_file = results_path / "baseline.json"
        baseline_file.write_text(json.dumps(baseline))

        config = EvalConfig(results_path=results_path)
        harness = EvalHarness(config=config)

        current_metrics = EvalMetrics(
            pass_at_1=0.87,  # Improved
            task_completion_rate=0.92,  # Improved
            pass_8=0.65,  # Improved
            cost_per_task=0.35,  # Improved (lower is better)
            avg_duration_ms=200000,
            total_benchmarks=3,
            passed_benchmarks=3,
            failed_benchmarks=0,
        )

        comparison = harness.compare_to_baseline(current_metrics)

        assert comparison.has_regression is False
        assert comparison.requires_approval is False

    def test_compare_to_baseline_regression(
        self, eval_config: EvalConfig, tmp_path: Path
    ) -> None:
        """Test comparison with regression detected."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        baseline = {
            "metrics": {
                "pass_at_1": 0.90,
                "task_completion_rate": 0.95,
                "pass_8": 0.70,
                "cost_per_task": 0.30,
            }
        }
        baseline_file = results_path / "baseline.json"
        baseline_file.write_text(json.dumps(baseline))

        config = EvalConfig(results_path=results_path, regression_threshold=0.05)
        harness = EvalHarness(config=config)

        current_metrics = EvalMetrics(
            pass_at_1=0.82,  # 8.9% regression (> 5% threshold)
            task_completion_rate=0.88,  # 7.4% regression
            pass_8=0.55,  # 21.4% regression
            cost_per_task=0.50,  # 66.7% cost increase
            avg_duration_ms=300000,
            total_benchmarks=3,
            passed_benchmarks=2,
            failed_benchmarks=1,
        )

        comparison = harness.compare_to_baseline(current_metrics)

        assert comparison.has_regression is True
        assert len(comparison.regressions) > 0

    def test_compare_to_baseline_requires_approval(
        self, eval_config: EvalConfig, tmp_path: Path
    ) -> None:
        """Test comparison requiring approval for large regression."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        baseline = {
            "metrics": {
                "pass_at_1": 0.90,
                "task_completion_rate": 0.95,
            }
        }
        baseline_file = results_path / "baseline.json"
        baseline_file.write_text(json.dumps(baseline))

        config = EvalConfig(
            results_path=results_path,
            regression_threshold=0.05,
        )
        harness = EvalHarness(config=config)

        # Large regression > 10%
        current_metrics = EvalMetrics(
            pass_at_1=0.75,  # 16.7% regression
            task_completion_rate=0.80,  # 15.8% regression
            pass_8=0.50,
            cost_per_task=0.60,
            avg_duration_ms=400000,
            total_benchmarks=3,
            passed_benchmarks=1,
            failed_benchmarks=2,
        )

        comparison = harness.compare_to_baseline(current_metrics)

        assert comparison.has_regression is True
        assert comparison.requires_approval is True

    def test_compare_to_baseline_no_baseline_file(
        self, eval_config: EvalConfig, tmp_path: Path
    ) -> None:
        """Test comparison when no baseline file exists."""
        results_path = tmp_path / "results"
        results_path.mkdir()  # No baseline.json

        config = EvalConfig(results_path=results_path)
        harness = EvalHarness(config=config)

        current_metrics = EvalMetrics(
            pass_at_1=0.87,
            task_completion_rate=0.92,
            pass_8=0.65,
            cost_per_task=0.35,
            avg_duration_ms=200000,
            total_benchmarks=3,
            passed_benchmarks=3,
            failed_benchmarks=0,
        )

        comparison = harness.compare_to_baseline(current_metrics)

        # No baseline = no regression possible
        assert comparison.has_regression is False
        assert comparison.baseline_exists is False


class TestComparisonResult:
    """Tests for ComparisonResult model."""

    def test_comparison_result_no_regression(self) -> None:
        """Test creating comparison result with no regression."""
        result = ComparisonResult(
            baseline_exists=True,
            has_regression=False,
            requires_approval=False,
            regressions=[],
            improvements=[
                {"metric": "pass_at_1", "change": 0.02},
                {"metric": "cost_per_task", "change": -0.05},
            ],
        )

        assert result.has_regression is False
        assert len(result.improvements) == 2

    def test_comparison_result_with_regression(self) -> None:
        """Test creating comparison result with regression."""
        result = ComparisonResult(
            baseline_exists=True,
            has_regression=True,
            requires_approval=True,
            regressions=[
                {"metric": "pass_at_1", "change": -0.12, "threshold": 0.05},
            ],
            improvements=[],
        )

        assert result.has_regression is True
        assert result.requires_approval is True
        assert len(result.regressions) == 1


class TestEvalHarnessSaveResults:
    """Tests for EvalHarness.save_results() method."""

    def test_save_results(
        self, eval_config: EvalConfig, sample_eval_metrics: EvalMetrics, tmp_path: Path
    ) -> None:
        """Test saving evaluation results."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        config = EvalConfig(results_path=results_path)
        harness = EvalHarness(config=config)

        benchmark_results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.23,
                duration_ms=180000,
                retries=1,
            ),
        ]

        result_path = harness.save_results(
            results=benchmark_results,
            metrics=sample_eval_metrics,
        )

        assert result_path.exists()
        assert result_path.suffix == ".json"

        # Verify content
        saved_data = json.loads(result_path.read_text())
        assert "run_id" in saved_data
        assert "timestamp" in saved_data
        assert "metrics" in saved_data
        assert "benchmark_results" in saved_data

    def test_save_results_with_run_id(
        self, eval_config: EvalConfig, sample_eval_metrics: EvalMetrics, tmp_path: Path
    ) -> None:
        """Test saving results with custom run ID."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        config = EvalConfig(results_path=results_path)
        harness = EvalHarness(config=config)

        result_path = harness.save_results(
            results=[],
            metrics=sample_eval_metrics,
            run_id="custom-run-123",
        )

        saved_data = json.loads(result_path.read_text())
        assert saved_data["run_id"] == "custom-run-123"

    def test_save_results_timestamped_filename(
        self, eval_config: EvalConfig, sample_eval_metrics: EvalMetrics, tmp_path: Path
    ) -> None:
        """Test that results are saved with timestamped filename."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        config = EvalConfig(results_path=results_path)
        harness = EvalHarness(config=config)

        result_path = harness.save_results(
            results=[],
            metrics=sample_eval_metrics,
        )

        # Filename should contain date
        filename = result_path.name
        assert filename.startswith("eval_")
        assert filename.endswith(".json")


class TestEvalHarnessGenerateReport:
    """Tests for EvalHarness.generate_report() method."""

    def test_generate_report_markdown(
        self, eval_config: EvalConfig, sample_eval_metrics: EvalMetrics
    ) -> None:
        """Test generating markdown report."""
        harness = EvalHarness(config=eval_config)

        benchmark_results = [
            BenchmarkResult(
                benchmark_id="calculator",
                success=True,
                tasks_completed=7,
                total_tasks=7,
                cost_usd=0.23,
                duration_ms=180000,
                retries=1,
            ),
            BenchmarkResult(
                benchmark_id="todo_app",
                success=False,
                tasks_completed=10,
                total_tasks=12,
                cost_usd=0.85,
                duration_ms=420000,
                retries=3,
                error_message="Test failures",
            ),
        ]

        report = harness.generate_report(
            results=benchmark_results,
            metrics=sample_eval_metrics,
        )

        # Check report structure
        assert "# Evaluation Report" in report
        assert "## Summary" in report
        assert "## Metrics" in report
        assert "## Benchmark Results" in report
        assert "calculator" in report
        assert "todo_app" in report

    def test_generate_report_includes_thresholds(
        self, eval_config: EvalConfig, sample_eval_metrics: EvalMetrics
    ) -> None:
        """Test that report includes threshold checks."""
        harness = EvalHarness(config=eval_config)

        report = harness.generate_report(
            results=[],
            metrics=sample_eval_metrics,
        )

        assert "pass@1" in report.lower() or "pass_at_1" in report
        assert "task completion" in report.lower() or "task_completion" in report

    def test_generate_report_includes_comparison(
        self, eval_config: EvalConfig, sample_eval_metrics: EvalMetrics, tmp_path: Path
    ) -> None:
        """Test that report includes baseline comparison."""
        results_path = tmp_path / "results"
        results_path.mkdir()

        baseline = {
            "metrics": {
                "pass_at_1": 0.85,
                "task_completion_rate": 0.90,
            }
        }
        baseline_file = results_path / "baseline.json"
        baseline_file.write_text(json.dumps(baseline))

        config = EvalConfig(results_path=results_path)
        harness = EvalHarness(config=config)

        comparison = harness.compare_to_baseline(sample_eval_metrics)

        report = harness.generate_report(
            results=[],
            metrics=sample_eval_metrics,
            comparison=comparison,
        )

        assert "## Baseline Comparison" in report or "baseline" in report.lower()


# ============================================================================
# Integration Tests
# ============================================================================


class TestEvalHarnessIntegration:
    """Integration tests for the complete eval workflow."""

    @pytest.mark.asyncio
    async def test_full_eval_workflow(
        self, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test complete evaluation workflow from start to finish."""
        # Setup directories
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        results_path = tmp_path / "results"
        results_path.mkdir()

        # Write benchmark index
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        # Create harness
        config = EvalConfig(
            benchmarks_path=benchmarks_path,
            results_path=results_path,
            default_trials=1,  # Single trial for speed
        )
        harness = EvalHarness(config=config)

        # Mock agent execution
        with patch.object(
            harness, "_execute_agent_pipeline", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = [
                BenchmarkResult(
                    benchmark_id="calculator",
                    success=True,
                    tasks_completed=7,
                    total_tasks=7,
                    cost_usd=0.23,
                    duration_ms=180000,
                    retries=1,
                ),
                BenchmarkResult(
                    benchmark_id="todo_app",
                    success=True,
                    tasks_completed=12,
                    total_tasks=12,
                    cost_usd=0.65,
                    duration_ms=350000,
                    retries=0,
                ),
            ]

            # Run all benchmarks
            results = await harness.run_all_benchmarks()

        # Calculate metrics
        metrics = harness.calculate_metrics(results)

        # Generate report
        report = harness.generate_report(results=results, metrics=metrics)

        # Save results
        result_path = harness.save_results(results=results, metrics=metrics)

        # Assertions
        assert len(results) == 2
        assert metrics.pass_at_1 == 1.0
        assert metrics.task_completion_rate == 1.0
        assert "# Evaluation Report" in report
        assert result_path.exists()

    @pytest.mark.asyncio
    async def test_eval_with_regression_detection(
        self, mock_benchmark_index: dict, tmp_path: Path
    ) -> None:
        """Test evaluation with baseline comparison and regression detection."""
        benchmarks_path = tmp_path / "benchmarks"
        benchmarks_path.mkdir()
        results_path = tmp_path / "results"
        results_path.mkdir()

        # Write benchmark index
        index_file = benchmarks_path / "index.json"
        index_file.write_text(json.dumps(mock_benchmark_index))

        # Create baseline
        baseline = {
            "metrics": {
                "pass_at_1": 0.90,
                "task_completion_rate": 0.95,
                "pass_8": 0.70,
                "cost_per_task": 0.30,
            }
        }
        baseline_file = results_path / "baseline.json"
        baseline_file.write_text(json.dumps(baseline))

        config = EvalConfig(
            benchmarks_path=benchmarks_path,
            results_path=results_path,
            regression_threshold=0.05,
        )
        harness = EvalHarness(config=config)

        # Create metrics showing regression
        metrics = EvalMetrics(
            pass_at_1=0.82,  # 8.9% regression
            task_completion_rate=0.88,  # 7.4% regression
            pass_8=0.60,
            cost_per_task=0.45,
            avg_duration_ms=300000,
            total_benchmarks=2,
            passed_benchmarks=1,
            failed_benchmarks=1,
        )

        comparison = harness.compare_to_baseline(metrics)

        assert comparison.has_regression is True
        assert len(comparison.regressions) > 0
