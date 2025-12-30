"""
Tests for Drift Detection Alerting and Actions (DRIFT-002).

Tests cover:
- AlertChannel enum for delivery channels (SLACK, LINEAR, EMAIL, WEBHOOK)
- AlertConfig Pydantic model for alert configuration
- AlertSender class for sending alerts to various channels
- DriftActionHandler class for executing actions based on drift severity
- DriftAlertSystem class for integrated alerting
- WeeklyReportGenerator for drift reports
- Severity-to-action mapping

Based on DRIFT-002 requirements and FR-05.1 in PRD.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

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

# Import the modules we are testing - these do not exist yet (RED phase)
from daw_agents.ops.alerts import (
    AlertChannel,
    AlertConfig,
    AlertResult,
    AlertSender,
    DriftAlertSystem,
    SeverityActionMapping,
    WeeklyReportGenerator,
)
from daw_agents.ops.actions import (
    ActionResult,
    DriftActionHandler,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# ============================================================================
# AlertChannel Enum Tests
# ============================================================================


class TestAlertChannel:
    """Tests for AlertChannel enum."""

    def test_alert_channel_values(self) -> None:
        """Test that AlertChannel has all expected values."""
        assert AlertChannel.SLACK is not None
        assert AlertChannel.LINEAR is not None
        assert AlertChannel.EMAIL is not None
        assert AlertChannel.WEBHOOK is not None

    def test_alert_channel_is_enum(self) -> None:
        """Test that AlertChannel is an enum."""
        assert len(AlertChannel) == 4


# ============================================================================
# AlertConfig Tests
# ============================================================================


class TestAlertConfig:
    """Tests for AlertConfig Pydantic model."""

    def test_alert_config_with_slack(self) -> None:
        """Test AlertConfig with Slack configuration."""
        config = AlertConfig(
            slack_webhook_url="https://hooks.slack.com/services/xxx",
            slack_channel="#alerts",
        )
        assert config.slack_webhook_url == "https://hooks.slack.com/services/xxx"
        assert config.slack_channel == "#alerts"

    def test_alert_config_with_linear(self) -> None:
        """Test AlertConfig with Linear configuration."""
        config = AlertConfig(
            linear_api_key="lin_api_xxx",
            linear_team_id="team-123",
        )
        assert config.linear_api_key == "lin_api_xxx"
        assert config.linear_team_id == "team-123"

    def test_alert_config_with_email(self) -> None:
        """Test AlertConfig with email configuration."""
        config = AlertConfig(
            email_recipients=["ops@example.com", "dev@example.com"],
            smtp_host="smtp.example.com",
            smtp_port=587,
        )
        assert len(config.email_recipients) == 2
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 587

    def test_alert_config_with_webhook(self) -> None:
        """Test AlertConfig with custom webhook configuration."""
        config = AlertConfig(
            webhook_url="https://example.com/webhook",
            webhook_headers={"Authorization": "Bearer xxx"},
        )
        assert config.webhook_url == "https://example.com/webhook"
        assert config.webhook_headers["Authorization"] == "Bearer xxx"

    def test_alert_config_all_channels(self) -> None:
        """Test AlertConfig with all channels configured."""
        config = AlertConfig(
            slack_webhook_url="https://hooks.slack.com/services/xxx",
            slack_channel="#alerts",
            linear_api_key="lin_api_xxx",
            linear_team_id="team-123",
            email_recipients=["ops@example.com"],
            smtp_host="smtp.example.com",
            webhook_url="https://example.com/webhook",
        )
        assert config.slack_webhook_url is not None
        assert config.linear_api_key is not None
        assert len(config.email_recipients) == 1
        assert config.webhook_url is not None

    def test_alert_config_from_env(self) -> None:
        """Test AlertConfig.from_env() class method."""
        with patch.dict(
            "os.environ",
            {
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
                "SLACK_CHANNEL": "#test-alerts",
                "LINEAR_API_KEY": "lin_test",
                "LINEAR_TEAM_ID": "team-test",
            },
        ):
            config = AlertConfig.from_env()
            assert config.slack_webhook_url == "https://hooks.slack.com/test"
            assert config.slack_channel == "#test-alerts"


# ============================================================================
# AlertResult Tests
# ============================================================================


class TestAlertResult:
    """Tests for AlertResult model."""

    def test_alert_result_success(self) -> None:
        """Test successful alert result."""
        result = AlertResult(
            channel=AlertChannel.SLACK,
            success=True,
            message="Alert sent successfully",
        )
        assert result.success is True
        assert result.channel == AlertChannel.SLACK

    def test_alert_result_failure(self) -> None:
        """Test failed alert result."""
        result = AlertResult(
            channel=AlertChannel.EMAIL,
            success=False,
            message="SMTP connection failed",
            error_code="SMTP_ERROR",
        )
        assert result.success is False
        assert result.error_code == "SMTP_ERROR"


# ============================================================================
# AlertSender Tests
# ============================================================================


class TestAlertSender:
    """Tests for AlertSender class."""

    @pytest.fixture
    def alert_config(self) -> AlertConfig:
        """Create a test alert configuration."""
        return AlertConfig(
            slack_webhook_url="https://hooks.slack.com/services/test",
            slack_channel="#test-alerts",
            linear_api_key="lin_api_test",
            linear_team_id="team-test",
            email_recipients=["test@example.com"],
            smtp_host="localhost",
            smtp_port=25,
            webhook_url="https://example.com/webhook",
        )

    @pytest.fixture
    def alert_sender(self, alert_config: AlertConfig) -> AlertSender:
        """Create AlertSender instance."""
        return AlertSender(config=alert_config)

    @pytest.fixture
    def sample_drift_metric(self) -> DriftMetric:
        """Create a sample drift metric for testing."""
        return DriftMetric(
            metric_type=MetricType.TOOL_USAGE,
            metric_name="tool_calls",
            task_type="coding",
            baseline=10.0,
            current=16.0,
            deviation_pct=60.0,
            severity=DriftSeverity.WARNING,
            recommended_actions=[DriftAction.LOG, DriftAction.ALERT],
        )

    @pytest.mark.asyncio
    async def test_send_slack_alert(
        self, alert_sender: AlertSender, sample_drift_metric: DriftMetric
    ) -> None:
        """Test sending alert to Slack."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = await alert_sender.send_slack_alert(
                drift_metric=sample_drift_metric,
                title="Drift Detected",
                message="Tool usage increased by 60%",
            )
            assert result.success is True
            assert result.channel == AlertChannel.SLACK

    @pytest.mark.asyncio
    async def test_send_linear_alert(
        self, alert_sender: AlertSender, sample_drift_metric: DriftMetric
    ) -> None:
        """Test creating Linear ticket for drift alert."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "data": {
                        "issueCreate": {
                            "success": True,
                            "issue": {"id": "issue-123", "url": "https://linear.app/issue-123"},
                        }
                    }
                },
            )
            result = await alert_sender.send_linear_alert(
                drift_metric=sample_drift_metric,
                title="Critical Drift: Agent Paused",
                description="Step count doubled, agent paused for investigation.",
            )
            assert result.success is True
            assert result.channel == AlertChannel.LINEAR

    @pytest.mark.asyncio
    async def test_send_email_alert(
        self, alert_sender: AlertSender, sample_drift_metric: DriftMetric
    ) -> None:
        """Test sending email alert."""
        import sys
        mock_aiosmtplib = MagicMock()
        mock_aiosmtplib.send = AsyncMock(return_value=None)
        with patch.dict(sys.modules, {"aiosmtplib": mock_aiosmtplib}):
            result = await alert_sender.send_email_alert(
                drift_metric=sample_drift_metric,
                subject="Drift Alert: Budget Warning",
                body="Token costs have increased by 200%.",
            )
            assert result.success is True
            assert result.channel == AlertChannel.EMAIL

    @pytest.mark.asyncio
    async def test_send_webhook_alert(
        self, alert_sender: AlertSender, sample_drift_metric: DriftMetric
    ) -> None:
        """Test sending alert to custom webhook."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = await alert_sender.send_webhook_alert(
                drift_metric=sample_drift_metric,
                payload={"event": "drift_detected", "severity": "warning"},
            )
            assert result.success is True
            assert result.channel == AlertChannel.WEBHOOK

    @pytest.mark.asyncio
    async def test_send_alert_handles_errors(
        self, alert_sender: AlertSender, sample_drift_metric: DriftMetric
    ) -> None:
        """Test that alert sender handles network errors gracefully."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            result = await alert_sender.send_slack_alert(
                drift_metric=sample_drift_metric,
                title="Test",
                message="Test message",
            )
            assert result.success is False
            assert "error" in result.message.lower() or result.error_code is not None

    @pytest.mark.asyncio
    async def test_send_to_all_channels(
        self, alert_sender: AlertSender, sample_drift_metric: DriftMetric
    ) -> None:
        """Test sending to all configured channels."""
        import sys
        mock_aiosmtplib = MagicMock()
        mock_aiosmtplib.send = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            with patch.dict(sys.modules, {"aiosmtplib": mock_aiosmtplib}):
                results = await alert_sender.send_to_all_channels(
                    drift_metric=sample_drift_metric,
                    title="Drift Alert",
                    message="Drift detected across multiple metrics.",
                )
                assert len(results) == 4  # All 4 channels


# ============================================================================
# ActionResult Tests
# ============================================================================


class TestActionResult:
    """Tests for ActionResult model."""

    def test_action_result_success(self) -> None:
        """Test successful action result."""
        result = ActionResult(
            action=DriftAction.LOG,
            success=True,
            message="Logged drift event",
        )
        assert result.success is True
        assert result.action == DriftAction.LOG

    def test_action_result_failure(self) -> None:
        """Test failed action result."""
        result = ActionResult(
            action=DriftAction.PAUSE_AGENT,
            success=False,
            message="Failed to pause agent",
            error="Agent not found",
        )
        assert result.success is False
        assert result.error == "Agent not found"


# ============================================================================
# DriftActionHandler Tests
# ============================================================================


class TestDriftActionHandler:
    """Tests for DriftActionHandler class."""

    @pytest.fixture
    def action_handler(self) -> DriftActionHandler:
        """Create DriftActionHandler instance."""
        alert_config = AlertConfig(
            slack_webhook_url="https://hooks.slack.com/test",
            linear_api_key="lin_api_test",
            linear_team_id="team-test",
        )
        return DriftActionHandler(alert_config=alert_config)

    @pytest.fixture
    def sample_drift_metric(self) -> DriftMetric:
        """Create a sample drift metric."""
        return DriftMetric(
            metric_type=MetricType.STEP_COUNT,
            metric_name="reasoning_steps",
            task_type="coding",
            baseline=20.0,
            current=45.0,
            deviation_pct=125.0,
            severity=DriftSeverity.CRITICAL,
            recommended_actions=[DriftAction.PAUSE_AGENT, DriftAction.ESCALATE_TO_HUMAN],
        )

    @pytest.mark.asyncio
    async def test_handle_log_action(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test LOG action writes to logs."""
        with patch("logging.Logger.warning") as mock_log:
            result = await action_handler.handle_log(sample_drift_metric)
            assert result.success is True
            assert result.action == DriftAction.LOG

    @pytest.mark.asyncio
    async def test_handle_alert_action(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test ALERT action sends notification."""
        with patch.object(
            action_handler._alert_sender,
            "send_slack_alert",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = AlertResult(
                channel=AlertChannel.SLACK, success=True, message="Sent"
            )
            result = await action_handler.handle_alert(sample_drift_metric)
            assert result.success is True
            assert result.action == DriftAction.ALERT

    @pytest.mark.asyncio
    async def test_handle_pause_agent_action(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test PAUSE_AGENT action stops agent execution."""
        # Mock the agent pause mechanism
        mock_pause_callback = AsyncMock()
        action_handler.register_pause_callback(mock_pause_callback)

        result = await action_handler.handle_pause_agent(
            sample_drift_metric, agent_id="agent-123"
        )
        assert result.success is True
        assert result.action == DriftAction.PAUSE_AGENT
        mock_pause_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_force_compaction_action(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test FORCE_COMPACTION action triggers context compaction."""
        mock_compact_callback = AsyncMock()
        action_handler.register_compaction_callback(mock_compact_callback)

        result = await action_handler.handle_force_compaction(
            sample_drift_metric, conversation_id="conv-456"
        )
        assert result.success is True
        assert result.action == DriftAction.FORCE_COMPACTION
        mock_compact_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_budget_alert_action(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test BUDGET_ALERT action sends budget notification."""
        with patch.object(
            action_handler._alert_sender,
            "send_to_all_channels",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = [
                AlertResult(channel=AlertChannel.SLACK, success=True, message="Sent")
            ]
            result = await action_handler.handle_budget_alert(sample_drift_metric)
            assert result.success is True
            assert result.action == DriftAction.BUDGET_ALERT

    @pytest.mark.asyncio
    async def test_handle_escalate_to_human_action(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test ESCALATE_TO_HUMAN action creates Linear ticket."""
        with patch.object(
            action_handler._alert_sender,
            "send_linear_alert",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = AlertResult(
                channel=AlertChannel.LINEAR, success=True, message="Ticket created"
            )
            result = await action_handler.handle_escalate(sample_drift_metric)
            assert result.success is True
            assert result.action == DriftAction.ESCALATE_TO_HUMAN

    @pytest.mark.asyncio
    async def test_execute_action_dispatches_correctly(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test execute_action routes to correct handler."""
        with patch.object(
            action_handler, "handle_log", new_callable=AsyncMock
        ) as mock_log:
            mock_log.return_value = ActionResult(
                action=DriftAction.LOG, success=True, message="Logged"
            )
            result = await action_handler.execute_action(
                DriftAction.LOG, sample_drift_metric
            )
            assert result.action == DriftAction.LOG
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_multiple_actions(
        self, action_handler: DriftActionHandler, sample_drift_metric: DriftMetric
    ) -> None:
        """Test executing multiple actions in sequence."""
        with patch.object(
            action_handler, "handle_log", new_callable=AsyncMock
        ) as mock_log:
            mock_log.return_value = ActionResult(
                action=DriftAction.LOG, success=True, message="Logged"
            )
            with patch.object(
                action_handler, "handle_alert", new_callable=AsyncMock
            ) as mock_alert:
                mock_alert.return_value = ActionResult(
                    action=DriftAction.ALERT, success=True, message="Alerted"
                )
                results = await action_handler.execute_actions(
                    [DriftAction.LOG, DriftAction.ALERT],
                    sample_drift_metric,
                )
                assert len(results) == 2
                assert all(r.success for r in results)


# ============================================================================
# SeverityActionMapping Tests
# ============================================================================


class TestSeverityActionMapping:
    """Tests for severity-to-action mapping."""

    def test_normal_severity_actions(self) -> None:
        """Test NORMAL severity maps to LOG only."""
        mapping = SeverityActionMapping()
        actions = mapping.get_actions(DriftSeverity.NORMAL)
        assert DriftAction.LOG in actions
        assert DriftAction.ALERT not in actions
        assert DriftAction.PAUSE_AGENT not in actions

    def test_warning_severity_actions(self) -> None:
        """Test WARNING severity maps to LOG + ALERT."""
        mapping = SeverityActionMapping()
        actions = mapping.get_actions(DriftSeverity.WARNING)
        assert DriftAction.LOG in actions
        assert DriftAction.ALERT in actions
        assert DriftAction.PAUSE_AGENT not in actions

    def test_critical_severity_actions(self) -> None:
        """Test CRITICAL severity maps to PAUSE_AGENT + LINEAR ticket."""
        mapping = SeverityActionMapping()
        actions = mapping.get_actions(DriftSeverity.CRITICAL)
        assert DriftAction.PAUSE_AGENT in actions
        assert DriftAction.ESCALATE_TO_HUMAN in actions

    def test_emergency_severity_actions(self) -> None:
        """Test EMERGENCY severity triggers all channels + human escalation."""
        mapping = SeverityActionMapping()
        actions = mapping.get_actions(DriftSeverity.EMERGENCY)
        assert DriftAction.PAUSE_AGENT in actions
        assert DriftAction.ESCALATE_TO_HUMAN in actions
        assert DriftAction.ALERT in actions

    def test_custom_severity_mapping(self) -> None:
        """Test custom severity-to-action mapping."""
        custom_mapping = {
            DriftSeverity.WARNING: [DriftAction.BUDGET_ALERT],
            DriftSeverity.CRITICAL: [DriftAction.FORCE_COMPACTION],
        }
        mapping = SeverityActionMapping(custom_mapping=custom_mapping)
        assert DriftAction.BUDGET_ALERT in mapping.get_actions(DriftSeverity.WARNING)


# ============================================================================
# DriftAlertSystem Tests
# ============================================================================


class TestDriftAlertSystem:
    """Tests for DriftAlertSystem integrated alerting."""

    @pytest.fixture
    def alert_system(self) -> DriftAlertSystem:
        """Create DriftAlertSystem instance."""
        alert_config = AlertConfig(
            slack_webhook_url="https://hooks.slack.com/test",
            linear_api_key="lin_api_test",
            linear_team_id="team-test",
        )
        detector = DriftDetector()
        detector.record_baseline(
            task_type="coding",
            tool_usage_count=10.0,
            step_count=20.0,
            context_tokens=50000.0,
            retry_count=1.0,
            token_cost_usd=0.10,
        )
        return DriftAlertSystem(
            detector=detector,
            alert_config=alert_config,
        )

    @pytest.fixture
    def task_metrics_warning(self) -> TaskMetrics:
        """Create TaskMetrics that trigger WARNING severity."""
        return TaskMetrics(
            task_id="TEST-001",
            task_type="coding",
            tool_usage_count=16,  # 60% increase -> WARNING
            step_count=22,
            context_tokens=50000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.11,
        )

    @pytest.fixture
    def task_metrics_critical(self) -> TaskMetrics:
        """Create TaskMetrics that trigger CRITICAL severity."""
        return TaskMetrics(
            task_id="TEST-002",
            task_type="coding",
            tool_usage_count=10,
            step_count=45,  # 125% increase -> CRITICAL
            context_tokens=50000,
            context_window_size=128000,
            retry_count=1,
            token_cost_usd=0.10,
        )

    @pytest.mark.asyncio
    async def test_evaluate_and_alert_warning(
        self,
        alert_system: DriftAlertSystem,
        task_metrics_warning: TaskMetrics,
    ) -> None:
        """Test evaluating metrics and sending warning alerts."""
        with patch.object(
            alert_system._action_handler,
            "execute_actions",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = [
                ActionResult(action=DriftAction.LOG, success=True, message="OK")
            ]
            results = await alert_system.evaluate_and_alert(task_metrics_warning)
            assert results.max_severity == DriftSeverity.WARNING
            mock_execute.assert_called()

    @pytest.mark.asyncio
    async def test_evaluate_and_alert_critical(
        self,
        alert_system: DriftAlertSystem,
        task_metrics_critical: TaskMetrics,
    ) -> None:
        """Test evaluating metrics and handling critical drift."""
        with patch.object(
            alert_system._action_handler,
            "execute_actions",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = [
                ActionResult(action=DriftAction.PAUSE_AGENT, success=True, message="OK")
            ]
            results = await alert_system.evaluate_and_alert(task_metrics_critical)
            assert results.max_severity == DriftSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_alert_system_respects_severity_mapping(
        self,
        alert_system: DriftAlertSystem,
        task_metrics_critical: TaskMetrics,
    ) -> None:
        """Test that alert system uses severity mapping for actions."""
        with patch.object(
            alert_system._action_handler,
            "execute_actions",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = []
            await alert_system.evaluate_and_alert(task_metrics_critical)
            # Verify CRITICAL severity triggers PAUSE_AGENT action
            called_actions = mock_execute.call_args_list[0][0][0]
            assert DriftAction.PAUSE_AGENT in called_actions

    def test_alert_system_integration_with_detector(
        self, alert_system: DriftAlertSystem
    ) -> None:
        """Test alert system integrates with DriftDetector."""
        assert alert_system._detector is not None
        # Verify detector has baselines
        assert "coding" in alert_system._detector.baselines


# ============================================================================
# WeeklyReportGenerator Tests
# ============================================================================


class TestWeeklyReportGenerator:
    """Tests for WeeklyReportGenerator."""

    @pytest.fixture
    def report_generator(self) -> WeeklyReportGenerator:
        """Create WeeklyReportGenerator instance."""
        return WeeklyReportGenerator()

    @pytest.fixture
    def sample_drift_events(self) -> list[DriftMetric]:
        """Create sample drift events for reporting."""
        return [
            DriftMetric(
                metric_type=MetricType.TOOL_USAGE,
                metric_name="tool_calls",
                task_type="coding",
                baseline=10.0,
                current=16.0,
                deviation_pct=60.0,
                severity=DriftSeverity.WARNING,
                recommended_actions=[DriftAction.LOG],
            ),
            DriftMetric(
                metric_type=MetricType.STEP_COUNT,
                metric_name="reasoning_steps",
                task_type="coding",
                baseline=20.0,
                current=45.0,
                deviation_pct=125.0,
                severity=DriftSeverity.CRITICAL,
                recommended_actions=[DriftAction.PAUSE_AGENT],
            ),
            DriftMetric(
                metric_type=MetricType.TOKEN_COST,
                metric_name="token_cost",
                task_type="planning",
                baseline=0.10,
                current=0.35,
                deviation_pct=250.0,
                severity=DriftSeverity.WARNING,
                recommended_actions=[DriftAction.BUDGET_ALERT],
            ),
        ]

    def test_add_drift_event(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test adding drift events to report."""
        for event in sample_drift_events:
            report_generator.add_event(event)
        assert report_generator.event_count == 3

    def test_generate_summary(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test generating summary report."""
        for event in sample_drift_events:
            report_generator.add_event(event)

        summary = report_generator.generate_summary()
        assert summary.total_events == 3
        assert summary.warning_count == 2
        assert summary.critical_count == 1
        assert summary.emergency_count == 0

    def test_generate_report_by_task_type(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test report breakdown by task type."""
        for event in sample_drift_events:
            report_generator.add_event(event)

        report = report_generator.generate_report()
        assert "coding" in report.by_task_type
        assert "planning" in report.by_task_type
        assert report.by_task_type["coding"]["event_count"] == 2

    def test_generate_report_by_metric_type(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test report breakdown by metric type."""
        for event in sample_drift_events:
            report_generator.add_event(event)

        report = report_generator.generate_report()
        assert MetricType.TOOL_USAGE in report.by_metric_type
        assert MetricType.STEP_COUNT in report.by_metric_type

    def test_generate_report_trends(
        self,
        report_generator: WeeklyReportGenerator,
    ) -> None:
        """Test trend analysis in weekly report."""
        # Add events over time
        base_time = datetime.now(UTC) - timedelta(days=7)
        for i in range(7):
            event = DriftMetric(
                metric_type=MetricType.TOOL_USAGE,
                metric_name="tool_calls",
                task_type="coding",
                baseline=10.0,
                current=10.0 + (i * 2),  # Increasing drift
                severity=DriftSeverity.WARNING if i > 3 else DriftSeverity.NORMAL,
                recommended_actions=[],
                timestamp=base_time + timedelta(days=i),
            )
            report_generator.add_event(event)

        report = report_generator.generate_report()
        assert report.trends is not None
        assert "tool_usage_trend" in report.trends

    def test_clear_events(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test clearing events after report generation."""
        for event in sample_drift_events:
            report_generator.add_event(event)

        report_generator.clear()
        assert report_generator.event_count == 0

    def test_format_report_as_markdown(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test formatting report as markdown."""
        for event in sample_drift_events:
            report_generator.add_event(event)

        markdown = report_generator.format_as_markdown()
        assert "# Weekly Drift Report" in markdown
        assert "## Summary" in markdown
        assert "WARNING" in markdown
        assert "CRITICAL" in markdown

    def test_format_report_as_json(
        self,
        report_generator: WeeklyReportGenerator,
        sample_drift_events: list[DriftMetric],
    ) -> None:
        """Test formatting report as JSON."""
        for event in sample_drift_events:
            report_generator.add_event(event)

        json_data = report_generator.format_as_json()
        assert "total_events" in json_data
        assert "by_severity" in json_data
