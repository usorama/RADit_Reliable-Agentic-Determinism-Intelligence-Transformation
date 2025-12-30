"""RBAC (Role-Based Access Control) for MCP Tools.

This module implements fine-grained Role-Based Access Control for MCP tools
per FR-01.3.2 in the PRD.

RBAC Role Permissions (from PRD):
- Planner: search, read_file, query_db (SELECT) - No writes
- Executor: read_file, write_file, git_commit - write_file scoped to project directory
- Validator: run_tests, security_scan, lint - No file writes
- Healer: read_file, write_file (patches only) - Requires human approval for production

Key Features:
- Role enum defining agent roles (PLANNER, EXECUTOR, VALIDATOR, HEALER)
- Permission model with tool, actions, scope, and conditions
- RBACPolicy class for loading and managing policies from YAML
- check_permission method for contextual permission checks
- Scope validation (project directory for Executor, patches for Healer)
- Human approval requirement for Healer in production
- Policy hot-reloading capability

References:
    - PRD FR-01.3.2: RBAC for Tools
    - Definition of Done Story 6.2

Example usage:
    policy = RBACPolicy.from_yaml()

    result = policy.check_permission(
        role=Role.PLANNER,
        tool="search",
        action="search",
    )

    if result.allowed:
        # Proceed with tool call
        pass
    elif result.requires_approval:
        # Request human approval
        pass
    else:
        # Deny access
        raise PermissionDeniedError(...)
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Default path to policies.yaml relative to this module
_DEFAULT_POLICY_PATH = Path(__file__).parent / "policies.yaml"


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class Role(str, Enum):
    """Agent role definitions for RBAC.

    Per PRD FR-01.3.2, the system defines four agent roles:
    - PLANNER: Read-only access for planning and research
    - EXECUTOR: Write access scoped to project directory
    - VALIDATOR: Testing and scanning, no write access
    - HEALER: Patch-only writes with approval in production
    """

    PLANNER = "planner"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    HEALER = "healer"


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class RBACError(Exception):
    """Base exception for RBAC errors."""

    pass


class PolicyParseError(RBACError):
    """Raised when policy YAML cannot be parsed."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class PermissionDeniedError(RBACError):
    """Raised when a permission check fails."""

    def __init__(self, role: str, tool: str, reason: str) -> None:
        self.role = role
        self.tool = tool
        self.reason = reason
        super().__init__(f"Permission denied for {role} on {tool}: {reason}")


class RoleNotFoundError(RBACError):
    """Raised when a role is not found in the policy."""

    def __init__(self, role: str) -> None:
        self.role = role
        super().__init__(f"Role not found: {role}")


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class Permission(BaseModel):
    """Permission definition for a single tool.

    Attributes:
        tool: The name of the tool this permission applies to
        actions: List of allowed actions (e.g., ["read", "write"] or ["SELECT"])
        scope: Optional scope restriction (e.g., "{project_root}", "patches")
        conditions: Optional conditions dict (e.g., {"requires_approval_in": ["production"]})
    """

    tool: str
    actions: list[str]
    scope: str | None = Field(default=None)
    conditions: dict[str, Any] | None = Field(default=None)


class PermissionContext(BaseModel):
    """Context for permission checks.

    Provides contextual information for scope validation and conditional checks.

    Attributes:
        path: The file path being accessed (if applicable)
        project_root: The root directory of the project
        environment: The deployment environment (development, staging, production)
        query: The database query being executed (if applicable)
    """

    path: str | None = Field(default=None)
    project_root: str | None = Field(default=None)
    environment: str | None = Field(default=None)
    query: str | None = Field(default=None)

    def is_within_project(self) -> bool:
        """Check if the path is within the project root.

        Returns:
            True if path is within project_root, False otherwise
        """
        if not self.path or not self.project_root:
            return True  # No path restriction if not specified

        path = Path(self.path).resolve()
        project = Path(self.project_root).resolve()

        try:
            path.relative_to(project)
            return True
        except ValueError:
            return False

    def is_patch_file(self) -> bool:
        """Check if the path is a patch file.

        Returns:
            True if path is a .patch file or in patches directory
        """
        if not self.path:
            return False

        path_lower = self.path.lower()
        return path_lower.endswith(".patch") or "/patches/" in path_lower

    def is_production(self) -> bool:
        """Check if the environment is production.

        Returns:
            True if environment is "production"
        """
        return self.environment == "production"


class PermissionResult(BaseModel):
    """Result of a permission check.

    Attributes:
        allowed: Whether the permission is granted
        role: The role that was checked
        tool: The tool that was checked
        action: The action that was checked
        reason: Explanation for the result (especially for denials)
        requires_approval: Whether human approval is required before execution
    """

    allowed: bool
    role: str
    tool: str
    action: str | None = Field(default=None)
    reason: str | None = Field(default=None)
    requires_approval: bool = Field(default=False)


class RolePolicy(BaseModel):
    """Policy definition for a single role.

    Attributes:
        role: The role this policy applies to
        permissions: List of permissions granted to this role
    """

    role: Role
    permissions: list[Permission]

    def has_permission(self, tool: str) -> bool:
        """Check if this role has any permission for a tool.

        Args:
            tool: The tool name to check

        Returns:
            True if any permission exists for this tool
        """
        return any(p.tool == tool for p in self.permissions)

    def get_permission(self, tool: str) -> Permission | None:
        """Get the permission for a specific tool.

        Args:
            tool: The tool name to get permission for

        Returns:
            The Permission object, or None if not found
        """
        for perm in self.permissions:
            if perm.tool == tool:
                return perm
        return None


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def get_default_policy_path() -> str:
    """Get the default path to policies.yaml.

    Returns:
        Absolute path to the default policies.yaml file
    """
    return str(_DEFAULT_POLICY_PATH)


# -----------------------------------------------------------------------------
# RBACPolicy Class
# -----------------------------------------------------------------------------


class RBACPolicy:
    """RBAC Policy manager for MCP tools.

    Manages role-based access control policies, supporting:
    - Loading policies from YAML configuration
    - Permission checking with context
    - Scope validation
    - Human approval requirements
    - Policy hot-reloading

    Example:
        policy = RBACPolicy.from_yaml()
        result = policy.check_permission(
            role=Role.PLANNER,
            tool="read_file",
            action="read",
        )
    """

    def __init__(
        self,
        role_policies: dict[Role, RolePolicy] | None = None,
        policy_path: str | None = None,
    ) -> None:
        """Initialize RBACPolicy.

        Args:
            role_policies: Optional pre-configured role policies
            policy_path: Optional path to policy YAML file for reloading
        """
        self._policy_path = policy_path
        self._role_policies: dict[Role, RolePolicy] = {}

        if role_policies:
            self._role_policies = role_policies
        else:
            # Initialize with default policies
            self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Initialize default policies per PRD FR-01.3.2."""
        # Planner: search, read_file, query_db (SELECT) - No writes
        self._role_policies[Role.PLANNER] = RolePolicy(
            role=Role.PLANNER,
            permissions=[
                Permission(tool="search", actions=["search"]),
                Permission(tool="read_file", actions=["read"]),
                Permission(tool="query_db", actions=["SELECT"]),
            ],
        )

        # Executor: read_file, write_file, git_commit - write_file scoped to project
        self._role_policies[Role.EXECUTOR] = RolePolicy(
            role=Role.EXECUTOR,
            permissions=[
                Permission(tool="read_file", actions=["read"]),
                Permission(
                    tool="write_file",
                    actions=["write"],
                    scope="{project_root}",
                ),
                Permission(tool="git_commit", actions=["commit"]),
            ],
        )

        # Validator: run_tests, security_scan, lint - No file writes
        self._role_policies[Role.VALIDATOR] = RolePolicy(
            role=Role.VALIDATOR,
            permissions=[
                Permission(tool="run_tests", actions=["run"]),
                Permission(tool="security_scan", actions=["scan"]),
                Permission(tool="lint", actions=["run"]),
            ],
        )

        # Healer: read_file, write_file (patches only) - Requires approval in production
        self._role_policies[Role.HEALER] = RolePolicy(
            role=Role.HEALER,
            permissions=[
                Permission(tool="read_file", actions=["read"]),
                Permission(
                    tool="write_file",
                    actions=["write"],
                    scope="patches",
                    conditions={"requires_approval_in": ["production"]},
                ),
            ],
        )

    @classmethod
    def from_yaml(cls, path: str | None = None) -> RBACPolicy:
        """Load policies from a YAML file.

        Args:
            path: Path to the YAML file. If None, uses default policies.yaml

        Returns:
            RBACPolicy instance with loaded policies

        Raises:
            PolicyParseError: If the YAML is invalid or missing required fields
        """
        if path is None:
            path = get_default_policy_path()

        policy_path = Path(path)
        if not policy_path.exists():
            # If file doesn't exist, return default policies
            logger.warning(
                "Policy file not found at %s, using defaults", path
            )
            return cls(policy_path=path)

        try:
            with open(policy_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PolicyParseError(f"Invalid YAML: {e}") from e

        if not isinstance(data, dict) or "roles" not in data:
            raise PolicyParseError("YAML must have 'roles' key")

        role_policies: dict[Role, RolePolicy] = {}

        for role_name, role_data in data["roles"].items():
            try:
                role = Role(role_name)
            except ValueError:
                logger.warning("Unknown role in policy: %s", role_name)
                continue

            if "permissions" not in role_data:
                raise PolicyParseError(
                    f"Role '{role_name}' missing 'permissions' key"
                )

            permissions: list[Permission] = []
            for perm_data in role_data["permissions"]:
                if "tool" not in perm_data or "actions" not in perm_data:
                    raise PolicyParseError(
                        f"Permission in role '{role_name}' missing required fields"
                    )

                permissions.append(
                    Permission(
                        tool=perm_data["tool"],
                        actions=perm_data["actions"],
                        scope=perm_data.get("scope"),
                        conditions=perm_data.get("conditions"),
                    )
                )

            role_policies[role] = RolePolicy(
                role=role,
                permissions=permissions,
            )

        return cls(role_policies=role_policies, policy_path=path)

    def get_role_policy(self, role: Role | str) -> RolePolicy | None:
        """Get the policy for a specific role.

        Args:
            role: The role to get policy for (Role enum or string)

        Returns:
            RolePolicy for the role, or None if not found
        """
        if isinstance(role, str):
            try:
                role = Role(role)
            except ValueError:
                return None

        return self._role_policies.get(role)

    def check_permission(
        self,
        role: Role | str,
        tool: str,
        action: str,
        context: PermissionContext | None = None,
    ) -> PermissionResult:
        """Check if a role has permission for a tool action.

        Args:
            role: The role to check (Role enum or string)
            tool: The tool name
            action: The action being performed
            context: Optional context for scope and condition checks

        Returns:
            PermissionResult indicating whether access is allowed
        """
        # Normalize role
        if isinstance(role, str):
            try:
                role_enum = Role(role)
            except ValueError:
                return PermissionResult(
                    allowed=False,
                    role=role,
                    tool=tool,
                    action=action,
                    reason=f"Unknown role: {role}",
                )
        else:
            role_enum = role

        # Get role policy
        role_policy = self._role_policies.get(role_enum)
        if not role_policy:
            return PermissionResult(
                allowed=False,
                role=role_enum.value,
                tool=tool,
                action=action,
                reason=f"No policy defined for role: {role_enum.value}",
            )

        # Check if tool permission exists
        permission = role_policy.get_permission(tool)
        if not permission:
            return PermissionResult(
                allowed=False,
                role=role_enum.value,
                tool=tool,
                action=action,
                reason=f"Tool '{tool}' not permitted for role '{role_enum.value}'",
            )

        # Check if action is allowed
        if action not in permission.actions:
            return PermissionResult(
                allowed=False,
                role=role_enum.value,
                tool=tool,
                action=action,
                reason=f"Action '{action}' not permitted for tool '{tool}'",
            )

        # Check scope restrictions
        if permission.scope and context:
            scope_result = self._check_scope(
                permission.scope, context, role_enum, tool, action
            )
            if not scope_result.allowed:
                return scope_result

        # Check conditions (e.g., requires_approval_in)
        requires_approval = False
        if permission.conditions and context:
            requires_approval = self._check_requires_approval(
                permission.conditions, context
            )

        return PermissionResult(
            allowed=True,
            role=role_enum.value,
            tool=tool,
            action=action,
            requires_approval=requires_approval,
        )

    def _check_scope(
        self,
        scope: str,
        context: PermissionContext,
        role: Role,
        tool: str,
        action: str,
    ) -> PermissionResult:
        """Check scope restrictions.

        Args:
            scope: The scope restriction from permission
            context: The permission context
            role: The role being checked
            tool: The tool being accessed
            action: The action being performed

        Returns:
            PermissionResult indicating scope check result
        """
        # Project root scope check
        if scope == "{project_root}":
            if not context.is_within_project():
                return PermissionResult(
                    allowed=False,
                    role=role.value,
                    tool=tool,
                    action=action,
                    reason="Path is outside project scope",
                )

        # Patches scope check
        elif scope == "patches":
            if not context.is_patch_file():
                return PermissionResult(
                    allowed=False,
                    role=role.value,
                    tool=tool,
                    action=action,
                    reason="Only patch files are permitted",
                )

        return PermissionResult(
            allowed=True,
            role=role.value,
            tool=tool,
            action=action,
        )

    def _check_requires_approval(
        self,
        conditions: dict[str, Any],
        context: PermissionContext,
    ) -> bool:
        """Check if human approval is required.

        Args:
            conditions: The conditions dict from permission
            context: The permission context

        Returns:
            True if approval is required
        """
        requires_approval_in = conditions.get("requires_approval_in", [])

        if context.environment and context.environment in requires_approval_in:
            return True

        return False

    def reload(self) -> None:
        """Reload policies from the YAML file.

        Only works if policy was loaded from a file.
        """
        if self._policy_path:
            loaded = RBACPolicy.from_yaml(self._policy_path)
            self._role_policies = loaded._role_policies
            logger.info("Reloaded policies from %s", self._policy_path)

    def watch(self, callback: Any = None) -> None:
        """Enable watching the policy file for changes.

        This is a placeholder for file watching functionality.
        In production, this would use watchdog or similar.

        Args:
            callback: Optional callback when file changes
        """
        # Placeholder for file watching
        # In production, would use watchdog or fswatch
        logger.info("Policy watching enabled for %s", self._policy_path)
