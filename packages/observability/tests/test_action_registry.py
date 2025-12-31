"""
Tests for the Remediation Action Registry.

Part of OBS-010: Remediation Action Registry
Coverage target: >80%

Test categories:
- Model validation tests
- Registry loading tests
- Action validation tests
- Dry-run tests
- Execution history tests
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from observability.actions import (
    ActionDefinition,
    ActionExecution,
    ActionNotFoundError,
    ActionRegistry,
    ActionRegistryConfig,
    ActionType,
    ApprovalLevel,
    ConfigurationError,
    DryRunResult,
    TriggerType,
    ValidationResult,
)


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestActionType:
    """Tests for ActionType enum."""

    def test_all_types_defined(self) -> None:
        """Ensure all required action types are defined."""
        assert ActionType.RESTART == "restart"
        assert ActionType.SCALE == "scale"
        assert ActionType.ROLLBACK == "rollback"
        assert ActionType.CLEAR_CACHE == "clear_cache"
        assert ActionType.CUSTOM == "custom"


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_all_triggers_defined(self) -> None:
        """Ensure all required trigger types are defined."""
        assert TriggerType.CONTAINER_UNHEALTHY == "container_unhealthy"
        assert TriggerType.HIGH_CPU_SUSTAINED == "high_cpu_sustained"
        assert TriggerType.ERROR_RATE_SPIKE == "error_rate_spike"
        assert TriggerType.CACHE_MEMORY_HIGH == "cache_memory_high"


class TestApprovalLevel:
    """Tests for ApprovalLevel enum."""

    def test_all_levels_defined(self) -> None:
        """Ensure all approval levels are defined."""
        assert ApprovalLevel.NONE == "none"
        assert ApprovalLevel.NOTIFY == "notify"
        assert ApprovalLevel.REQUIRE == "require"


class TestActionDefinition:
    """Tests for ActionDefinition model."""

    def test_valid_action_definition(self) -> None:
        """Test creating a valid action definition."""
        action = ActionDefinition(
            name="restart_container",
            action_type=ActionType.RESTART,
            trigger=TriggerType.CONTAINER_UNHEALTHY,
            command="docker restart {target}",
        )
        assert action.name == "restart_container"
        assert action.action_type == ActionType.RESTART
        assert action.cooldown_seconds == 300  # default
        assert action.max_attempts == 3  # default
        assert action.enabled is True

    def test_name_validation_lowercase(self) -> None:
        """Test that names are normalized to lowercase."""
        action = ActionDefinition(
            name="RESTART_CONTAINER",
            action_type=ActionType.RESTART,
            trigger=TriggerType.CONTAINER_UNHEALTHY,
            command="docker restart {target}",
        )
        assert action.name == "restart_container"

    def test_name_validation_invalid_chars(self) -> None:
        """Test that invalid characters in name are rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            ActionDefinition(
                name="restart-container",  # hyphen not allowed
                action_type=ActionType.RESTART,
                trigger=TriggerType.CONTAINER_UNHEALTHY,
                command="docker restart {target}",
            )

    def test_tags_normalized(self) -> None:
        """Test that tags are normalized to lowercase."""
        action = ActionDefinition(
            name="test_action",
            action_type=ActionType.CUSTOM,
            trigger=TriggerType.CUSTOM,
            command="echo test",
            tags=["Docker", "  CONTAINER  ", ""],
        )
        assert action.tags == ["docker", "container"]

    def test_render_command_success(self) -> None:
        """Test rendering a command with variables."""
        action = ActionDefinition(
            name="scale_service",
            action_type=ActionType.SCALE,
            trigger=TriggerType.HIGH_CPU_SUSTAINED,
            command="docker service scale {target}={replicas}",
        )
        result = action.render_command({"target": "web-api", "replicas": "5"})
        assert result == "docker service scale web-api=5"

    def test_render_command_missing_variable(self) -> None:
        """Test that missing variables raise KeyError."""
        action = ActionDefinition(
            name="scale_service",
            action_type=ActionType.SCALE,
            trigger=TriggerType.HIGH_CPU_SUSTAINED,
            command="docker service scale {target}={replicas}",
        )
        with pytest.raises(KeyError, match="replicas"):
            action.render_command({"target": "web-api"})

    def test_cooldown_constraints(self) -> None:
        """Test cooldown value constraints."""
        # Valid: 0 seconds (no cooldown)
        action = ActionDefinition(
            name="test",
            action_type=ActionType.CUSTOM,
            trigger=TriggerType.CUSTOM,
            command="echo test",
            cooldown_seconds=0,
        )
        assert action.cooldown_seconds == 0

        # Invalid: negative
        with pytest.raises(ValueError):
            ActionDefinition(
                name="test",
                action_type=ActionType.CUSTOM,
                trigger=TriggerType.CUSTOM,
                command="echo test",
                cooldown_seconds=-1,
            )

        # Invalid: > 24 hours
        with pytest.raises(ValueError):
            ActionDefinition(
                name="test",
                action_type=ActionType.CUSTOM,
                trigger=TriggerType.CUSTOM,
                command="echo test",
                cooldown_seconds=86401,
            )


class TestActionRegistryConfig:
    """Tests for ActionRegistryConfig model."""

    def test_valid_config(self) -> None:
        """Test creating a valid config."""
        config = ActionRegistryConfig(
            version="1.0.0",
            actions=[
                ActionDefinition(
                    name="test",
                    action_type=ActionType.CUSTOM,
                    trigger=TriggerType.CUSTOM,
                    command="echo test",
                )
            ],
        )
        assert config.version == "1.0.0"
        assert len(config.actions) == 1

    def test_duplicate_action_names_rejected(self) -> None:
        """Test that duplicate action names are rejected."""
        with pytest.raises(ValueError, match="Duplicate action names"):
            ActionRegistryConfig(
                actions=[
                    ActionDefinition(
                        name="test",
                        action_type=ActionType.CUSTOM,
                        trigger=TriggerType.CUSTOM,
                        command="echo test1",
                    ),
                    ActionDefinition(
                        name="test",  # duplicate
                        action_type=ActionType.RESTART,
                        trigger=TriggerType.CONTAINER_UNHEALTHY,
                        command="echo test2",
                    ),
                ]
            )


# =============================================================================
# REGISTRY LOADING TESTS
# =============================================================================


class TestRegistryLoading:
    """Tests for loading the registry from various sources."""

    def test_from_yaml_file(self) -> None:
        """Test loading registry from a YAML file."""
        config = """
version: "1.0.0"
global_rate_limit_per_hour: 5
actions:
  - name: restart_test
    action_type: restart
    trigger: container_unhealthy
    command: "docker restart {target}"
    cooldown_seconds: 60
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config)
            f.flush()
            registry = ActionRegistry.from_yaml(f.name)

        assert len(registry) == 1
        assert "restart_test" in registry
        action = registry.get_action("restart_test")
        assert action.cooldown_seconds == 60

    def test_from_yaml_nonexistent_file(self) -> None:
        """Test loading from nonexistent file returns empty registry."""
        registry = ActionRegistry.from_yaml("/nonexistent/path/config.yaml")
        assert len(registry) == 0

    def test_from_yaml_invalid_yaml(self) -> None:
        """Test loading invalid YAML raises ConfigurationError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [[[")
            f.flush()
            with pytest.raises(ConfigurationError, match="Invalid YAML"):
                ActionRegistry.from_yaml(f.name)

    def test_from_yaml_invalid_config(self) -> None:
        """Test loading invalid config raises ConfigurationError."""
        config = """
version: "1.0.0"
actions:
  - name: test
    # missing required fields
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config)
            f.flush()
            with pytest.raises(ConfigurationError, match="Invalid configuration"):
                ActionRegistry.from_yaml(f.name)

    def test_from_dict(self) -> None:
        """Test loading registry from a dictionary."""
        config = {
            "version": "1.0.0",
            "actions": [
                {
                    "name": "test_action",
                    "action_type": "restart",
                    "trigger": "container_unhealthy",
                    "command": "docker restart {target}",
                }
            ],
        }
        registry = ActionRegistry.from_dict(config)
        assert len(registry) == 1
        assert "test_action" in registry

    def test_from_dict_with_bool_approval(self) -> None:
        """Test handling legacy boolean requires_approval."""
        config = {
            "actions": [
                {
                    "name": "test_action",
                    "action_type": "restart",
                    "trigger": "container_unhealthy",
                    "command": "docker restart {target}",
                    "requires_approval": True,  # Legacy boolean
                }
            ],
        }
        registry = ActionRegistry.from_dict(config)
        action = registry.get_action("test_action")
        assert action.requires_approval == ApprovalLevel.REQUIRE

    def test_from_default_config(self) -> None:
        """Test loading from default config file."""
        registry = ActionRegistry.from_yaml()
        # Default config should have at least the standard actions
        assert len(registry) > 0
        # Check for expected actions
        assert "restart_container" in registry
        assert "scale_service" in registry
        assert "rollback_deployment" in registry
        assert "clear_cache" in registry


# =============================================================================
# REGISTRY OPERATIONS TESTS
# =============================================================================


class TestRegistryOperations:
    """Tests for registry operations."""

    @pytest.fixture
    def registry(self) -> ActionRegistry:
        """Create a test registry."""
        config = ActionRegistryConfig(
            version="1.0.0",
            global_rate_limit_per_hour=5,
            actions=[
                ActionDefinition(
                    name="restart_container",
                    action_type=ActionType.RESTART,
                    trigger=TriggerType.CONTAINER_UNHEALTHY,
                    command="docker restart {target}",
                    cooldown_seconds=60,
                    max_attempts=3,
                    tags=["docker", "automatic"],
                ),
                ActionDefinition(
                    name="scale_service",
                    action_type=ActionType.SCALE,
                    trigger=TriggerType.HIGH_CPU_SUSTAINED,
                    command="docker service scale {target}={replicas}",
                    requires_approval=ApprovalLevel.REQUIRE,
                    tags=["docker", "manual"],
                ),
                ActionDefinition(
                    name="disabled_action",
                    action_type=ActionType.CUSTOM,
                    trigger=TriggerType.CUSTOM,
                    command="echo disabled",
                    enabled=False,
                    tags=["test"],
                ),
            ],
        )
        return ActionRegistry(config)

    def test_get_action_exists(self, registry: ActionRegistry) -> None:
        """Test getting an existing action."""
        action = registry.get_action("restart_container")
        assert action.name == "restart_container"
        assert action.action_type == ActionType.RESTART

    def test_get_action_not_found(self, registry: ActionRegistry) -> None:
        """Test getting a nonexistent action."""
        with pytest.raises(ActionNotFoundError, match="not found"):
            registry.get_action("nonexistent")

    def test_list_actions_all(self, registry: ActionRegistry) -> None:
        """Test listing all enabled actions."""
        actions = registry.list_actions()
        assert len(actions) == 2  # disabled_action excluded

    def test_list_actions_include_disabled(self, registry: ActionRegistry) -> None:
        """Test listing all actions including disabled."""
        actions = registry.list_actions(enabled_only=False)
        assert len(actions) == 3

    def test_list_actions_by_type(self, registry: ActionRegistry) -> None:
        """Test filtering by action type."""
        actions = registry.list_actions(action_type=ActionType.RESTART)
        assert len(actions) == 1
        assert actions[0].name == "restart_container"

    def test_list_actions_by_trigger(self, registry: ActionRegistry) -> None:
        """Test filtering by trigger type."""
        actions = registry.list_actions(trigger=TriggerType.HIGH_CPU_SUSTAINED)
        assert len(actions) == 1
        assert actions[0].name == "scale_service"

    def test_list_actions_by_tags(self, registry: ActionRegistry) -> None:
        """Test filtering by tags."""
        actions = registry.list_actions(tags=["automatic"])
        assert len(actions) == 1
        assert actions[0].name == "restart_container"

        actions = registry.list_actions(tags=["docker"])
        assert len(actions) == 2  # Both docker actions

    def test_contains(self, registry: ActionRegistry) -> None:
        """Test the contains operator."""
        assert "restart_container" in registry
        assert "nonexistent" not in registry

    def test_len(self, registry: ActionRegistry) -> None:
        """Test the len operator."""
        assert len(registry) == 3

    def test_get_actions_for_trigger(self, registry: ActionRegistry) -> None:
        """Test getting actions for a specific trigger."""
        actions = registry.get_actions_for_trigger(TriggerType.CONTAINER_UNHEALTHY)
        assert len(actions) == 1
        assert actions[0].name == "restart_container"


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestValidation:
    """Tests for action validation."""

    @pytest.fixture
    def registry(self) -> ActionRegistry:
        """Create a test registry."""
        config = ActionRegistryConfig(
            version="1.0.0",
            global_rate_limit_per_hour=5,
            actions=[
                ActionDefinition(
                    name="auto_action",
                    action_type=ActionType.RESTART,
                    trigger=TriggerType.CONTAINER_UNHEALTHY,
                    command="docker restart {target}",
                    cooldown_seconds=60,
                    max_attempts=2,
                    requires_approval=ApprovalLevel.NONE,
                ),
                ActionDefinition(
                    name="approval_action",
                    action_type=ActionType.SCALE,
                    trigger=TriggerType.HIGH_CPU_SUSTAINED,
                    command="docker service scale {target}={replicas}",
                    requires_approval=ApprovalLevel.REQUIRE,
                ),
                ActionDefinition(
                    name="notify_action",
                    action_type=ActionType.CLEAR_CACHE,
                    trigger=TriggerType.CACHE_MEMORY_HIGH,
                    command="redis-cli FLUSHDB",
                    requires_approval=ApprovalLevel.NOTIFY,
                ),
                ActionDefinition(
                    name="disabled_action",
                    action_type=ActionType.CUSTOM,
                    trigger=TriggerType.CUSTOM,
                    command="echo test",
                    enabled=False,
                ),
            ],
        )
        return ActionRegistry(config)

    def test_validate_action_success(self, registry: ActionRegistry) -> None:
        """Test successful validation."""
        result = registry.validate_action("auto_action", target="web-api")
        assert result.can_execute is True
        assert result.reason == "Action is ready to execute"

    def test_validate_action_not_found(self, registry: ActionRegistry) -> None:
        """Test validation of nonexistent action."""
        result = registry.validate_action("nonexistent", target="web-api")
        assert result.can_execute is False
        assert "not found" in result.reason

    def test_validate_action_disabled(self, registry: ActionRegistry) -> None:
        """Test validation of disabled action."""
        result = registry.validate_action("disabled_action", target="web-api")
        assert result.can_execute is False
        assert "disabled" in result.reason

    def test_validate_action_requires_approval(self, registry: ActionRegistry) -> None:
        """Test validation when approval is required."""
        result = registry.validate_action("approval_action", target="web-api")
        assert result.can_execute is False
        assert "requires approval" in result.reason
        assert result.requires_approval is True

        # With approval granted
        result = registry.validate_action(
            "approval_action", target="web-api", approval_granted=True
        )
        assert result.can_execute is True

    def test_validate_action_notify_level(self, registry: ActionRegistry) -> None:
        """Test validation with notify approval level."""
        result = registry.validate_action("notify_action", target="web-api")
        assert result.can_execute is True
        assert result.requires_approval is True  # Should flag for notification

    def test_validate_action_cooldown(self, registry: ActionRegistry) -> None:
        """Test validation respects cooldown."""
        # Record an execution
        registry.record_execution("auto_action", "web-api", success=True)

        # Should be in cooldown
        result = registry.validate_action("auto_action", target="web-api")
        assert result.can_execute is False
        assert "cooldown" in result.reason
        assert result.cooldown_remaining_seconds is not None
        assert result.cooldown_remaining_seconds > 0

    def test_validate_action_max_attempts(self, registry: ActionRegistry) -> None:
        """Test validation respects max attempts."""
        # Record max executions
        registry.record_execution("auto_action", "web-api", success=False)
        registry.record_execution("auto_action", "web-api", success=False)

        # Should have exhausted attempts
        result = registry.validate_action("auto_action", target="web-api")
        assert result.can_execute is False
        assert "max attempts" in result.reason
        assert result.attempts_remaining == 0

    def test_validate_action_global_rate_limit(self, registry: ActionRegistry) -> None:
        """Test validation respects global rate limit."""
        # Record executions up to limit
        for i in range(5):
            registry.record_execution("auto_action", f"target-{i}", success=True)

        # Should hit global rate limit
        result = registry.validate_action("auto_action", target="new-target")
        assert result.can_execute is False
        assert "Global rate limit" in result.reason

    def test_dry_run_excludes_from_rate_limit(self, registry: ActionRegistry) -> None:
        """Test that dry-run executions don't count toward limits."""
        # Record dry-run executions
        registry.record_execution("auto_action", "web-api", success=True, dry_run=True)
        registry.record_execution("auto_action", "web-api", success=True, dry_run=True)

        # Should still be able to execute
        result = registry.validate_action("auto_action", target="web-api")
        assert result.can_execute is True


# =============================================================================
# DRY-RUN TESTS
# =============================================================================


class TestDryRun:
    """Tests for dry-run functionality."""

    @pytest.fixture
    def registry(self) -> ActionRegistry:
        """Create a test registry."""
        config = ActionRegistryConfig(
            actions=[
                ActionDefinition(
                    name="restart_container",
                    action_type=ActionType.RESTART,
                    trigger=TriggerType.CONTAINER_UNHEALTHY,
                    command="docker restart {target}",
                    timeout_seconds=60,
                    rollback_command="docker start {target}",
                ),
                ActionDefinition(
                    name="scale_service",
                    action_type=ActionType.SCALE,
                    trigger=TriggerType.HIGH_CPU_SUSTAINED,
                    command="docker service scale {target}={replicas}",
                    max_attempts=1,
                    requires_approval=ApprovalLevel.REQUIRE,
                ),
            ]
        )
        return ActionRegistry(config)

    def test_dry_run_basic(self, registry: ActionRegistry) -> None:
        """Test basic dry-run."""
        result = registry.dry_run("restart_container", target="web-api")

        assert result.action_name == "restart_container"
        assert result.action_type == ActionType.RESTART
        assert result.target == "web-api"
        assert result.command == "docker restart web-api"
        assert result.validation.can_execute is True
        assert result.estimated_duration_seconds == 60
        assert result.rollback_available is True

    def test_dry_run_with_variables(self, registry: ActionRegistry) -> None:
        """Test dry-run with custom variables."""
        result = registry.dry_run(
            "scale_service",
            target="web-api",
            variables={"replicas": "5"},
            approval_granted=True,
        )

        assert result.command == "docker service scale web-api=5"

    def test_dry_run_missing_variable(self, registry: ActionRegistry) -> None:
        """Test dry-run with missing variable adds warning."""
        result = registry.dry_run("scale_service", target="web-api", approval_granted=True)

        assert "missing variable" in result.command.lower()
        assert any("Missing required variable" in w for w in result.warnings)

    def test_dry_run_nonexistent_action(self, registry: ActionRegistry) -> None:
        """Test dry-run of nonexistent action."""
        result = registry.dry_run("nonexistent", target="web-api")

        assert result.command == "(action not found)"
        assert result.validation.can_execute is False

    def test_dry_run_adds_approval_warning(self, registry: ActionRegistry) -> None:
        """Test dry-run adds warning for approval-required actions."""
        result = registry.dry_run("scale_service", target="web-api")

        assert any("requires human approval" in w for w in result.warnings)

    def test_dry_run_adds_max_attempts_warning(self, registry: ActionRegistry) -> None:
        """Test dry-run adds warning for single-attempt actions."""
        result = registry.dry_run(
            "scale_service", target="web-api", approval_granted=True
        )

        assert any("only be attempted once" in w for w in result.warnings)


# =============================================================================
# EXECUTION HISTORY TESTS
# =============================================================================


class TestExecutionHistory:
    """Tests for execution history tracking."""

    @pytest.fixture
    def registry(self) -> ActionRegistry:
        """Create a test registry."""
        config = ActionRegistryConfig(
            actions=[
                ActionDefinition(
                    name="test_action",
                    action_type=ActionType.RESTART,
                    trigger=TriggerType.CONTAINER_UNHEALTHY,
                    command="docker restart {target}",
                )
            ]
        )
        return ActionRegistry(config)

    def test_record_execution(self, registry: ActionRegistry) -> None:
        """Test recording an execution."""
        execution = registry.record_execution(
            action_name="test_action",
            target="web-api",
            success=True,
            duration_ms=1500,
            output="Container restarted",
        )

        assert execution.action_name == "test_action"
        assert execution.target == "web-api"
        assert execution.success is True
        assert execution.duration_ms == 1500
        assert execution.output == "Container restarted"

    def test_record_failed_execution(self, registry: ActionRegistry) -> None:
        """Test recording a failed execution."""
        execution = registry.record_execution(
            action_name="test_action",
            target="web-api",
            success=False,
            error="Connection refused",
        )

        assert execution.success is False
        assert execution.error == "Connection refused"

    def test_get_execution_history(self, registry: ActionRegistry) -> None:
        """Test retrieving execution history."""
        registry.record_execution("test_action", "target-1", success=True)
        registry.record_execution("test_action", "target-2", success=True)
        registry.record_execution("test_action", "target-1", success=False)

        # All history
        history = registry.get_execution_history()
        assert len(history) == 3

        # Filter by action
        history = registry.get_execution_history(action_name="test_action")
        assert len(history) == 3

        # Filter by target
        history = registry.get_execution_history(target="target-1")
        assert len(history) == 2

        # Filter by both
        history = registry.get_execution_history(
            action_name="test_action", target="target-1"
        )
        assert len(history) == 2

    def test_get_execution_history_since(self, registry: ActionRegistry) -> None:
        """Test filtering history by time."""
        registry.record_execution("test_action", "target-1", success=True)

        # Should find recent execution
        history = registry.get_execution_history(
            since=datetime.now(UTC) - timedelta(minutes=1)
        )
        assert len(history) == 1

        # Should not find execution before it happened
        history = registry.get_execution_history(
            since=datetime.now(UTC) + timedelta(minutes=1)
        )
        assert len(history) == 0

    def test_get_execution_history_limit(self, registry: ActionRegistry) -> None:
        """Test limiting history results."""
        for i in range(10):
            registry.record_execution("test_action", f"target-{i}", success=True)

        history = registry.get_execution_history(limit=5)
        assert len(history) == 5

    def test_clear_history_all(self, registry: ActionRegistry) -> None:
        """Test clearing all history."""
        registry.record_execution("test_action", "target-1", success=True)
        registry.record_execution("test_action", "target-2", success=True)

        count = registry.clear_history()
        assert count == 2
        assert len(registry.get_execution_history()) == 0

    def test_clear_history_by_action(self, registry: ActionRegistry) -> None:
        """Test clearing history for specific action."""
        registry.record_execution("test_action", "target-1", success=True)
        registry.record_execution("test_action", "target-2", success=True)

        count = registry.clear_history(action_name="test_action")
        assert count == 2

    def test_clear_history_by_target(self, registry: ActionRegistry) -> None:
        """Test clearing history for specific target."""
        registry.record_execution("test_action", "target-1", success=True)
        registry.record_execution("test_action", "target-1", success=True)
        registry.record_execution("test_action", "target-2", success=True)

        count = registry.clear_history(target="target-1")
        assert count == 2
        assert len(registry.get_execution_history()) == 1

    def test_clear_history_by_action_and_target(self, registry: ActionRegistry) -> None:
        """Test clearing history for specific action and target."""
        registry.record_execution("test_action", "target-1", success=True)
        registry.record_execution("test_action", "target-2", success=True)

        count = registry.clear_history(action_name="test_action", target="target-1")
        assert count == 1
        assert len(registry.get_execution_history()) == 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestDefaultConfigIntegration:
    """Tests using the default actions.yaml configuration."""

    def test_load_default_config(self) -> None:
        """Test that default config loads successfully."""
        registry = ActionRegistry.from_yaml()
        assert len(registry) > 0

    def test_restart_container_action(self) -> None:
        """Test restart_container action from default config."""
        registry = ActionRegistry.from_yaml()
        action = registry.get_action("restart_container")

        assert action.action_type == ActionType.RESTART
        assert action.trigger == TriggerType.CONTAINER_UNHEALTHY
        assert action.requires_approval == ApprovalLevel.NONE
        assert action.enabled is True

    def test_scale_service_action(self) -> None:
        """Test scale_service action from default config."""
        registry = ActionRegistry.from_yaml()
        action = registry.get_action("scale_service")

        assert action.action_type == ActionType.SCALE
        assert action.requires_approval == ApprovalLevel.REQUIRE

    def test_rollback_deployment_action(self) -> None:
        """Test rollback_deployment action from default config."""
        registry = ActionRegistry.from_yaml()
        action = registry.get_action("rollback_deployment")

        assert action.action_type == ActionType.ROLLBACK
        assert action.trigger == TriggerType.ERROR_RATE_SPIKE
        assert action.max_attempts == 1  # Rollback should be single attempt
        assert action.requires_approval == ApprovalLevel.REQUIRE

    def test_clear_cache_action(self) -> None:
        """Test clear_cache action from default config."""
        registry = ActionRegistry.from_yaml()
        action = registry.get_action("clear_cache")

        assert action.action_type == ActionType.CLEAR_CACHE
        assert action.trigger == TriggerType.CACHE_MEMORY_HIGH

    def test_dry_run_default_actions(self) -> None:
        """Test dry-run on default actions."""
        registry = ActionRegistry.from_yaml()

        # Restart
        result = registry.dry_run("restart_container", target="web-api")
        assert "docker restart web-api" in result.command
        assert result.validation.can_execute is True

        # Scale (requires approval)
        result = registry.dry_run(
            "scale_service",
            target="web-api",
            variables={"replicas": "3"},
        )
        assert "docker service scale web-api=3" in result.command
        assert result.validation.can_execute is False  # No approval
        assert result.validation.requires_approval is True
