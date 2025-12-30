"""
Tests for Drift Detection Metrics module (DRIFT-001).

These tests verify:
1. DriftMetric model - metric name, baseline, current, deviation percentage, severity
2. DriftSeverity enum - NORMAL, WARNING, CRITICAL, EMERGENCY
3. DriftDetector class - initialization and configuration
4. Tool usage frequency tracking (+50% deviation = WARNING)
5. Reasoning step count tracking (+100% increase = CRITICAL, pause agent)
6. Context window utilization (>90% = WARNING, force compaction)
7. Retry rate tracking (>3x baseline = CRITICAL, escalate to human)
8. Token cost per task (+200% increase = WARNING, budget alert)
9. Baseline calculation per task type
10. Drift evaluation with severity assignment
11. Integration with Helicone tracker for cost data

Based on FR-05.1 in PRD requirements.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from daw_agents.ops.drift_detector import (
    BaselineConfig,
    DriftAction,
    DriftDetector,
    DriftMetric,
    DriftSeverity,
    MetricType,
    TaskMetrics,
)


class TestDriftSeverity:
    """Test DriftSeverity enum."""

    def test_severity_levels_exist(self) -> None:
        """Test that all required severity levels exist."""
        assert DriftSeverity.NORMAL is not None
        assert DriftSeverity.WARNING is not None
        assert DriftSeverity.CRITICAL is not None
        assert DriftSeverity.EMERGENCY is not None

    def test_severity_ordering(self) -> None:
        """Test that severity levels have correct ordering."""
        # NORMAL < WARNING < CRITICAL < EMERGENCY
        assert DriftSeverity.NORMAL.value < DriftSeverity.WARNING.value
        assert DriftSeverity.WARNING.value < DriftSeverity.CRITICAL.value
        assert DriftSeverity.CRITICAL.value < DriftSeverity.EMERGENCY.value


class TestDriftAction:
    """Test DriftAction enum."""

    def test_action_types_exist(self) -> None:
        """Test that all required action types exist."""
        assert DriftAction.LOG is not None
        assert DriftAction.ALERT is not None
        assert DriftAction.PAUSE_AGENT is not None
        assert DriftAction.FORCE_COMPACTION is not None
        assert DriftAction.BUDGET_ALERT is not None
        assert DriftAction.ESCALATE_TO_HUMAN is not None


class TestMetricType:
    """Test MetricType enum."""

    def test_metric_types_exist(self) -> None:
        """Test that all required metric types exist."""
        assert MetricType.TOOL_USAGE is not None
        assert MetricType.STEP_COUNT is not None
        assert MetricType.CONTEXT_UTILIZATION is not None
        assert MetricType.RETRY_RATE is not None
        assert MetricType.TOKEN_COST is not None


class TestDriftMetric:
    """Test DriftMetric Pydantic model."""

    def test_drift_metric_creation(self) -> None:
        """Test creating DriftMetric with all fields."""
        metric = DriftMetric(
            metric_type=MetricType.TOOL_USAGE,
            metric_name="tool_calls",
            task_type="coding",
            baseline=10.0,
            current=15.0,
            deviation_pct=50.0,
            severity=DriftSeverity.WARNING,
            recommended_actions=[DriftAction.LOG, DriftAction.ALERT],
        )
        assert metric.metric_type == MetricType.TOOL_USAGE
        assert metric.metric_name == "tool_calls"
        assert metric.task_type == "coding"
        assert metric.baseline == 10.0
        assert metric.current == 15.0
        assert metric.deviation_pct == 50.0
        assert metric.severity == DriftSeverity.WARNING
        assert DriftAction.LOG in metric.recommended_actions

    def test_drift_metric_auto_deviation_calculation(self) -> None:
        """Test that deviation percentage can be auto-calculated."""
        metric = DriftMetric(
            metric_type=MetricType.TOOL_USAGE,
            metric_name="tool_calls",
            task_type="coding",
            baseline=10.0,
            current=15.0,
            severity=DriftSeverity.WARNING,
        )
        # Should auto-calculate: (15 - 10) / 10 * 100 = 50%
        assert metric.deviation_pct == 50.0

    def test_drift_metric_zero_baseline(self) -> None:
        """Test handling of zero baseline (avoid division by zero)."""
        metric = DriftMetric(
            metric_type=MetricType.RETRY_RATE,
            metric_name="retries",
            task_type="coding",
            baseline=0.0,
            current=3.0,
            severity=DriftSeverity.CRITICAL,
        )
        # With zero baseline, any positive current should indicate high deviation
        assert metric.deviation_pct > 0

    def test_drift_metric_timestamp(self) -> None:
        """Test that timestamp is set automatically."""
        metric = DriftMetric(
            metric_type=MetricType.TOOL_USAGE,
            metric_name="tool_calls",
            task_type="coding",
            baseline=10.0,
            current=12.0,
            severity=DriftSeverity.NORMAL,
        )
        assert metric.timestamp is not None
        # Should be recent (within last minute)
        now = datetime.now(UTC)
        assert (now - metric.timestamp).total_seconds() < 60


class TestTaskMetrics:
    """Test TaskMetrics model for tracking per-task measurements."""

    def test_task_metrics_creation(self) -> None:
        """Test creating TaskMetrics with all fields."""
        metrics = TaskMetrics(
            task_id="CORE-001",
            task_type="coding",
            tool_usage_count=15,
            step_count=25,
            context_tokens=100000,
            context_window_size=128000,
            retry_count=2,
            token_cost_usd=0.15,
        )
        assert metrics.task_id == "CORE-001"
        assert metrics.task_type == "coding"
        assert metrics.tool_usage_count == 15
        assert metrics.step_count == 25
        assert metrics.context_tokens == 100000
        assert metrics.context_window_size == 128000
        assert metrics.retry_count == 2
        assert metrics.token_cost_usd == 0.15

    def test_task_metrics_context_utilization(self) -> None:
        """Test context utilization percentage calculation."""
        metrics = TaskMetrics(
            task_id="CORE-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=115200,  # 90% of 128000
            context_window_size=128000,
            retry_count=0,
            token_cost_usd=0.10,
        )
        # Should calculate: 115200 / 128000 * 100 = 90%
        assert metrics.context_utilization_pct == 90.0


class TestBaselineConfig:
    """Test BaselineConfig for threshold configuration."""

    def test_baseline_config_defaults(self) -> None:
        """Test BaselineConfig default thresholds."""
        config = BaselineConfig()
        # Default thresholds from requirements
        assert config.tool_usage_warning_pct == 50.0  # +50% = WARNING
        assert config.step_count_critical_pct == 100.0  # +100% = CRITICAL
        assert config.context_utilization_warning_pct == 90.0  # >90% = WARNING
        assert config.retry_rate_critical_multiplier == 3.0  # >3x = CRITICAL
        assert config.token_cost_warning_pct == 200.0  # +200% = WARNING

    def test_baseline_config_custom(self) -> None:
        """Test BaselineConfig with custom thresholds."""
        config = BaselineConfig(
            tool_usage_warning_pct=75.0,
            step_count_critical_pct=150.0,
            context_utilization_warning_pct=85.0,
            retry_rate_critical_multiplier=5.0,
            token_cost_warning_pct=300.0,
        )
        assert config.tool_usage_warning_pct == 75.0
        assert config.step_count_critical_pct == 150.0
        assert config.context_utilization_warning_pct == 85.0
        assert config.retry_rate_critical_multiplier == 5.0
        assert config.token_cost_warning_pct == 300.0


class TestDriftDetector:
    """Test DriftDetector main class."""

    @pytest.fixture
    def detector(self) -> DriftDetector:
        """Create a DriftDetector instance for testing."""
        return DriftDetector()

    @pytest.fixture
    def detector_with_config(self) -> DriftDetector:
        """Create a DriftDetector with custom configuration."""
        config = BaselineConfig(
            tool_usage_warning_pct=40.0,
            step_count_critical_pct=80.0,
        )
        return DriftDetector(config=config)

    def test_detector_initialization(self, detector: DriftDetector) -> None:
        """Test that detector initializes correctly."""
        assert detector.config is not None
        assert detector.baselines == {}

    def test_detector_custom_config(self, detector_with_config: DriftDetector) -> None:
        """Test that detector accepts custom configuration."""
        assert detector_with_config.config.tool_usage_warning_pct == 40.0
        assert detector_with_config.config.step_count_critical_pct == 80.0

    # === Baseline Recording Tests ===

    def test_record_baseline(self, detector: DriftDetector) -> None:
        """Test recording a baseline for a task type."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        assert "coding" in detector.baselines
        baseline = detector.baselines["coding"]
        assert baseline["tool_usage_count"] == 10.0
        assert baseline["step_count"] == 20.0
        assert baseline["context_tokens"] == 50000.0
        assert baseline["retry_count"] == 1.0
        assert baseline["token_cost_usd"] == 0.10

    def test_record_multiple_baselines(self, detector: DriftDetector) -> None:
        """Test recording baselines for multiple task types."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )
        detector.record_baseline(
            task_type="planning",
            tool_usage_count=5.0,
            step_count=15.0,
            context_tokens=30000.0,
            retry_count=0.5,
            token_cost_usd=0.25,
        )

        assert "coding" in detector.baselines
        assert "planning" in detector.baselines
        assert detector.baselines["coding"]["tool_usage_count"] == 10.0
        assert detector.baselines["planning"]["tool_usage_count"] == 5.0

    def test_update_baseline(self, detector: DriftDetector) -> None:
        """Test that recording a baseline updates existing values."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        # Update with new values
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=12.0,
            step_count=22.0,
            context_tokens=55000.0,
            retry_count=1.5,
            token_cost_usd=0.12,
        )

        baseline = detector.baselines["coding"]
        assert baseline["tool_usage_count"] == 12.0
        assert baseline["step_count"] == 22.0

    # === Tool Usage Drift Tests ===

    def test_tool_usage_normal(self, detector: DriftDetector) -> None:
        """Test that normal tool usage shows no drift."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=12,  # 20% increase, below 50% threshold
            step_count=22,
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        tool_metric = next((m for m in results if m.metric_type == MetricType.TOOL_USAGE), None)
        assert tool_metric is not None
        assert tool_metric.severity == DriftSeverity.NORMAL

    def test_tool_usage_warning(self, detector: DriftDetector) -> None:
        """Test that +50% tool usage triggers WARNING."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=15,  # 50% increase
            step_count=22,
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        tool_metric = next((m for m in results if m.metric_type == MetricType.TOOL_USAGE), None)
        assert tool_metric is not None
        assert tool_metric.severity == DriftSeverity.WARNING
        assert tool_metric.deviation_pct == 50.0
        assert DriftAction.LOG in tool_metric.recommended_actions

    # === Reasoning Step Count Drift Tests ===

    def test_step_count_normal(self, detector: DriftDetector) -> None:
        """Test that normal step count shows no drift."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=30,  # 50% increase, below 100% threshold
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        step_metric = next((m for m in results if m.metric_type == MetricType.STEP_COUNT), None)
        assert step_metric is not None
        assert step_metric.severity == DriftSeverity.NORMAL

    def test_step_count_critical_pause_agent(self, detector: DriftDetector) -> None:
        """Test that +100% step count triggers CRITICAL and PAUSE_AGENT."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=40,  # 100% increase
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        step_metric = next((m for m in results if m.metric_type == MetricType.STEP_COUNT), None)
        assert step_metric is not None
        assert step_metric.severity == DriftSeverity.CRITICAL
        assert step_metric.deviation_pct == 100.0
        assert DriftAction.PAUSE_AGENT in step_metric.recommended_actions

    # === Context Window Utilization Tests ===

    def test_context_utilization_normal(self, detector: DriftDetector) -> None:
        """Test that normal context utilization shows no drift."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=100000,  # 78% of 128000, below 90%
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        ctx_metric = next((m for m in results if m.metric_type == MetricType.CONTEXT_UTILIZATION), None)
        assert ctx_metric is not None
        assert ctx_metric.severity == DriftSeverity.NORMAL

    def test_context_utilization_warning_force_compaction(self, detector: DriftDetector) -> None:
        """Test that >90% context utilization triggers WARNING and FORCE_COMPACTION."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=120000,  # 93.75% of 128000, above 90%
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        ctx_metric = next((m for m in results if m.metric_type == MetricType.CONTEXT_UTILIZATION), None)
        assert ctx_metric is not None
        assert ctx_metric.severity == DriftSeverity.WARNING
        assert DriftAction.FORCE_COMPACTION in ctx_metric.recommended_actions

    # === Retry Rate Tests ===

    def test_retry_rate_normal(self, detector: DriftDetector) -> None:
        """Test that normal retry rate shows no drift."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=2,  # 2x baseline, below 3x threshold
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        retry_metric = next((m for m in results if m.metric_type == MetricType.RETRY_RATE), None)
        assert retry_metric is not None
        assert retry_metric.severity == DriftSeverity.NORMAL

    def test_retry_rate_critical_escalate(self, detector: DriftDetector) -> None:
        """Test that >3x retry rate triggers CRITICAL and ESCALATE_TO_HUMAN."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=4,  # 4x baseline, above 3x threshold
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)
        retry_metric = next((m for m in results if m.metric_type == MetricType.RETRY_RATE), None)
        assert retry_metric is not None
        assert retry_metric.severity == DriftSeverity.CRITICAL
        assert DriftAction.ESCALATE_TO_HUMAN in retry_metric.recommended_actions

    # === Token Cost Tests ===

    def test_token_cost_normal(self, detector: DriftDetector) -> None:
        """Test that normal token cost shows no drift."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.20,  # 100% increase, below 200% threshold
        )

        results = detector.evaluate(metrics)
        cost_metric = next((m for m in results if m.metric_type == MetricType.TOKEN_COST), None)
        assert cost_metric is not None
        assert cost_metric.severity == DriftSeverity.NORMAL

    def test_token_cost_warning_budget_alert(self, detector: DriftDetector) -> None:
        """Test that +200% token cost triggers WARNING and BUDGET_ALERT."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.30,  # 200% increase
        )

        results = detector.evaluate(metrics)
        cost_metric = next((m for m in results if m.metric_type == MetricType.TOKEN_COST), None)
        assert cost_metric is not None
        assert cost_metric.severity == DriftSeverity.WARNING
        # Use approximate comparison for floating point (199.999... is close to 200.0)
        assert cost_metric.deviation_pct is not None
        assert abs(cost_metric.deviation_pct - 200.0) < 0.01
        assert DriftAction.BUDGET_ALERT in cost_metric.recommended_actions

    # === Missing Baseline Tests ===

    def test_evaluate_without_baseline_raises_error(self, detector: DriftDetector) -> None:
        """Test that evaluating without a baseline raises an error."""
        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",  # No baseline recorded for 'coding'
            tool_usage_count=10,
            step_count=20,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.10,
        )

        with pytest.raises(ValueError, match="No baseline found for task type"):
            detector.evaluate(metrics)

    # === Multiple Drift Detection ===

    def test_multiple_drift_conditions(self, detector: DriftDetector) -> None:
        """Test detection of multiple drift conditions simultaneously."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=15,  # 50% increase -> WARNING
            step_count=40,  # 100% increase -> CRITICAL
            context_tokens=120000,  # >90% -> WARNING
            context_window_size=128000,
            retry_count=4,  # >3x -> CRITICAL
            token_cost_usd=0.30,  # 200% increase -> WARNING
        )

        results = detector.evaluate(metrics)

        # Should detect all drift conditions
        assert len(results) == 5

        # Verify each metric detected correctly
        severities = {r.metric_type: r.severity for r in results}
        assert severities[MetricType.TOOL_USAGE] == DriftSeverity.WARNING
        assert severities[MetricType.STEP_COUNT] == DriftSeverity.CRITICAL
        assert severities[MetricType.CONTEXT_UTILIZATION] == DriftSeverity.WARNING
        assert severities[MetricType.RETRY_RATE] == DriftSeverity.CRITICAL
        assert severities[MetricType.TOKEN_COST] == DriftSeverity.WARNING

    # === Aggregate Severity Tests ===

    def test_get_max_severity(self, detector: DriftDetector) -> None:
        """Test getting maximum severity from drift results."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        # Create metrics that trigger CRITICAL drift
        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=15,  # WARNING
            step_count=40,  # CRITICAL
            context_tokens=55000,  # NORMAL
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,  # NORMAL
        )

        results = detector.evaluate(metrics)
        max_severity = detector.get_max_severity(results)

        assert max_severity == DriftSeverity.CRITICAL

    def test_get_max_severity_all_normal(self, detector: DriftDetector) -> None:
        """Test that max severity is NORMAL when no drift detected."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=10,
            step_count=20,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.10,
        )

        results = detector.evaluate(metrics)
        max_severity = detector.get_max_severity(results)

        assert max_severity == DriftSeverity.NORMAL

    # === Action Collection Tests ===

    def test_get_recommended_actions(self, detector: DriftDetector) -> None:
        """Test collecting all recommended actions from drift results."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=15,  # WARNING -> LOG
            step_count=40,  # CRITICAL -> PAUSE_AGENT
            context_tokens=120000,  # WARNING -> FORCE_COMPACTION
            context_window_size=128000,
            retry_count=4,  # CRITICAL -> ESCALATE_TO_HUMAN
            token_cost_usd=0.30,  # WARNING -> BUDGET_ALERT
        )

        results = detector.evaluate(metrics)
        actions = detector.get_recommended_actions(results)

        assert DriftAction.LOG in actions
        assert DriftAction.PAUSE_AGENT in actions
        assert DriftAction.FORCE_COMPACTION in actions
        assert DriftAction.ESCALATE_TO_HUMAN in actions
        assert DriftAction.BUDGET_ALERT in actions

    # === History and Trends ===

    def test_evaluate_returns_drift_metrics(self, detector: DriftDetector) -> None:
        """Test that evaluate returns list of DriftMetric objects."""
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=12,
            step_count=22,
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

        results = detector.evaluate(metrics)

        assert isinstance(results, list)
        assert len(results) > 0
        for result in results:
            assert isinstance(result, DriftMetric)


class TestDriftDetectorIntegration:
    """Test DriftDetector integration scenarios."""

    def test_full_workflow(self) -> None:
        """Test complete drift detection workflow."""
        # Initialize detector
        detector = DriftDetector()

        # Record baseline from historical data
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        # Simulate a task with drift
        metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=16,  # 60% increase -> WARNING
            step_count=25,  # 25% increase -> NORMAL
            context_tokens=115000,  # ~90% context -> WARNING
            context_window_size=128000,
            retry_count=1,  # Normal
            token_cost_usd=0.15,  # 50% increase -> NORMAL
        )

        # Evaluate drift
        results = detector.evaluate(metrics)
        max_severity = detector.get_max_severity(results)
        actions = detector.get_recommended_actions(results)

        # Should detect WARNING level drift
        assert max_severity == DriftSeverity.WARNING
        assert len(actions) > 0

    def test_baseline_per_task_type_isolation(self) -> None:
        """Test that baselines are correctly isolated per task type."""
        detector = DriftDetector()

        # Record different baselines for different task types
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )
        detector.record_baseline(
            task_type="planning",
            tool_usage_count=5.0,  # Planning uses fewer tools
            step_count=10.0,  # Fewer steps
            context_tokens=30000.0,
            retry_count=0.5,
            token_cost_usd=0.25,  # But costs more per task
        )

        # A task that's normal for coding but would be high for planning
        coding_metrics = TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=12,  # 20% increase from coding baseline
            step_count=24,
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.12,
        )

        # Same numbers but for planning task
        planning_metrics = TaskMetrics(
            task_id="TEST-002",
            task_type="planning",
            tool_usage_count=8,  # 60% increase from planning baseline -> WARNING
            step_count=20,  # 100% increase -> CRITICAL
            context_tokens=55000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.30,  # 20% increase -> NORMAL
        )

        coding_results = detector.evaluate(coding_metrics)
        planning_results = detector.evaluate(planning_metrics)

        coding_max = detector.get_max_severity(coding_results)
        planning_max = detector.get_max_severity(planning_results)

        # Coding should be mostly normal
        assert coding_max == DriftSeverity.NORMAL
        # Planning should have higher severity due to different baseline
        assert planning_max == DriftSeverity.CRITICAL
