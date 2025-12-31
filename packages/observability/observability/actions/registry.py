"""
Remediation Action Registry for the Observability System.

This module provides the ActionRegistry class that:
- Loads action definitions from YAML configuration
- Validates whether actions can be executed (cooldowns, max attempts)
- Supports dry-run mode for testing actions
- Tracks execution history for rate limiting

Part of OBS-010: Remediation Action Registry
See: docs/planning/epics/EPIC-13-OBSERVABILITY.md

Note: This registry does NOT execute actions - it only defines and validates them.
Actual execution is handled by OBS-011 (Self-Healing Executor).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import (
    ActionDefinition,
    ActionExecution,
    ActionRegistryConfig,
    ActionType,
    ApprovalLevel,
    DryRunResult,
    TriggerType,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Default config file location
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "actions.yaml"


class ActionRegistryError(Exception):
    """Base exception for action registry errors."""

    pass


class ActionNotFoundError(ActionRegistryError):
    """Raised when a requested action does not exist."""

    pass


class ConfigurationError(ActionRegistryError):
    """Raised when configuration is invalid."""

    pass


class ActionRegistry:
    """Registry for remediation actions.

    Loads action definitions from YAML configuration and provides methods
    to validate and prepare action executions. Does not execute actions directly.

    Usage:
        # Load from default config
        registry = ActionRegistry.from_yaml()

        # Or from custom path
        registry = ActionRegistry.from_yaml("/path/to/actions.yaml")

        # Check if action can be executed
        validation = registry.validate_action("restart_container", target="web-api")
        if validation.can_execute:
            # Proceed with execution (handled by OBS-011)
            pass

        # Dry-run to see what would happen
        dry_run = registry.dry_run("restart_container", target="web-api")
        print(dry_run.command)  # Shows rendered command

    Attributes:
        config: The loaded registry configuration
        actions: Dictionary of action definitions by name
    """

    def __init__(self, config: ActionRegistryConfig) -> None:
        """Initialize the registry with configuration.

        Args:
            config: The registry configuration containing action definitions
        """
        self._config = config
        self._actions: dict[str, ActionDefinition] = {
            action.name: action for action in config.actions
        }
        # Execution history: {action_name: {target: [ActionExecution]}}
        self._execution_history: dict[str, dict[str, list[ActionExecution]]] = defaultdict(
            lambda: defaultdict(list)
        )

    @property
    def config(self) -> ActionRegistryConfig:
        """Get the registry configuration."""
        return self._config

    @property
    def actions(self) -> dict[str, ActionDefinition]:
        """Get all registered actions."""
        return self._actions.copy()

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "ActionRegistry":
        """Load registry from YAML configuration file.

        Args:
            path: Path to YAML config file. Uses default if not provided.

        Returns:
            Initialized ActionRegistry instance

        Raises:
            ConfigurationError: If the file cannot be read or parsed
        """
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH

        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, using empty registry")
            return cls(ActionRegistryConfig())

        try:
            with open(config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            if raw_config is None:
                raw_config = {}

            # Parse and validate configuration
            config = cls._parse_config(raw_config)
            logger.info(f"Loaded {len(config.actions)} actions from {config_path}")
            return cls(config)

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in config file: {e}")
        except ValidationError as e:
            raise ConfigurationError(f"Invalid configuration: {e}")
        except OSError as e:
            raise ConfigurationError(f"Cannot read config file: {e}")

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "ActionRegistry":
        """Load registry from a dictionary.

        Args:
            config_dict: Dictionary containing registry configuration

        Returns:
            Initialized ActionRegistry instance

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        try:
            config = cls._parse_config(config_dict)
            return cls(config)
        except ValidationError as e:
            raise ConfigurationError(f"Invalid configuration: {e}")

    @staticmethod
    def _parse_config(raw_config: dict[str, Any]) -> ActionRegistryConfig:
        """Parse raw configuration dict into ActionRegistryConfig.

        Args:
            raw_config: Raw dictionary from YAML or other source

        Returns:
            Validated ActionRegistryConfig
        """
        # Convert action definitions if present
        if "actions" in raw_config:
            actions = []
            for action_dict in raw_config["actions"]:
                # Convert string enum values
                if "action_type" in action_dict and isinstance(action_dict["action_type"], str):
                    action_dict["action_type"] = ActionType(action_dict["action_type"])
                if "trigger" in action_dict and isinstance(action_dict["trigger"], str):
                    action_dict["trigger"] = TriggerType(action_dict["trigger"])
                if "requires_approval" in action_dict and isinstance(
                    action_dict["requires_approval"], str
                ):
                    action_dict["requires_approval"] = ApprovalLevel(action_dict["requires_approval"])
                elif "requires_approval" in action_dict and isinstance(
                    action_dict["requires_approval"], bool
                ):
                    # Handle legacy boolean format
                    action_dict["requires_approval"] = (
                        ApprovalLevel.REQUIRE if action_dict["requires_approval"] else ApprovalLevel.NONE
                    )

                actions.append(ActionDefinition(**action_dict))
            raw_config["actions"] = actions

        return ActionRegistryConfig(**raw_config)

    def get_action(self, name: str) -> ActionDefinition:
        """Get an action definition by name.

        Args:
            name: The action name

        Returns:
            The ActionDefinition

        Raises:
            ActionNotFoundError: If the action does not exist
        """
        action = self._actions.get(name.lower())
        if action is None:
            raise ActionNotFoundError(f"Action '{name}' not found in registry")
        return action

    def list_actions(
        self,
        *,
        action_type: ActionType | None = None,
        trigger: TriggerType | None = None,
        enabled_only: bool = True,
        tags: list[str] | None = None,
    ) -> list[ActionDefinition]:
        """List actions matching the given filters.

        Args:
            action_type: Filter by action type
            trigger: Filter by trigger type
            enabled_only: Only return enabled actions
            tags: Filter by tags (actions must have at least one matching tag)

        Returns:
            List of matching ActionDefinition objects
        """
        results = list(self._actions.values())

        if enabled_only:
            results = [a for a in results if a.enabled]

        if action_type is not None:
            results = [a for a in results if a.action_type == action_type]

        if trigger is not None:
            results = [a for a in results if a.trigger == trigger]

        if tags:
            tag_set = {t.lower() for t in tags}
            results = [a for a in results if tag_set.intersection(a.tags)]

        # Sort by priority (lower = higher priority)
        return sorted(results, key=lambda a: a.priority)

    def validate_action(
        self,
        action_name: str,
        target: str,
        *,
        approval_granted: bool = False,
    ) -> ValidationResult:
        """Validate whether an action can be executed.

        Checks:
        1. Action exists and is enabled
        2. Approval granted if required
        3. Max attempts not exceeded
        4. Cooldown period has passed
        5. Global rate limit not exceeded

        Args:
            action_name: Name of the action to validate
            target: The target (service, container, etc.) for the action
            approval_granted: Whether human approval has been obtained

        Returns:
            ValidationResult with can_execute status and reason
        """
        try:
            action = self.get_action(action_name)
        except ActionNotFoundError:
            return ValidationResult(
                can_execute=False,
                action_name=action_name,
                target=target,
                reason=f"Action '{action_name}' not found in registry",
            )

        # Check if action is enabled
        if not action.enabled:
            return ValidationResult(
                can_execute=False,
                action_name=action_name,
                target=target,
                reason=f"Action '{action_name}' is disabled",
            )

        # Check approval requirement
        if action.requires_approval == ApprovalLevel.REQUIRE and not approval_granted:
            return ValidationResult(
                can_execute=False,
                action_name=action_name,
                target=target,
                reason=f"Action '{action_name}' requires approval",
                requires_approval=True,
            )

        # Get execution history for this action/target (excluding dry-runs)
        history = self._execution_history[action_name][target]
        real_history = [e for e in history if not e.dry_run]
        now = datetime.now(UTC)

        # Check max attempts within cooldown window
        # This is checked BEFORE cooldown so tests can verify max_attempts logic
        window_start = now - timedelta(seconds=action.cooldown_seconds)
        recent_attempts = [e for e in real_history if e.timestamp >= window_start]
        attempts_remaining = action.max_attempts - len(recent_attempts)

        if attempts_remaining <= 0:
            return ValidationResult(
                can_execute=False,
                action_name=action_name,
                target=target,
                reason=f"Action '{action_name}' has reached max attempts ({action.max_attempts})",
                attempts_remaining=0,
            )

        # Check cooldown (only for real executions)
        if real_history:
            last_execution = max(real_history, key=lambda e: e.timestamp)
            cooldown_ends = last_execution.timestamp + timedelta(seconds=action.cooldown_seconds)
            if now < cooldown_ends:
                remaining = int((cooldown_ends - now).total_seconds())
                return ValidationResult(
                    can_execute=False,
                    action_name=action_name,
                    target=target,
                    reason=f"Action '{action_name}' is in cooldown ({remaining}s remaining)",
                    cooldown_remaining_seconds=remaining,
                )

        # Check global rate limit (only real executions)
        all_recent_executions = sum(
            len([e for e in target_history if e.timestamp >= now - timedelta(hours=1) and not e.dry_run])
            for action_history in self._execution_history.values()
            for target_history in action_history.values()
        )
        if all_recent_executions >= self._config.global_rate_limit_per_hour:
            return ValidationResult(
                can_execute=False,
                action_name=action_name,
                target=target,
                reason="Global rate limit exceeded",
            )

        # All checks passed
        return ValidationResult(
            can_execute=True,
            action_name=action_name,
            target=target,
            reason="Action is ready to execute",
            attempts_remaining=attempts_remaining,
            requires_approval=(action.requires_approval == ApprovalLevel.NOTIFY),
        )

    def dry_run(
        self,
        action_name: str,
        target: str,
        variables: dict[str, str] | None = None,
        *,
        approval_granted: bool = False,
    ) -> DryRunResult:
        """Perform a dry-run of an action.

        Shows what would happen if the action were executed without actually
        running it.

        Args:
            action_name: Name of the action to dry-run
            target: The target for the action
            variables: Variables to substitute in the command template
            approval_granted: Whether approval has been granted

        Returns:
            DryRunResult showing what would happen
        """
        try:
            action = self.get_action(action_name)
        except ActionNotFoundError:
            # Return a result indicating action not found
            validation = ValidationResult(
                can_execute=False,
                action_name=action_name,
                target=target,
                reason=f"Action '{action_name}' not found in registry",
            )
            return DryRunResult(
                action_name=action_name,
                action_type=ActionType.CUSTOM,
                target=target,
                command="(action not found)",
                validation=validation,
            )

        # Prepare variables with defaults
        all_variables = {"target": target}
        if variables:
            all_variables.update(variables)

        # Render command
        warnings: list[str] = []
        try:
            rendered_command = action.render_command(all_variables)
        except KeyError as e:
            rendered_command = f"(missing variable: {e})"
            warnings.append(f"Missing required variable: {e}")

        # Validate
        validation = self.validate_action(action_name, target, approval_granted=approval_granted)

        # Add warnings
        if action.requires_approval == ApprovalLevel.REQUIRE and not approval_granted:
            warnings.append("This action requires human approval before execution")
        if action.requires_approval == ApprovalLevel.NOTIFY:
            warnings.append("Executing this action will send a notification")
        if action.max_attempts == 1:
            warnings.append("This action can only be attempted once per cooldown period")

        return DryRunResult(
            action_name=action_name,
            action_type=action.action_type,
            target=target,
            command=rendered_command,
            validation=validation,
            estimated_duration_seconds=action.timeout_seconds,
            warnings=warnings,
            rollback_available=action.rollback_command is not None,
        )

    def record_execution(
        self,
        action_name: str,
        target: str,
        success: bool,
        *,
        dry_run: bool = False,
        duration_ms: int | None = None,
        error: str | None = None,
        output: str | None = None,
        approved_by: str | None = None,
    ) -> ActionExecution:
        """Record an action execution attempt.

        This should be called by the executor (OBS-011) after attempting
        an action.

        Args:
            action_name: Name of the action that was executed
            target: The target of the action
            success: Whether the execution succeeded
            dry_run: Whether this was a dry-run
            duration_ms: Execution duration in milliseconds
            error: Error message if failed
            output: Output from execution
            approved_by: Who approved the execution

        Returns:
            The recorded ActionExecution
        """
        execution = ActionExecution(
            action_name=action_name,
            target=target,
            success=success,
            dry_run=dry_run,
            duration_ms=duration_ms,
            error=error,
            output=output,
            approved_by=approved_by,
        )
        self._execution_history[action_name][target].append(execution)
        return execution

    def get_execution_history(
        self,
        action_name: str | None = None,
        target: str | None = None,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ActionExecution]:
        """Get execution history.

        Args:
            action_name: Filter by action name
            target: Filter by target
            since: Only return executions after this time
            limit: Maximum number of results

        Returns:
            List of ActionExecution records
        """
        results: list[ActionExecution] = []

        for a_name, targets in self._execution_history.items():
            if action_name and a_name != action_name:
                continue
            for t, executions in targets.items():
                if target and t != target:
                    continue
                results.extend(executions)

        if since:
            results = [e for e in results if e.timestamp >= since]

        # Sort by timestamp descending
        results.sort(key=lambda e: e.timestamp, reverse=True)

        return results[:limit]

    def clear_history(
        self,
        action_name: str | None = None,
        target: str | None = None,
    ) -> int:
        """Clear execution history.

        Args:
            action_name: Clear only for this action
            target: Clear only for this target

        Returns:
            Number of records cleared
        """
        count = 0

        if action_name is None and target is None:
            # Clear all
            for a_name in list(self._execution_history.keys()):
                for t in list(self._execution_history[a_name].keys()):
                    count += len(self._execution_history[a_name][t])
            self._execution_history.clear()
        elif action_name and target:
            count = len(self._execution_history.get(action_name, {}).get(target, []))
            if action_name in self._execution_history:
                self._execution_history[action_name].pop(target, None)
        elif action_name:
            if action_name in self._execution_history:
                count = sum(len(execs) for execs in self._execution_history[action_name].values())
                del self._execution_history[action_name]
        elif target:
            for a_name in list(self._execution_history.keys()):
                if target in self._execution_history[a_name]:
                    count += len(self._execution_history[a_name][target])
                    del self._execution_history[a_name][target]

        return count

    def get_actions_for_trigger(self, trigger: TriggerType) -> list[ActionDefinition]:
        """Get all enabled actions for a specific trigger.

        Args:
            trigger: The trigger type

        Returns:
            List of ActionDefinition objects that respond to this trigger
        """
        return self.list_actions(trigger=trigger, enabled_only=True)

    def __len__(self) -> int:
        """Return number of registered actions."""
        return len(self._actions)

    def __contains__(self, action_name: str) -> bool:
        """Check if an action exists in the registry."""
        return action_name.lower() in self._actions
