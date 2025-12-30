"""
Drift Detection Metrics module for DAW Agent Workbench.

This module provides:
- DriftSeverity: Enum for drift severity levels (NORMAL, WARNING, CRITICAL, EMERGENCY)
- DriftAction: Enum for recommended actions when drift is detected
- MetricType: Enum for different metric types being tracked
- DriftMetric: Model for individual drift measurements
- TaskMetrics: Model for per-task measurement data
- BaselineConfig: Configuration for drift thresholds
- DriftDetector: Main class for detecting behavioral drift

Based on DRIFT-001 requirements and FR-05.1 in PRD:
- Tool Usage Frequency: +50% deviation = WARNING (log warning)
- Reasoning Step Count: +100% increase = CRITICAL (pause agent)
- Context Window Utilization: >90% = WARNING (force compaction)
- Retry Rate: >3x baseline = CRITICAL (escalate to human)
- Token Cost per Task: +200% increase = WARNING (budget alert)

See: docs/planning/prd/02_functional_requirements.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, auto

from pydantic import BaseModel, Field, model_validator


class DriftSeverity(IntEnum):
    """Severity levels for drift detection.

    Ordered from lowest to highest severity for comparison.
    """

    NORMAL = 0
    WARNING = 1
    CRITICAL = 2
    EMERGENCY = 3


class DriftAction(IntEnum):
    """Recommended actions when drift is detected.

    Actions are escalating based on severity:
    - LOG: Log the event for analysis
    - ALERT: Send notification to monitoring
    - PAUSE_AGENT: Stop agent execution
    - FORCE_COMPACTION: Trigger context compaction
    - BUDGET_ALERT: Alert about cost overrun
    - ESCALATE_TO_HUMAN: Require human intervention
    """

    LOG = auto()
    ALERT = auto()
    PAUSE_AGENT = auto()
    FORCE_COMPACTION = auto()
    BUDGET_ALERT = auto()
    ESCALATE_TO_HUMAN = auto()


class MetricType(IntEnum):
    """Types of metrics tracked for drift detection."""

    TOOL_USAGE = auto()
    STEP_COUNT = auto()
    CONTEXT_UTILIZATION = auto()
    RETRY_RATE = auto()
    TOKEN_COST = auto()


class DriftMetric(BaseModel):
    """Model for a single drift metric measurement.

    Represents the comparison of current metric value against baseline,
    with calculated deviation and assigned severity.

    Attributes:
        metric_type: Type of metric being measured
        metric_name: Human-readable name for the metric
        task_type: Type of task this metric applies to
        baseline: Baseline value for comparison
        current: Current measured value
        deviation_pct: Percentage deviation from baseline
        severity: Assigned severity level
        recommended_actions: List of recommended actions
        timestamp: When the measurement was taken
    """

    metric_type: MetricType
    metric_name: str
    task_type: str
    baseline: float = Field(ge=0)
    current: float = Field(ge=0)
    deviation_pct: float | None = None
    severity: DriftSeverity
    recommended_actions: list[DriftAction] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def calculate_deviation(self) -> DriftMetric:
        """Auto-calculate deviation percentage if not provided."""
        if self.deviation_pct is None:
            if self.baseline > 0:
                self.deviation_pct = ((self.current - self.baseline) / self.baseline) * 100
            elif self.current > 0:
                # With zero baseline, any positive current is significant
                self.deviation_pct = float("inf") if self.current > 0 else 0.0
                # Cap at a reasonable value for display
                self.deviation_pct = min(self.deviation_pct, 999999.0)
            else:
                self.deviation_pct = 0.0
        return self


class TaskMetrics(BaseModel):
    """Model for tracking per-task measurements.

    Captures all relevant metrics for a single task execution
    that will be compared against baselines.

    Attributes:
        task_id: Unique identifier for the task
        task_type: Category of task (coding, planning, validation, etc.)
        tool_usage_count: Number of tool calls made
        step_count: Number of reasoning steps taken
        context_tokens: Current tokens in context window
        context_window_size: Maximum context window size
        retry_count: Number of retries performed
        token_cost_usd: Total token cost in USD
        timestamp: When the metrics were recorded
    """

    task_id: str
    task_type: str
    tool_usage_count: int = Field(ge=0)
    step_count: int = Field(ge=0)
    context_tokens: int = Field(ge=0)
    context_window_size: int = Field(gt=0)
    retry_count: int = Field(ge=0)
    token_cost_usd: float = Field(ge=0.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def context_utilization_pct(self) -> float:
        """Calculate context window utilization percentage."""
        return (self.context_tokens / self.context_window_size) * 100


class BaselineConfig(BaseModel):
    """Configuration for drift detection thresholds.

    Default values are based on FR-05.1 requirements:
    - Tool Usage: +50% = WARNING
    - Step Count: +100% = CRITICAL (pause agent)
    - Context Utilization: >90% = WARNING (force compaction)
    - Retry Rate: >3x baseline = CRITICAL (escalate)
    - Token Cost: +200% = WARNING (budget alert)

    Attributes:
        tool_usage_warning_pct: Percentage increase to trigger WARNING
        step_count_critical_pct: Percentage increase to trigger CRITICAL
        context_utilization_warning_pct: Utilization percentage for WARNING
        retry_rate_critical_multiplier: Multiplier of baseline for CRITICAL
        token_cost_warning_pct: Percentage increase for budget WARNING
    """

    tool_usage_warning_pct: float = Field(default=50.0, ge=0)
    step_count_critical_pct: float = Field(default=100.0, ge=0)
    context_utilization_warning_pct: float = Field(default=90.0, ge=0, le=100)
    retry_rate_critical_multiplier: float = Field(default=3.0, ge=1.0)
    token_cost_warning_pct: float = Field(default=200.0, ge=0)


class DriftDetector:
    """Main class for detecting behavioral drift in agent execution.

    Compares current task metrics against recorded baselines to
    identify when agent behavior deviates from expected patterns.

    Thresholds (from FR-05.1):
    - Tool Usage Frequency: +50% deviation = WARNING (log warning)
    - Reasoning Step Count: +100% increase = CRITICAL (pause agent)
    - Context Window Utilization: >90% = WARNING (force compaction)
    - Retry Rate: >3x baseline = CRITICAL (escalate to human)
    - Token Cost per Task: +200% increase = WARNING (budget alert)

    Usage:
        detector = DriftDetector()

        # Record baselines from historical data
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )

        # Evaluate current task
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

        # Check severity and actions
        max_severity = detector.get_max_severity(results)
        actions = detector.get_recommended_actions(results)
    """

    def __init__(self, config: BaselineConfig | None = None) -> None:
        """Initialize DriftDetector with optional custom configuration.

        Args:
            config: Custom threshold configuration. Uses defaults if None.
        """
        self.config = config or BaselineConfig()
        self.baselines: dict[str, dict[str, float]] = {}

    def record_baseline(
        self,
        task_type: str,
        tool_usage_count: float,
        step_count: float,
        context_tokens: float,
        retry_count: float,
        token_cost_usd: float,
    ) -> None:
        """Record baseline metrics for a task type.

        Baselines should be calculated from historical data representing
        normal agent behavior for each task type.

        Args:
            task_type: Category of task (e.g., "coding", "planning")
            tool_usage_count: Average tool calls per task
            step_count: Average reasoning steps per task
            context_tokens: Average context tokens used
            retry_count: Average retries per task
            token_cost_usd: Average cost per task in USD
        """
        self.baselines[task_type] = {
            "tool_usage_count": tool_usage_count,
            "step_count": step_count,
            "context_tokens": context_tokens,
            "retry_count": retry_count,
            "token_cost_usd": token_cost_usd,
        }

    def evaluate(self, metrics: TaskMetrics) -> list[DriftMetric]:
        """Evaluate current task metrics against baselines.

        Compares all metric types against recorded baselines and
        assigns severity levels based on configured thresholds.

        Args:
            metrics: Current task metrics to evaluate

        Returns:
            List of DriftMetric objects, one for each metric type

        Raises:
            ValueError: If no baseline exists for the task type
        """
        task_type = metrics.task_type

        if task_type not in self.baselines:
            raise ValueError(f"No baseline found for task type: {task_type}")

        baseline = self.baselines[task_type]
        results: list[DriftMetric] = []

        # Evaluate Tool Usage
        results.append(self._evaluate_tool_usage(metrics, baseline))

        # Evaluate Step Count
        results.append(self._evaluate_step_count(metrics, baseline))

        # Evaluate Context Utilization
        results.append(self._evaluate_context_utilization(metrics))

        # Evaluate Retry Rate
        results.append(self._evaluate_retry_rate(metrics, baseline))

        # Evaluate Token Cost
        results.append(self._evaluate_token_cost(metrics, baseline))

        return results

    def _evaluate_tool_usage(
        self, metrics: TaskMetrics, baseline: dict[str, float]
    ) -> DriftMetric:
        """Evaluate tool usage drift.

        +50% deviation = WARNING with LOG action.
        """
        baseline_val = baseline["tool_usage_count"]
        current_val = float(metrics.tool_usage_count)

        if baseline_val > 0:
            deviation_pct = ((current_val - baseline_val) / baseline_val) * 100
        else:
            deviation_pct = 0.0 if current_val == 0 else 100.0

        severity = DriftSeverity.NORMAL
        actions: list[DriftAction] = []

        if deviation_pct >= self.config.tool_usage_warning_pct:
            severity = DriftSeverity.WARNING
            actions = [DriftAction.LOG, DriftAction.ALERT]

        return DriftMetric(
            metric_type=MetricType.TOOL_USAGE,
            metric_name="tool_calls",
            task_type=metrics.task_type,
            baseline=baseline_val,
            current=current_val,
            deviation_pct=deviation_pct,
            severity=severity,
            recommended_actions=actions,
        )

    def _evaluate_step_count(
        self, metrics: TaskMetrics, baseline: dict[str, float]
    ) -> DriftMetric:
        """Evaluate reasoning step count drift.

        +100% increase = CRITICAL with PAUSE_AGENT action.
        """
        baseline_val = baseline["step_count"]
        current_val = float(metrics.step_count)

        if baseline_val > 0:
            deviation_pct = ((current_val - baseline_val) / baseline_val) * 100
        else:
            deviation_pct = 0.0 if current_val == 0 else 100.0

        severity = DriftSeverity.NORMAL
        actions: list[DriftAction] = []

        if deviation_pct >= self.config.step_count_critical_pct:
            severity = DriftSeverity.CRITICAL
            actions = [DriftAction.PAUSE_AGENT, DriftAction.ESCALATE_TO_HUMAN]

        return DriftMetric(
            metric_type=MetricType.STEP_COUNT,
            metric_name="reasoning_steps",
            task_type=metrics.task_type,
            baseline=baseline_val,
            current=current_val,
            deviation_pct=deviation_pct,
            severity=severity,
            recommended_actions=actions,
        )

    def _evaluate_context_utilization(self, metrics: TaskMetrics) -> DriftMetric:
        """Evaluate context window utilization.

        >90% utilization = WARNING with FORCE_COMPACTION action.

        Note: This uses absolute percentage, not deviation from baseline.
        """
        utilization = metrics.context_utilization_pct
        baseline_val = self.config.context_utilization_warning_pct
        current_val = utilization

        severity = DriftSeverity.NORMAL
        actions: list[DriftAction] = []

        if utilization >= self.config.context_utilization_warning_pct:
            severity = DriftSeverity.WARNING
            actions = [DriftAction.FORCE_COMPACTION, DriftAction.ALERT]

        return DriftMetric(
            metric_type=MetricType.CONTEXT_UTILIZATION,
            metric_name="context_window",
            task_type=metrics.task_type,
            baseline=baseline_val,
            current=current_val,
            deviation_pct=utilization - baseline_val,  # How much over threshold
            severity=severity,
            recommended_actions=actions,
        )

    def _evaluate_retry_rate(
        self, metrics: TaskMetrics, baseline: dict[str, float]
    ) -> DriftMetric:
        """Evaluate retry rate drift.

        >3x baseline = CRITICAL with ESCALATE_TO_HUMAN action.
        """
        baseline_val = baseline["retry_count"]
        current_val = float(metrics.retry_count)

        # Calculate multiplier instead of percentage
        if baseline_val > 0:
            multiplier = current_val / baseline_val
            deviation_pct = (multiplier - 1.0) * 100  # Convert to percentage
        else:
            multiplier = current_val  # Any retries when baseline is 0
            deviation_pct = current_val * 100 if current_val > 0 else 0.0

        severity = DriftSeverity.NORMAL
        actions: list[DriftAction] = []

        if multiplier >= self.config.retry_rate_critical_multiplier:
            severity = DriftSeverity.CRITICAL
            actions = [DriftAction.ESCALATE_TO_HUMAN, DriftAction.ALERT]

        return DriftMetric(
            metric_type=MetricType.RETRY_RATE,
            metric_name="retries",
            task_type=metrics.task_type,
            baseline=baseline_val,
            current=current_val,
            deviation_pct=deviation_pct,
            severity=severity,
            recommended_actions=actions,
        )

    def _evaluate_token_cost(
        self, metrics: TaskMetrics, baseline: dict[str, float]
    ) -> DriftMetric:
        """Evaluate token cost drift.

        +200% increase = WARNING with BUDGET_ALERT action.
        """
        baseline_val = baseline["token_cost_usd"]
        current_val = metrics.token_cost_usd

        if baseline_val > 0:
            deviation_pct = ((current_val - baseline_val) / baseline_val) * 100
        else:
            deviation_pct = 0.0 if current_val == 0 else 200.0

        severity = DriftSeverity.NORMAL
        actions: list[DriftAction] = []

        # Use small epsilon for floating point comparison (1e-9)
        threshold = self.config.token_cost_warning_pct
        if deviation_pct >= threshold - 1e-9:
            severity = DriftSeverity.WARNING
            actions = [DriftAction.BUDGET_ALERT, DriftAction.ALERT]

        return DriftMetric(
            metric_type=MetricType.TOKEN_COST,
            metric_name="token_cost",
            task_type=metrics.task_type,
            baseline=baseline_val,
            current=current_val,
            deviation_pct=deviation_pct,
            severity=severity,
            recommended_actions=actions,
        )

    def get_max_severity(self, results: list[DriftMetric]) -> DriftSeverity:
        """Get the maximum severity from drift results.

        Args:
            results: List of DriftMetric objects from evaluate()

        Returns:
            The highest severity level found in results
        """
        if not results:
            return DriftSeverity.NORMAL

        return max(r.severity for r in results)

    def get_recommended_actions(self, results: list[DriftMetric]) -> set[DriftAction]:
        """Collect all recommended actions from drift results.

        Args:
            results: List of DriftMetric objects from evaluate()

        Returns:
            Set of all unique recommended actions
        """
        actions: set[DriftAction] = set()

        for result in results:
            actions.update(result.recommended_actions)

        return actions
