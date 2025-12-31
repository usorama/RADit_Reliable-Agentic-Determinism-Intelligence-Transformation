"""
Remediation Actions module for the Observability package.

This module provides the action registry and models for configurable
remediation actions used by the self-healing system.

Part of OBS-010: Remediation Action Registry
See: docs/planning/epics/EPIC-13-OBSERVABILITY.md

Exports:
    Models:
        - ActionType: Types of remediation actions (restart, scale, rollback, etc.)
        - TriggerType: Event types that can trigger actions
        - ApprovalLevel: Approval requirements (none, notify, require)
        - ActionDefinition: Configuration for a single action
        - ActionExecution: Record of an action execution
        - ValidationResult: Result of action validation
        - DryRunResult: Result of a dry-run execution
        - ActionRegistryConfig: Full registry configuration

    Registry:
        - ActionRegistry: Main registry class for managing actions
        - ActionRegistryError: Base exception
        - ActionNotFoundError: Action not found in registry
        - ConfigurationError: Invalid configuration
"""

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
from .registry import (
    ActionNotFoundError,
    ActionRegistry,
    ActionRegistryError,
    ConfigurationError,
)

__all__ = [
    # Models
    "ActionType",
    "TriggerType",
    "ApprovalLevel",
    "ActionDefinition",
    "ActionExecution",
    "ValidationResult",
    "DryRunResult",
    "ActionRegistryConfig",
    # Registry
    "ActionRegistry",
    "ActionRegistryError",
    "ActionNotFoundError",
    "ConfigurationError",
]
