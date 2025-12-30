"""
Drift Detection Alerting module for DAW Agent Workbench.

This module provides:
- AlertChannel: Enum for delivery channels (SLACK, LINEAR, EMAIL, WEBHOOK)
- AlertConfig: Pydantic model for alert configuration
- AlertResult: Model for alert delivery results
- AlertSender: Class for sending alerts to various channels
- SeverityActionMapping: Maps drift severity to recommended actions
- DriftAlertSystem: Integrated alerting system with DriftDetector
- WeeklyReportGenerator: Generates weekly drift reports

Based on DRIFT-002 requirements and FR-05.1 in PRD:
- Integrate with observability stack (Helicone, Datadog)
- Slack/Linear notifications for drift detection
- Weekly drift report generation
- Severity-to-action mapping

See: docs/planning/prd/02_functional_requirements.md
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from daw_agents.ops.drift_detector import (
    DriftAction,
    DriftDetector,
    DriftMetric,
    DriftSeverity,
    MetricType,
    TaskMetrics,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AlertChannel(IntEnum):
    """Delivery channels for drift alerts.

    Channels are ordered by typical urgency/formality:
    - SLACK: Real-time team notifications
    - LINEAR: Issue tracking for follow-up
    - EMAIL: Formal notifications
    - WEBHOOK: Custom integrations
    """

    SLACK = auto()
    LINEAR = auto()
    EMAIL = auto()
    WEBHOOK = auto()


class AlertConfig(BaseModel):
    """Configuration for alert delivery channels.

    Stores credentials and settings for each alert channel.
    Use from_env() to load from environment variables.

    Attributes:
        slack_webhook_url: Slack incoming webhook URL
        slack_channel: Slack channel for alerts (e.g., #alerts)
        linear_api_key: Linear API key for issue creation
        linear_team_id: Linear team ID for issue assignment
        email_recipients: List of email addresses for alerts
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port (default: 587)
        smtp_username: SMTP authentication username
        smtp_password: SMTP authentication password
        webhook_url: Custom webhook URL
        webhook_headers: Custom headers for webhook requests
    """

    # Slack configuration
    slack_webhook_url: str | None = None
    slack_channel: str | None = None

    # Linear configuration
    linear_api_key: str | None = None
    linear_team_id: str | None = None

    # Email configuration
    email_recipients: list[str] = Field(default_factory=list)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None

    # Custom webhook configuration
    webhook_url: str | None = None
    webhook_headers: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_env(cls) -> AlertConfig:
        """Load configuration from environment variables.

        Reads:
        - SLACK_WEBHOOK_URL, SLACK_CHANNEL
        - LINEAR_API_KEY, LINEAR_TEAM_ID
        - ALERT_EMAIL_RECIPIENTS (comma-separated)
        - SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
        - ALERT_WEBHOOK_URL

        Returns:
            AlertConfig instance loaded from environment
        """
        email_recipients_str = os.environ.get("ALERT_EMAIL_RECIPIENTS", "")
        email_recipients = (
            [e.strip() for e in email_recipients_str.split(",") if e.strip()]
            if email_recipients_str
            else []
        )

        return cls(
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
            slack_channel=os.environ.get("SLACK_CHANNEL"),
            linear_api_key=os.environ.get("LINEAR_API_KEY"),
            linear_team_id=os.environ.get("LINEAR_TEAM_ID"),
            email_recipients=email_recipients,
            smtp_host=os.environ.get("SMTP_HOST"),
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_username=os.environ.get("SMTP_USERNAME"),
            smtp_password=os.environ.get("SMTP_PASSWORD"),
            webhook_url=os.environ.get("ALERT_WEBHOOK_URL"),
        )


class AlertResult(BaseModel):
    """Result of an alert delivery attempt.

    Attributes:
        channel: The channel the alert was sent to
        success: Whether the delivery was successful
        message: Human-readable result message
        error_code: Optional error code if delivery failed
        timestamp: When the delivery was attempted
    """

    channel: AlertChannel
    success: bool
    message: str
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AlertSender:
    """Sends alerts to configured channels.

    Supports:
    - Slack: Sends formatted messages via webhook
    - Linear: Creates issues for drift events
    - Email: Sends SMTP emails
    - Webhook: Posts JSON to custom endpoints

    Usage:
        config = AlertConfig(slack_webhook_url="...")
        sender = AlertSender(config=config)
        result = await sender.send_slack_alert(
            drift_metric=metric,
            title="Drift Detected",
            message="Tool usage increased by 60%"
        )
    """

    def __init__(self, config: AlertConfig) -> None:
        """Initialize AlertSender with configuration.

        Args:
            config: Alert channel configuration
        """
        self.config = config

    async def send_slack_alert(
        self,
        drift_metric: DriftMetric,
        title: str,
        message: str,
    ) -> AlertResult:
        """Send alert to Slack via webhook.

        Args:
            drift_metric: The drift metric triggering the alert
            title: Alert title
            message: Alert message body

        Returns:
            AlertResult indicating success or failure
        """
        try:
            import httpx

            if not self.config.slack_webhook_url:
                return AlertResult(
                    channel=AlertChannel.SLACK,
                    success=False,
                    message="Slack webhook URL not configured",
                    error_code="NO_CONFIG",
                )

            # Format Slack message with drift details
            payload = {
                "channel": self.config.slack_channel or "#alerts",
                "text": title,
                "attachments": [
                    {
                        "color": self._severity_to_color(drift_metric.severity),
                        "title": title,
                        "text": message,
                        "fields": [
                            {
                                "title": "Metric",
                                "value": drift_metric.metric_name,
                                "short": True,
                            },
                            {
                                "title": "Task Type",
                                "value": drift_metric.task_type,
                                "short": True,
                            },
                            {
                                "title": "Severity",
                                "value": drift_metric.severity.name,
                                "short": True,
                            },
                            {
                                "title": "Deviation",
                                "value": f"{drift_metric.deviation_pct:.1f}%",
                                "short": True,
                            },
                        ],
                        "footer": "DAW Drift Detection",
                        "ts": int(drift_metric.timestamp.timestamp()),
                    }
                ],
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.slack_webhook_url,
                    json=payload,
                    timeout=30.0,
                )

            if response.status_code == 200:
                return AlertResult(
                    channel=AlertChannel.SLACK,
                    success=True,
                    message="Alert sent to Slack successfully",
                )
            return AlertResult(
                channel=AlertChannel.SLACK,
                success=False,
                message=f"Slack API error: {response.status_code}",
                error_code=f"HTTP_{response.status_code}",
            )

        except Exception as e:
            logger.exception("Failed to send Slack alert")
            return AlertResult(
                channel=AlertChannel.SLACK,
                success=False,
                message=f"Error sending Slack alert: {e!s}",
                error_code="SLACK_ERROR",
            )

    async def send_linear_alert(
        self,
        drift_metric: DriftMetric,
        title: str,
        description: str,
    ) -> AlertResult:
        """Create Linear issue for drift alert.

        Args:
            drift_metric: The drift metric triggering the alert
            title: Issue title
            description: Issue description

        Returns:
            AlertResult indicating success or failure
        """
        try:
            import httpx

            if not self.config.linear_api_key or not self.config.linear_team_id:
                return AlertResult(
                    channel=AlertChannel.LINEAR,
                    success=False,
                    message="Linear API key or team ID not configured",
                    error_code="NO_CONFIG",
                )

            # Linear GraphQL mutation for creating issues
            mutation = """
            mutation IssueCreate($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue {
                        id
                        title
                        url
                    }
                }
            }
            """

            # Format description with drift details
            full_description = f"""{description}

## Drift Details
- **Metric**: {drift_metric.metric_name}
- **Task Type**: {drift_metric.task_type}
- **Baseline**: {drift_metric.baseline}
- **Current**: {drift_metric.current}
- **Deviation**: {drift_metric.deviation_pct:.1f}%
- **Severity**: {drift_metric.severity.name}
- **Timestamp**: {drift_metric.timestamp.isoformat()}

## Recommended Actions
{chr(10).join(f'- {action.name}' for action in drift_metric.recommended_actions)}
"""

            payload = {
                "query": mutation,
                "variables": {
                    "input": {
                        "teamId": self.config.linear_team_id,
                        "title": title,
                        "description": full_description,
                        "priority": self._severity_to_priority(drift_metric.severity),
                    }
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.linear.app/graphql",
                    json=payload,
                    headers={
                        "Authorization": self.config.linear_api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("issueCreate", {}).get("success"):
                    issue = data["data"]["issueCreate"]["issue"]
                    return AlertResult(
                        channel=AlertChannel.LINEAR,
                        success=True,
                        message=f"Linear issue created: {issue.get('id', 'unknown')}",
                    )

            return AlertResult(
                channel=AlertChannel.LINEAR,
                success=False,
                message=f"Linear API error: {response.status_code}",
                error_code=f"HTTP_{response.status_code}",
            )

        except Exception as e:
            logger.exception("Failed to create Linear issue")
            return AlertResult(
                channel=AlertChannel.LINEAR,
                success=False,
                message=f"Error creating Linear issue: {e!s}",
                error_code="LINEAR_ERROR",
            )

    async def send_email_alert(
        self,
        drift_metric: DriftMetric,
        subject: str,
        body: str,
    ) -> AlertResult:
        """Send email alert via SMTP.

        Args:
            drift_metric: The drift metric triggering the alert
            subject: Email subject
            body: Email body

        Returns:
            AlertResult indicating success or failure
        """
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            if not self.config.email_recipients or not self.config.smtp_host:
                return AlertResult(
                    channel=AlertChannel.EMAIL,
                    success=False,
                    message="Email recipients or SMTP host not configured",
                    error_code="NO_CONFIG",
                )

            # Create email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.smtp_username or "noreply@daw.example.com"
            msg["To"] = ", ".join(self.config.email_recipients)

            # Create HTML body with drift details
            html_body = f"""
<html>
<body>
<h2>{subject}</h2>
<p>{body}</p>
<h3>Drift Details</h3>
<table border="1" cellpadding="5">
<tr><th>Metric</th><td>{drift_metric.metric_name}</td></tr>
<tr><th>Task Type</th><td>{drift_metric.task_type}</td></tr>
<tr><th>Baseline</th><td>{drift_metric.baseline}</td></tr>
<tr><th>Current</th><td>{drift_metric.current}</td></tr>
<tr><th>Deviation</th><td>{drift_metric.deviation_pct:.1f}%</td></tr>
<tr><th>Severity</th><td>{drift_metric.severity.name}</td></tr>
</table>
<p><small>Generated by DAW Drift Detection at {drift_metric.timestamp.isoformat()}</small></p>
</body>
</html>
"""
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                username=self.config.smtp_username,
                password=self.config.smtp_password,
                start_tls=True,
            )

            return AlertResult(
                channel=AlertChannel.EMAIL,
                success=True,
                message=f"Email sent to {len(self.config.email_recipients)} recipients",
            )

        except Exception as e:
            logger.exception("Failed to send email alert")
            return AlertResult(
                channel=AlertChannel.EMAIL,
                success=False,
                message=f"Error sending email: {e!s}",
                error_code="EMAIL_ERROR",
            )

    async def send_webhook_alert(
        self,
        drift_metric: DriftMetric,
        payload: dict[str, Any] | None = None,
    ) -> AlertResult:
        """Send alert to custom webhook.

        Args:
            drift_metric: The drift metric triggering the alert
            payload: Optional custom payload (merged with drift data)

        Returns:
            AlertResult indicating success or failure
        """
        try:
            import httpx

            if not self.config.webhook_url:
                return AlertResult(
                    channel=AlertChannel.WEBHOOK,
                    success=False,
                    message="Webhook URL not configured",
                    error_code="NO_CONFIG",
                )

            # Build webhook payload
            webhook_payload = {
                "event": "drift_detected",
                "timestamp": drift_metric.timestamp.isoformat(),
                "drift_metric": {
                    "metric_type": drift_metric.metric_type.name,
                    "metric_name": drift_metric.metric_name,
                    "task_type": drift_metric.task_type,
                    "baseline": drift_metric.baseline,
                    "current": drift_metric.current,
                    "deviation_pct": drift_metric.deviation_pct,
                    "severity": drift_metric.severity.name,
                    "recommended_actions": [
                        a.name for a in drift_metric.recommended_actions
                    ],
                },
            }

            # Merge custom payload if provided
            if payload:
                webhook_payload.update(payload)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.webhook_url,
                    json=webhook_payload,
                    headers=self.config.webhook_headers,
                    timeout=30.0,
                )

            if response.status_code in (200, 201, 202, 204):
                return AlertResult(
                    channel=AlertChannel.WEBHOOK,
                    success=True,
                    message="Webhook delivered successfully",
                )

            return AlertResult(
                channel=AlertChannel.WEBHOOK,
                success=False,
                message=f"Webhook error: {response.status_code}",
                error_code=f"HTTP_{response.status_code}",
            )

        except Exception as e:
            logger.exception("Failed to send webhook alert")
            return AlertResult(
                channel=AlertChannel.WEBHOOK,
                success=False,
                message=f"Error sending webhook: {e!s}",
                error_code="WEBHOOK_ERROR",
            )

    async def send_to_all_channels(
        self,
        drift_metric: DriftMetric,
        title: str,
        message: str,
    ) -> list[AlertResult]:
        """Send alert to all configured channels.

        Args:
            drift_metric: The drift metric triggering the alert
            title: Alert title
            message: Alert message

        Returns:
            List of AlertResult for each channel
        """
        results: list[AlertResult] = []

        # Send to Slack
        if self.config.slack_webhook_url:
            results.append(
                await self.send_slack_alert(drift_metric, title, message)
            )

        # Create Linear issue
        if self.config.linear_api_key:
            results.append(
                await self.send_linear_alert(drift_metric, title, message)
            )

        # Send email
        if self.config.email_recipients:
            results.append(
                await self.send_email_alert(drift_metric, f"[DAW] {title}", message)
            )

        # Send to webhook
        if self.config.webhook_url:
            results.append(
                await self.send_webhook_alert(drift_metric)
            )

        return results

    def _severity_to_color(self, severity: DriftSeverity) -> str:
        """Convert severity to Slack color code."""
        colors = {
            DriftSeverity.NORMAL: "good",  # green
            DriftSeverity.WARNING: "warning",  # yellow
            DriftSeverity.CRITICAL: "danger",  # red
            DriftSeverity.EMERGENCY: "#8B0000",  # dark red
        }
        return colors.get(severity, "good")

    def _severity_to_priority(self, severity: DriftSeverity) -> int:
        """Convert severity to Linear priority (0=none, 1=urgent, 2=high, 3=normal, 4=low)."""
        priorities = {
            DriftSeverity.NORMAL: 4,  # low
            DriftSeverity.WARNING: 3,  # normal
            DriftSeverity.CRITICAL: 2,  # high
            DriftSeverity.EMERGENCY: 1,  # urgent
        }
        return priorities.get(severity, 3)


class SeverityActionMapping:
    """Maps drift severity levels to recommended actions.

    Default mapping (per FR-05.1):
    - NORMAL: log only
    - WARNING: log + Slack alert
    - CRITICAL: pause agent + Linear ticket
    - EMERGENCY: all channels + human escalation

    Usage:
        mapping = SeverityActionMapping()
        actions = mapping.get_actions(DriftSeverity.CRITICAL)
        # Returns [DriftAction.PAUSE_AGENT, DriftAction.ESCALATE_TO_HUMAN, ...]
    """

    DEFAULT_MAPPING: dict[DriftSeverity, list[DriftAction]] = {
        DriftSeverity.NORMAL: [DriftAction.LOG],
        DriftSeverity.WARNING: [DriftAction.LOG, DriftAction.ALERT],
        DriftSeverity.CRITICAL: [
            DriftAction.LOG,
            DriftAction.ALERT,
            DriftAction.PAUSE_AGENT,
            DriftAction.ESCALATE_TO_HUMAN,
        ],
        DriftSeverity.EMERGENCY: [
            DriftAction.LOG,
            DriftAction.ALERT,
            DriftAction.PAUSE_AGENT,
            DriftAction.ESCALATE_TO_HUMAN,
        ],
    }

    def __init__(
        self,
        custom_mapping: dict[DriftSeverity, list[DriftAction]] | None = None,
    ) -> None:
        """Initialize with optional custom mapping.

        Args:
            custom_mapping: Override default severity-to-action mapping
        """
        self._mapping = self.DEFAULT_MAPPING.copy()
        if custom_mapping:
            self._mapping.update(custom_mapping)

    def get_actions(self, severity: DriftSeverity) -> list[DriftAction]:
        """Get recommended actions for a severity level.

        Args:
            severity: The drift severity level

        Returns:
            List of recommended actions
        """
        return self._mapping.get(severity, [DriftAction.LOG])


@dataclass
class DriftAlertResults:
    """Results from drift evaluation and alerting.

    Attributes:
        drift_metrics: List of evaluated drift metrics
        max_severity: Highest severity detected
        actions_executed: Actions that were executed
        action_results: Results from action execution
    """

    drift_metrics: list[DriftMetric]
    max_severity: DriftSeverity
    actions_executed: list[DriftAction] = field(default_factory=list)
    action_results: list[Any] = field(default_factory=list)


class DriftAlertSystem:
    """Integrated drift detection and alerting system.

    Combines DriftDetector with AlertSender to provide:
    - Automatic drift evaluation
    - Severity-based action routing
    - Multi-channel alert delivery
    - Action execution

    Usage:
        detector = DriftDetector()
        detector.record_baseline(...)

        alert_config = AlertConfig(slack_webhook_url="...")
        system = DriftAlertSystem(detector, alert_config)

        results = await system.evaluate_and_alert(task_metrics)
    """

    def __init__(
        self,
        detector: DriftDetector,
        alert_config: AlertConfig,
        severity_mapping: SeverityActionMapping | None = None,
    ) -> None:
        """Initialize DriftAlertSystem.

        Args:
            detector: DriftDetector instance with baselines
            alert_config: Alert channel configuration
            severity_mapping: Optional custom severity-to-action mapping
        """
        self._detector = detector
        self._alert_config = alert_config
        self._severity_mapping = severity_mapping or SeverityActionMapping()
        self._alert_sender = AlertSender(alert_config)

        # Import here to avoid circular dependency
        from daw_agents.ops.actions import DriftActionHandler

        self._action_handler = DriftActionHandler(alert_config=alert_config)

    async def evaluate_and_alert(
        self,
        metrics: TaskMetrics,
        agent_id: str | None = None,
        conversation_id: str | None = None,
    ) -> DriftAlertResults:
        """Evaluate metrics and execute appropriate actions.

        Args:
            metrics: Task metrics to evaluate
            agent_id: Optional agent ID for pause actions
            conversation_id: Optional conversation ID for compaction

        Returns:
            DriftAlertResults with metrics, severity, and action results
        """
        # Evaluate drift metrics
        drift_metrics = self._detector.evaluate(metrics)
        max_severity = self._detector.get_max_severity(drift_metrics)

        # Get actions for max severity
        actions = self._severity_mapping.get_actions(max_severity)

        # Find the drift metric with the max severity for action context
        max_severity_metric = next(
            (m for m in drift_metrics if m.severity == max_severity),
            drift_metrics[0] if drift_metrics else None,
        )

        # Execute actions
        action_results: list[Any] = []
        if max_severity_metric and actions:
            action_results = await self._action_handler.execute_actions(
                actions,
                max_severity_metric,
                agent_id=agent_id,
                conversation_id=conversation_id,
            )

        return DriftAlertResults(
            drift_metrics=drift_metrics,
            max_severity=max_severity,
            actions_executed=actions,
            action_results=action_results,
        )


@dataclass
class ReportSummary:
    """Summary statistics for weekly report.

    Attributes:
        total_events: Total number of drift events
        normal_count: Count of NORMAL severity events
        warning_count: Count of WARNING severity events
        critical_count: Count of CRITICAL severity events
        emergency_count: Count of EMERGENCY severity events
    """

    total_events: int = 0
    normal_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    emergency_count: int = 0


@dataclass
class WeeklyReport:
    """Weekly drift report structure.

    Attributes:
        summary: Summary statistics
        by_task_type: Breakdown by task type
        by_metric_type: Breakdown by metric type
        trends: Trend analysis data
        period_start: Report period start
        period_end: Report period end
    """

    summary: ReportSummary
    by_task_type: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_metric_type: dict[MetricType, dict[str, Any]] = field(default_factory=dict)
    trends: dict[str, Any] = field(default_factory=dict)
    period_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = field(default_factory=lambda: datetime.now(UTC))


class WeeklyReportGenerator:
    """Generates weekly drift detection reports.

    Collects drift events and generates:
    - Summary statistics
    - Breakdown by task type
    - Breakdown by metric type
    - Trend analysis
    - Markdown/JSON formatted reports

    Usage:
        generator = WeeklyReportGenerator()
        generator.add_event(drift_metric)
        generator.add_event(another_metric)

        report = generator.generate_report()
        markdown = generator.format_as_markdown()
    """

    def __init__(self) -> None:
        """Initialize WeeklyReportGenerator."""
        self._events: list[DriftMetric] = []

    @property
    def event_count(self) -> int:
        """Get current event count."""
        return len(self._events)

    def add_event(self, event: DriftMetric) -> None:
        """Add a drift event to the report.

        Args:
            event: DriftMetric to add
        """
        self._events.append(event)

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    def generate_summary(self) -> ReportSummary:
        """Generate summary statistics.

        Returns:
            ReportSummary with counts by severity
        """
        summary = ReportSummary(total_events=len(self._events))

        for event in self._events:
            if event.severity == DriftSeverity.NORMAL:
                summary.normal_count += 1
            elif event.severity == DriftSeverity.WARNING:
                summary.warning_count += 1
            elif event.severity == DriftSeverity.CRITICAL:
                summary.critical_count += 1
            elif event.severity == DriftSeverity.EMERGENCY:
                summary.emergency_count += 1

        return summary

    def generate_report(self) -> WeeklyReport:
        """Generate full weekly report.

        Returns:
            WeeklyReport with all breakdowns and trends
        """
        summary = self.generate_summary()

        # Calculate period
        if self._events:
            timestamps = [e.timestamp for e in self._events]
            period_start = min(timestamps)
            period_end = max(timestamps)
        else:
            now = datetime.now(UTC)
            period_start = now - timedelta(days=7)
            period_end = now

        # Breakdown by task type
        by_task_type: dict[str, dict[str, Any]] = {}
        for event in self._events:
            if event.task_type not in by_task_type:
                by_task_type[event.task_type] = {
                    "event_count": 0,
                    "warning_count": 0,
                    "critical_count": 0,
                    "avg_deviation": 0.0,
                    "deviations": [],
                }
            by_task_type[event.task_type]["event_count"] += 1
            if event.severity == DriftSeverity.WARNING:
                by_task_type[event.task_type]["warning_count"] += 1
            elif event.severity == DriftSeverity.CRITICAL:
                by_task_type[event.task_type]["critical_count"] += 1
            if event.deviation_pct is not None:
                by_task_type[event.task_type]["deviations"].append(event.deviation_pct)

        # Calculate averages
        for task_type in by_task_type:
            deviations = by_task_type[task_type]["deviations"]
            if deviations:
                by_task_type[task_type]["avg_deviation"] = sum(deviations) / len(
                    deviations
                )
            del by_task_type[task_type]["deviations"]

        # Breakdown by metric type
        by_metric_type: dict[MetricType, dict[str, Any]] = {}
        for event in self._events:
            if event.metric_type not in by_metric_type:
                by_metric_type[event.metric_type] = {
                    "event_count": 0,
                    "max_deviation": 0.0,
                }
            by_metric_type[event.metric_type]["event_count"] += 1
            if event.deviation_pct is not None:
                current_max = by_metric_type[event.metric_type]["max_deviation"]
                by_metric_type[event.metric_type]["max_deviation"] = max(
                    current_max, event.deviation_pct
                )

        # Trend analysis
        trends = self._calculate_trends()

        return WeeklyReport(
            summary=summary,
            by_task_type=by_task_type,
            by_metric_type=by_metric_type,
            trends=trends,
            period_start=period_start,
            period_end=period_end,
        )

    def _calculate_trends(self) -> dict[str, Any]:
        """Calculate trend data for the week.

        Returns:
            Dictionary with trend analysis
        """
        if not self._events:
            return {}

        trends: dict[str, Any] = {}

        # Group events by day
        events_by_day: dict[str, list[DriftMetric]] = {}
        for event in self._events:
            day_key = event.timestamp.strftime("%Y-%m-%d")
            if day_key not in events_by_day:
                events_by_day[day_key] = []
            events_by_day[day_key].append(event)

        # Calculate daily trends
        daily_counts = [len(events) for events in events_by_day.values()]
        if len(daily_counts) >= 2:
            # Simple trend: compare last day to first day
            trend_direction = "increasing" if daily_counts[-1] > daily_counts[0] else (
                "decreasing" if daily_counts[-1] < daily_counts[0] else "stable"
            )
            trends["overall_trend"] = trend_direction
            trends["daily_event_counts"] = daily_counts

        # Tool usage trend
        tool_usage_events = [
            e for e in self._events if e.metric_type == MetricType.TOOL_USAGE
        ]
        if tool_usage_events:
            deviations = [
                e.deviation_pct for e in tool_usage_events if e.deviation_pct is not None
            ]
            if deviations:
                trends["tool_usage_trend"] = {
                    "count": len(tool_usage_events),
                    "avg_deviation": sum(deviations) / len(deviations),
                    "max_deviation": max(deviations),
                }

        return trends

    def format_as_markdown(self) -> str:
        """Format report as markdown.

        Returns:
            Markdown-formatted report string
        """
        report = self.generate_report()

        lines = [
            "# Weekly Drift Report",
            "",
            f"**Period**: {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}",
            "",
            "## Summary",
            "",
            f"- **Total Events**: {report.summary.total_events}",
            f"- **NORMAL**: {report.summary.normal_count}",
            f"- **WARNING**: {report.summary.warning_count}",
            f"- **CRITICAL**: {report.summary.critical_count}",
            f"- **EMERGENCY**: {report.summary.emergency_count}",
            "",
        ]

        # Task type breakdown
        if report.by_task_type:
            lines.append("## By Task Type")
            lines.append("")
            lines.append("| Task Type | Events | Warnings | Critical | Avg Deviation |")
            lines.append("|-----------|--------|----------|----------|---------------|")
            for task_type, data in report.by_task_type.items():
                lines.append(
                    f"| {task_type} | {data['event_count']} | "
                    f"{data['warning_count']} | {data['critical_count']} | "
                    f"{data['avg_deviation']:.1f}% |"
                )
            lines.append("")

        # Metric type breakdown
        if report.by_metric_type:
            lines.append("## By Metric Type")
            lines.append("")
            lines.append("| Metric | Events | Max Deviation |")
            lines.append("|--------|--------|---------------|")
            for metric_type, data in report.by_metric_type.items():
                lines.append(
                    f"| {metric_type.name} | {data['event_count']} | "
                    f"{data['max_deviation']:.1f}% |"
                )
            lines.append("")

        # Trends
        if report.trends:
            lines.append("## Trends")
            lines.append("")
            if "overall_trend" in report.trends:
                lines.append(f"- **Overall Trend**: {report.trends['overall_trend']}")
            if "tool_usage_trend" in report.trends:
                tut = report.trends["tool_usage_trend"]
                lines.append(
                    f"- **Tool Usage**: {tut['count']} events, "
                    f"avg {tut['avg_deviation']:.1f}% deviation"
                )
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated at {datetime.now(UTC).isoformat()}*")

        return "\n".join(lines)

    def format_as_json(self) -> dict[str, Any]:
        """Format report as JSON-serializable dictionary.

        Returns:
            Dictionary with report data
        """
        report = self.generate_report()

        return {
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_events": report.summary.total_events,
            "by_severity": {
                "normal": report.summary.normal_count,
                "warning": report.summary.warning_count,
                "critical": report.summary.critical_count,
                "emergency": report.summary.emergency_count,
            },
            "by_task_type": report.by_task_type,
            "by_metric_type": {
                k.name: v for k, v in report.by_metric_type.items()
            },
            "trends": report.trends,
        }
