"""
Drift Action Handler module for DAW Agent Workbench.

This module provides:
- ActionResult: Model for action execution results
- DriftActionHandler: Class for executing actions based on drift severity

Actions include:
- LOG: Write drift event to logs
- ALERT: Send notification to monitoring
- PAUSE_AGENT: Stop agent execution
- FORCE_COMPACTION: Trigger context compaction
- BUDGET_ALERT: Send budget notification
- ESCALATE_TO_HUMAN: Create human review ticket

Based on DRIFT-002 requirements and FR-05.1 in PRD.
See: docs/planning/prd/02_functional_requirements.md
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from daw_agents.ops.alerts import (
    AlertConfig,
    AlertSender,
)
from daw_agents.ops.drift_detector import DriftAction, DriftMetric

logger = logging.getLogger(__name__)


class ActionResult(BaseModel):
    """Result of a drift action execution.

    Attributes:
        action: The action that was executed
        success: Whether the action completed successfully
        message: Human-readable result message
        error: Optional error details if action failed
        timestamp: When the action was executed
        metadata: Optional additional metadata
    """

    action: DriftAction
    success: bool
    message: str
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


# Type alias for callback functions
PauseCallback = Callable[[str, DriftMetric], Awaitable[bool]]
CompactionCallback = Callable[[str, DriftMetric], Awaitable[bool]]


class DriftActionHandler:
    """Handles execution of drift-triggered actions.

    Provides methods for each action type:
    - handle_log(): Write to logs
    - handle_alert(): Send Slack notification
    - handle_pause_agent(): Stop agent execution
    - handle_force_compaction(): Trigger context compaction
    - handle_budget_alert(): Send budget notification
    - handle_escalate(): Create Linear ticket

    Usage:
        handler = DriftActionHandler(alert_config=config)

        # Register callbacks for agent control
        handler.register_pause_callback(my_pause_fn)
        handler.register_compaction_callback(my_compact_fn)

        # Execute single action
        result = await handler.execute_action(DriftAction.LOG, drift_metric)

        # Execute multiple actions
        results = await handler.execute_actions(
            [DriftAction.LOG, DriftAction.ALERT],
            drift_metric
        )
    """

    def __init__(self, alert_config: AlertConfig) -> None:
        """Initialize DriftActionHandler.

        Args:
            alert_config: Configuration for alert delivery
        """
        self._alert_config = alert_config
        self._alert_sender = AlertSender(alert_config)
        self._pause_callback: PauseCallback | None = None
        self._compaction_callback: CompactionCallback | None = None

    def register_pause_callback(self, callback: PauseCallback) -> None:
        """Register callback for pausing agents.

        The callback receives (agent_id, drift_metric) and should return
        True if the agent was successfully paused.

        Args:
            callback: Async function to pause an agent
        """
        self._pause_callback = callback

    def register_compaction_callback(self, callback: CompactionCallback) -> None:
        """Register callback for triggering context compaction.

        The callback receives (conversation_id, drift_metric) and should
        return True if compaction was triggered successfully.

        Args:
            callback: Async function to trigger compaction
        """
        self._compaction_callback = callback

    async def handle_log(self, drift_metric: DriftMetric) -> ActionResult:
        """Log drift event.

        Writes drift details to the application log at WARNING level.

        Args:
            drift_metric: The drift metric to log

        Returns:
            ActionResult indicating success
        """
        log_message = (
            f"Drift detected: {drift_metric.metric_name} "
            f"({drift_metric.task_type}) - "
            f"baseline={drift_metric.baseline}, "
            f"current={drift_metric.current}, "
            f"deviation={drift_metric.deviation_pct:.1f}%, "
            f"severity={drift_metric.severity.name}"
        )

        if drift_metric.severity.value >= 2:  # CRITICAL or higher
            logger.error(log_message)
        else:
            logger.warning(log_message)

        return ActionResult(
            action=DriftAction.LOG,
            success=True,
            message=f"Logged drift event: {drift_metric.metric_name}",
        )

    async def handle_alert(self, drift_metric: DriftMetric) -> ActionResult:
        """Send alert notification.

        Sends Slack notification for drift event.

        Args:
            drift_metric: The drift metric triggering the alert

        Returns:
            ActionResult indicating success or failure
        """
        title = f"Drift Detected: {drift_metric.metric_name}"
        message = (
            f"Deviation: {drift_metric.deviation_pct:.1f}% "
            f"(baseline: {drift_metric.baseline}, current: {drift_metric.current})"
        )

        result = await self._alert_sender.send_slack_alert(
            drift_metric=drift_metric,
            title=title,
            message=message,
        )

        return ActionResult(
            action=DriftAction.ALERT,
            success=result.success,
            message=result.message,
            error=result.error_code,
        )

    async def handle_pause_agent(
        self,
        drift_metric: DriftMetric,
        agent_id: str | None = None,
    ) -> ActionResult:
        """Pause agent execution.

        Calls the registered pause callback to stop the agent.

        Args:
            drift_metric: The drift metric triggering the pause
            agent_id: ID of the agent to pause

        Returns:
            ActionResult indicating success or failure
        """
        if not self._pause_callback:
            logger.warning("No pause callback registered, agent pause skipped")
            return ActionResult(
                action=DriftAction.PAUSE_AGENT,
                success=False,
                message="No pause callback registered",
                error="NO_CALLBACK",
            )

        if not agent_id:
            return ActionResult(
                action=DriftAction.PAUSE_AGENT,
                success=False,
                message="Agent ID required for pause action",
                error="NO_AGENT_ID",
            )

        try:
            success = await self._pause_callback(agent_id, drift_metric)
            return ActionResult(
                action=DriftAction.PAUSE_AGENT,
                success=success,
                message=f"Agent {agent_id} paused successfully" if success else "Failed to pause agent",
                metadata={"agent_id": agent_id},
            )
        except Exception as e:
            logger.exception("Error pausing agent")
            return ActionResult(
                action=DriftAction.PAUSE_AGENT,
                success=False,
                message=f"Error pausing agent: {e!s}",
                error="PAUSE_ERROR",
            )

    async def handle_force_compaction(
        self,
        drift_metric: DriftMetric,
        conversation_id: str | None = None,
    ) -> ActionResult:
        """Trigger context compaction.

        Calls the registered compaction callback to reduce context size.

        Args:
            drift_metric: The drift metric triggering compaction
            conversation_id: ID of the conversation to compact

        Returns:
            ActionResult indicating success or failure
        """
        if not self._compaction_callback:
            logger.warning("No compaction callback registered, compaction skipped")
            return ActionResult(
                action=DriftAction.FORCE_COMPACTION,
                success=False,
                message="No compaction callback registered",
                error="NO_CALLBACK",
            )

        if not conversation_id:
            return ActionResult(
                action=DriftAction.FORCE_COMPACTION,
                success=False,
                message="Conversation ID required for compaction",
                error="NO_CONVERSATION_ID",
            )

        try:
            success = await self._compaction_callback(conversation_id, drift_metric)
            return ActionResult(
                action=DriftAction.FORCE_COMPACTION,
                success=success,
                message=(
                    f"Context compaction triggered for {conversation_id}"
                    if success
                    else "Failed to trigger compaction"
                ),
                metadata={"conversation_id": conversation_id},
            )
        except Exception as e:
            logger.exception("Error triggering compaction")
            return ActionResult(
                action=DriftAction.FORCE_COMPACTION,
                success=False,
                message=f"Error triggering compaction: {e!s}",
                error="COMPACTION_ERROR",
            )

    async def handle_budget_alert(self, drift_metric: DriftMetric) -> ActionResult:
        """Send budget alert notification.

        Sends notification to all configured channels about cost overrun.

        Args:
            drift_metric: The drift metric triggering the budget alert

        Returns:
            ActionResult indicating success or failure
        """
        title = "Budget Alert: Token Cost Increase"
        message = (
            f"Token costs have increased by {drift_metric.deviation_pct:.1f}%. "
            f"Baseline: ${drift_metric.baseline:.4f}, Current: ${drift_metric.current:.4f}"
        )

        results = await self._alert_sender.send_to_all_channels(
            drift_metric=drift_metric,
            title=title,
            message=message,
        )

        # Success if at least one channel succeeded
        any_success = any(r.success for r in results)
        success_count = sum(1 for r in results if r.success)

        return ActionResult(
            action=DriftAction.BUDGET_ALERT,
            success=any_success,
            message=f"Budget alert sent to {success_count}/{len(results)} channels",
            metadata={
                "channels_attempted": len(results),
                "channels_succeeded": success_count,
            },
        )

    async def handle_escalate(self, drift_metric: DriftMetric) -> ActionResult:
        """Escalate to human reviewer.

        Creates Linear issue for human investigation.

        Args:
            drift_metric: The drift metric triggering escalation

        Returns:
            ActionResult indicating success or failure
        """
        title = f"[ESCALATION] Critical Drift: {drift_metric.metric_name}"
        description = (
            f"Agent drift has been detected that requires human intervention.\n\n"
            f"**Severity**: {drift_metric.severity.name}\n"
            f"**Deviation**: {drift_metric.deviation_pct:.1f}%\n\n"
            f"Please investigate and take appropriate action."
        )

        result = await self._alert_sender.send_linear_alert(
            drift_metric=drift_metric,
            title=title,
            description=description,
        )

        return ActionResult(
            action=DriftAction.ESCALATE_TO_HUMAN,
            success=result.success,
            message=result.message,
            error=result.error_code,
        )

    async def execute_action(
        self,
        action: DriftAction,
        drift_metric: DriftMetric,
        agent_id: str | None = None,
        conversation_id: str | None = None,
    ) -> ActionResult:
        """Execute a single drift action.

        Dispatches to the appropriate handler based on action type.

        Args:
            action: The action to execute
            drift_metric: The drift metric triggering the action
            agent_id: Optional agent ID for pause actions
            conversation_id: Optional conversation ID for compaction

        Returns:
            ActionResult from the handler
        """
        handlers = {
            DriftAction.LOG: lambda: self.handle_log(drift_metric),
            DriftAction.ALERT: lambda: self.handle_alert(drift_metric),
            DriftAction.PAUSE_AGENT: lambda: self.handle_pause_agent(
                drift_metric, agent_id
            ),
            DriftAction.FORCE_COMPACTION: lambda: self.handle_force_compaction(
                drift_metric, conversation_id
            ),
            DriftAction.BUDGET_ALERT: lambda: self.handle_budget_alert(drift_metric),
            DriftAction.ESCALATE_TO_HUMAN: lambda: self.handle_escalate(drift_metric),
        }

        handler = handlers.get(action)
        if not handler:
            return ActionResult(
                action=action,
                success=False,
                message=f"Unknown action: {action.name}",
                error="UNKNOWN_ACTION",
            )

        return await handler()

    async def execute_actions(
        self,
        actions: list[DriftAction],
        drift_metric: DriftMetric,
        agent_id: str | None = None,
        conversation_id: str | None = None,
    ) -> list[ActionResult]:
        """Execute multiple drift actions in sequence.

        Args:
            actions: List of actions to execute
            drift_metric: The drift metric triggering the actions
            agent_id: Optional agent ID for pause actions
            conversation_id: Optional conversation ID for compaction

        Returns:
            List of ActionResult from each handler
        """
        results: list[ActionResult] = []

        for action in actions:
            result = await self.execute_action(
                action=action,
                drift_metric=drift_metric,
                agent_id=agent_id,
                conversation_id=conversation_id,
            )
            results.append(result)

        return results
