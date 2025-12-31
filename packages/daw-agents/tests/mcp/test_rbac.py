"""Comprehensive tests for RBAC (Role-Based Access Control) for MCP Tools.

This module tests the RBAC implementation for fine-grained access control of MCP tools
per FR-01.3.2 in the PRD.

RBAC Role Permissions (from PRD):
- Planner: search, read_file, query_db (SELECT) - No writes
- Executor: read_file, write_file, git_commit - write_file scoped to project directory
- Validator: run_tests, security_scan, lint - No file writes
- Healer: read_file, write_file (patches only) - Requires human approval for production

Tests cover:
1. Role enum definition (PLANNER, EXECUTOR, VALIDATOR, HEALER)
2. Permission model (tool_name, allowed_actions, scopes)
3. RBACPolicy class for loading and managing policies
4. YAML policy parsing from policies.yaml
5. check_permission(role, tool, action, context) method
6. Scope validation (project directory for Executor, patches for Healer)
7. Human approval requirement for Healer in production
8. Permission denial handling
9. Policy hot-reloading capability
10. Integration with MCP Gateway

References:
    - PRD FR-01.3.2: RBAC for Tools
    - Definition of Done Story 6.2
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Test: Role Enum
# -----------------------------------------------------------------------------


class TestRoleEnum:
    """Tests for the Role enum defining agent roles."""

    def test_role_enum_has_planner(self) -> None:
        """Role enum should define PLANNER role."""
        from daw_agents.mcp.rbac import Role

        assert hasattr(Role, "PLANNER")
        assert Role.PLANNER.value == "planner"

    def test_role_enum_has_executor(self) -> None:
        """Role enum should define EXECUTOR role."""
        from daw_agents.mcp.rbac import Role

        assert hasattr(Role, "EXECUTOR")
        assert Role.EXECUTOR.value == "executor"

    def test_role_enum_has_validator(self) -> None:
        """Role enum should define VALIDATOR role."""
        from daw_agents.mcp.rbac import Role

        assert hasattr(Role, "VALIDATOR")
        assert Role.VALIDATOR.value == "validator"

    def test_role_enum_has_healer(self) -> None:
        """Role enum should define HEALER role."""
        from daw_agents.mcp.rbac import Role

        assert hasattr(Role, "HEALER")
        assert Role.HEALER.value == "healer"

    def test_role_from_string(self) -> None:
        """Role should be constructable from string value."""
        from daw_agents.mcp.rbac import Role

        assert Role("planner") == Role.PLANNER
        assert Role("executor") == Role.EXECUTOR
        assert Role("validator") == Role.VALIDATOR
        assert Role("healer") == Role.HEALER


# -----------------------------------------------------------------------------
# Test: Permission Model
# -----------------------------------------------------------------------------


class TestPermission:
    """Tests for the Permission model defining tool permissions."""

    def test_permission_creation(self) -> None:
        """Permission should be creatable with tool and actions."""
        from daw_agents.mcp.rbac import Permission

        perm = Permission(
            tool="read_file",
            actions=["read"],
        )

        assert perm.tool == "read_file"
        assert "read" in perm.actions

    def test_permission_with_scope(self) -> None:
        """Permission should support scope restrictions."""
        from daw_agents.mcp.rbac import Permission

        perm = Permission(
            tool="write_file",
            actions=["write"],
            scope="/projects/{project_id}",
        )

        assert perm.tool == "write_file"
        assert perm.scope == "/projects/{project_id}"

    def test_permission_with_conditions(self) -> None:
        """Permission should support conditional access."""
        from daw_agents.mcp.rbac import Permission

        perm = Permission(
            tool="write_file",
            actions=["write"],
            conditions={"requires_approval": True, "environment": ["staging", "development"]},
        )

        assert perm.conditions is not None
        assert perm.conditions["requires_approval"] is True
        assert "production" not in perm.conditions["environment"]

    def test_permission_parametric_action(self) -> None:
        """Permission should support parametric actions like query_db:SELECT."""
        from daw_agents.mcp.rbac import Permission

        perm = Permission(
            tool="query_db",
            actions=["SELECT"],
        )

        assert "SELECT" in perm.actions
        assert "DROP" not in perm.actions


# -----------------------------------------------------------------------------
# Test: RolePolicy Model
# -----------------------------------------------------------------------------


class TestRolePolicy:
    """Tests for the RolePolicy model defining permissions per role."""

    def test_role_policy_creation(self) -> None:
        """RolePolicy should be creatable with role and permissions."""
        from daw_agents.mcp.rbac import Permission, Role, RolePolicy

        policy = RolePolicy(
            role=Role.PLANNER,
            permissions=[
                Permission(tool="search", actions=["search"]),
                Permission(tool="read_file", actions=["read"]),
            ],
        )

        assert policy.role == Role.PLANNER
        assert len(policy.permissions) == 2

    def test_role_policy_has_permission(self) -> None:
        """RolePolicy should check if permission exists for a tool."""
        from daw_agents.mcp.rbac import Permission, Role, RolePolicy

        policy = RolePolicy(
            role=Role.PLANNER,
            permissions=[
                Permission(tool="search", actions=["search"]),
            ],
        )

        assert policy.has_permission("search") is True
        assert policy.has_permission("write_file") is False

    def test_role_policy_get_permission(self) -> None:
        """RolePolicy should retrieve permission for a tool."""
        from daw_agents.mcp.rbac import Permission, Role, RolePolicy

        policy = RolePolicy(
            role=Role.PLANNER,
            permissions=[
                Permission(tool="search", actions=["search"]),
            ],
        )

        perm = policy.get_permission("search")
        assert perm is not None
        assert perm.tool == "search"


# -----------------------------------------------------------------------------
# Test: RBACPolicy Class
# -----------------------------------------------------------------------------


class TestRBACPolicy:
    """Tests for the RBACPolicy class that manages all role policies."""

    def test_rbac_policy_initialization(self) -> None:
        """RBACPolicy should initialize with default policies."""
        from daw_agents.mcp.rbac import RBACPolicy

        policy = RBACPolicy()

        assert policy is not None

    def test_rbac_policy_has_all_roles(self) -> None:
        """RBACPolicy should have policies for all predefined roles."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        assert policy.get_role_policy(Role.PLANNER) is not None
        assert policy.get_role_policy(Role.EXECUTOR) is not None
        assert policy.get_role_policy(Role.VALIDATOR) is not None
        assert policy.get_role_policy(Role.HEALER) is not None

    def test_rbac_policy_load_from_yaml(self) -> None:
        """RBACPolicy should load policies from YAML file."""
        from daw_agents.mcp.rbac import RBACPolicy

        # Should load from default policies.yaml
        policy = RBACPolicy.from_yaml()

        assert policy is not None

    def test_rbac_policy_load_from_custom_yaml(self, tmp_path: Path) -> None:
        """RBACPolicy should load policies from custom YAML path."""
        from daw_agents.mcp.rbac import RBACPolicy

        yaml_content = """
roles:
  planner:
    permissions:
      - tool: search
        actions: [search]
      - tool: read_file
        actions: [read]
"""
        yaml_file = tmp_path / "custom_policies.yaml"
        yaml_file.write_text(yaml_content)

        policy = RBACPolicy.from_yaml(str(yaml_file))

        assert policy.get_role_policy("planner") is not None


# -----------------------------------------------------------------------------
# Test: check_permission Method
# -----------------------------------------------------------------------------


class TestCheckPermission:
    """Tests for the check_permission method."""

    def test_check_permission_planner_read_allowed(self) -> None:
        """Planner should be allowed to read files."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.PLANNER,
            tool="read_file",
            action="read",
        )

        assert result.allowed is True

    def test_check_permission_planner_write_denied(self) -> None:
        """Planner should NOT be allowed to write files."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.PLANNER,
            tool="write_file",
            action="write",
        )

        assert result.allowed is False
        assert "not permitted" in result.reason.lower() or "denied" in result.reason.lower()

    def test_check_permission_planner_search_allowed(self) -> None:
        """Planner should be allowed to search."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.PLANNER,
            tool="search",
            action="search",
        )

        assert result.allowed is True

    def test_check_permission_planner_query_select_allowed(self) -> None:
        """Planner should be allowed to execute SELECT queries."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.PLANNER,
            tool="query_db",
            action="SELECT",
        )

        assert result.allowed is True

    def test_check_permission_planner_query_drop_denied(self) -> None:
        """Planner should NOT be allowed to execute DROP queries."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.PLANNER,
            tool="query_db",
            action="DROP",
        )

        assert result.allowed is False

    def test_check_permission_executor_write_allowed(self) -> None:
        """Executor should be allowed to write files."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.EXECUTOR,
            tool="write_file",
            action="write",
        )

        assert result.allowed is True

    def test_check_permission_executor_git_commit_allowed(self) -> None:
        """Executor should be allowed to git commit."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.EXECUTOR,
            tool="git_commit",
            action="commit",
        )

        assert result.allowed is True

    def test_check_permission_validator_run_tests_allowed(self) -> None:
        """Validator should be allowed to run tests."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.VALIDATOR,
            tool="run_tests",
            action="run",
        )

        assert result.allowed is True

    def test_check_permission_validator_security_scan_allowed(self) -> None:
        """Validator should be allowed to run security scans."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.VALIDATOR,
            tool="security_scan",
            action="scan",
        )

        assert result.allowed is True

    def test_check_permission_validator_write_denied(self) -> None:
        """Validator should NOT be allowed to write files."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.VALIDATOR,
            tool="write_file",
            action="write",
        )

        assert result.allowed is False

    def test_check_permission_healer_read_allowed(self) -> None:
        """Healer should be allowed to read files."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy()

        result = policy.check_permission(
            role=Role.HEALER,
            tool="read_file",
            action="read",
        )

        assert result.allowed is True


# -----------------------------------------------------------------------------
# Test: Scope Validation
# -----------------------------------------------------------------------------


class TestScopeValidation:
    """Tests for scope validation in RBAC."""

    def test_executor_write_in_project_directory_allowed(self) -> None:
        """Executor write_file should be allowed in project directory."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        context = PermissionContext(
            path="/projects/my-project/src/main.py",
            project_root="/projects/my-project",
        )

        result = policy.check_permission(
            role=Role.EXECUTOR,
            tool="write_file",
            action="write",
            context=context,
        )

        assert result.allowed is True

    def test_executor_write_outside_project_denied(self) -> None:
        """Executor write_file should be denied outside project directory."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        context = PermissionContext(
            path="/etc/passwd",
            project_root="/projects/my-project",
        )

        result = policy.check_permission(
            role=Role.EXECUTOR,
            tool="write_file",
            action="write",
            context=context,
        )

        assert result.allowed is False
        assert "outside project" in result.reason.lower() or "scope" in result.reason.lower()

    def test_healer_write_patches_only(self) -> None:
        """Healer write_file should only work for patches."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        # Patch file should be allowed
        patch_context = PermissionContext(
            path="/projects/my-project/patches/fix.patch",
        )

        result = policy.check_permission(
            role=Role.HEALER,
            tool="write_file",
            action="write",
            context=patch_context,
        )

        assert result.allowed is True

    def test_healer_write_non_patch_denied(self) -> None:
        """Healer write_file should be denied for non-patch files."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        # Non-patch file should be denied
        non_patch_context = PermissionContext(
            path="/projects/my-project/src/main.py",
        )

        result = policy.check_permission(
            role=Role.HEALER,
            tool="write_file",
            action="write",
            context=non_patch_context,
        )

        assert result.allowed is False


# -----------------------------------------------------------------------------
# Test: Human Approval Requirement
# -----------------------------------------------------------------------------


class TestHumanApproval:
    """Tests for human approval requirements in RBAC."""

    def test_healer_production_requires_approval(self) -> None:
        """Healer in production should require human approval."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        context = PermissionContext(
            environment="production",
            path="/projects/my-project/patches/fix.patch",
        )

        result = policy.check_permission(
            role=Role.HEALER,
            tool="write_file",
            action="write",
            context=context,
        )

        # Should indicate approval is required
        assert result.requires_approval is True

    def test_healer_staging_no_approval_needed(self) -> None:
        """Healer in staging should NOT require approval."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        context = PermissionContext(
            environment="staging",
            path="/projects/my-project/patches/fix.patch",
        )

        result = policy.check_permission(
            role=Role.HEALER,
            tool="write_file",
            action="write",
            context=context,
        )

        assert result.requires_approval is False

    def test_healer_development_no_approval_needed(self) -> None:
        """Healer in development should NOT require approval."""
        from daw_agents.mcp.rbac import PermissionContext, RBACPolicy, Role

        policy = RBACPolicy()

        context = PermissionContext(
            environment="development",
            path="/projects/my-project/patches/fix.patch",
        )

        result = policy.check_permission(
            role=Role.HEALER,
            tool="write_file",
            action="write",
            context=context,
        )

        assert result.requires_approval is False


# -----------------------------------------------------------------------------
# Test: PermissionResult Model
# -----------------------------------------------------------------------------


class TestPermissionResult:
    """Tests for the PermissionResult model."""

    def test_permission_result_allowed(self) -> None:
        """PermissionResult should indicate allowed access."""
        from daw_agents.mcp.rbac import PermissionResult

        result = PermissionResult(
            allowed=True,
            role="planner",
            tool="search",
            action="search",
        )

        assert result.allowed is True
        assert result.role == "planner"
        assert result.tool == "search"

    def test_permission_result_denied_with_reason(self) -> None:
        """PermissionResult should provide denial reason."""
        from daw_agents.mcp.rbac import PermissionResult

        result = PermissionResult(
            allowed=False,
            role="planner",
            tool="write_file",
            action="write",
            reason="Planner role does not have write permission",
        )

        assert result.allowed is False
        assert result.reason is not None
        assert "write" in result.reason.lower()

    def test_permission_result_requires_approval(self) -> None:
        """PermissionResult should indicate if approval is required."""
        from daw_agents.mcp.rbac import PermissionResult

        result = PermissionResult(
            allowed=True,
            role="healer",
            tool="write_file",
            action="write",
            requires_approval=True,
        )

        assert result.allowed is True
        assert result.requires_approval is True


# -----------------------------------------------------------------------------
# Test: PermissionContext Model
# -----------------------------------------------------------------------------


class TestPermissionContext:
    """Tests for the PermissionContext model for contextual checks."""

    def test_permission_context_creation(self) -> None:
        """PermissionContext should be creatable with context info."""
        from daw_agents.mcp.rbac import PermissionContext

        context = PermissionContext(
            path="/projects/my-project/src/main.py",
            project_root="/projects/my-project",
            environment="development",
        )

        assert context.path == "/projects/my-project/src/main.py"
        assert context.project_root == "/projects/my-project"
        assert context.environment == "development"

    def test_permission_context_is_within_project(self) -> None:
        """PermissionContext should check if path is within project."""
        from daw_agents.mcp.rbac import PermissionContext

        context = PermissionContext(
            path="/projects/my-project/src/main.py",
            project_root="/projects/my-project",
        )

        assert context.is_within_project() is True

    def test_permission_context_is_patch_file(self) -> None:
        """PermissionContext should check if path is a patch file."""
        from daw_agents.mcp.rbac import PermissionContext

        patch_context = PermissionContext(
            path="/projects/my-project/patches/fix.patch",
        )
        assert patch_context.is_patch_file() is True

        non_patch_context = PermissionContext(
            path="/projects/my-project/src/main.py",
        )
        assert non_patch_context.is_patch_file() is False

    def test_permission_context_is_production(self) -> None:
        """PermissionContext should check if environment is production."""
        from daw_agents.mcp.rbac import PermissionContext

        prod_context = PermissionContext(
            environment="production",
        )
        assert prod_context.is_production() is True

        dev_context = PermissionContext(
            environment="development",
        )
        assert dev_context.is_production() is False


# -----------------------------------------------------------------------------
# Test: YAML Policy Parsing
# -----------------------------------------------------------------------------


class TestYAMLPolicyParsing:
    """Tests for YAML policy file parsing."""

    def test_parse_yaml_with_all_roles(self, tmp_path: Path) -> None:
        """YAML parser should handle all role definitions."""
        from daw_agents.mcp.rbac import RBACPolicy

        yaml_content = """
roles:
  planner:
    permissions:
      - tool: search
        actions: [search]
      - tool: read_file
        actions: [read]
      - tool: query_db
        actions: [SELECT]
  executor:
    permissions:
      - tool: read_file
        actions: [read]
      - tool: write_file
        actions: [write]
        scope: "{project_root}"
      - tool: git_commit
        actions: [commit]
  validator:
    permissions:
      - tool: run_tests
        actions: [run]
      - tool: security_scan
        actions: [scan]
      - tool: lint
        actions: [run]
  healer:
    permissions:
      - tool: read_file
        actions: [read]
      - tool: write_file
        actions: [write]
        scope: "patches"
        conditions:
          requires_approval_in:
            - production
"""
        yaml_file = tmp_path / "policies.yaml"
        yaml_file.write_text(yaml_content)

        policy = RBACPolicy.from_yaml(str(yaml_file))

        assert policy.get_role_policy("planner") is not None
        assert policy.get_role_policy("executor") is not None
        assert policy.get_role_policy("validator") is not None
        assert policy.get_role_policy("healer") is not None

    def test_parse_yaml_invalid_format(self, tmp_path: Path) -> None:
        """YAML parser should raise error on invalid format."""
        from daw_agents.mcp.rbac import PolicyParseError, RBACPolicy

        yaml_content = "invalid: yaml: content:"
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(PolicyParseError):
            RBACPolicy.from_yaml(str(yaml_file))

    def test_parse_yaml_missing_required_fields(self, tmp_path: Path) -> None:
        """YAML parser should validate required fields."""
        from daw_agents.mcp.rbac import PolicyParseError, RBACPolicy

        yaml_content = """
roles:
  planner:
    # Missing permissions key
    description: "Planner role"
"""
        yaml_file = tmp_path / "missing_fields.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(PolicyParseError):
            RBACPolicy.from_yaml(str(yaml_file))


# -----------------------------------------------------------------------------
# Test: Policy Hot-Reloading
# -----------------------------------------------------------------------------


class TestPolicyHotReload:
    """Tests for policy hot-reloading capability."""

    def test_reload_policies(self, tmp_path: Path) -> None:
        """RBACPolicy should support reloading policies from file."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        yaml_content = """
roles:
  planner:
    permissions:
      - tool: search
        actions: [search]
"""
        yaml_file = tmp_path / "policies.yaml"
        yaml_file.write_text(yaml_content)

        policy = RBACPolicy.from_yaml(str(yaml_file))

        # Update the file
        updated_content = """
roles:
  planner:
    permissions:
      - tool: search
        actions: [search]
      - tool: new_tool
        actions: [use]
"""
        yaml_file.write_text(updated_content)

        # Reload
        policy.reload()

        # Check new permission exists
        planner_policy = policy.get_role_policy(Role.PLANNER)
        assert planner_policy.has_permission("new_tool") is True

    def test_watch_policies_file(self, tmp_path: Path) -> None:
        """RBACPolicy should be able to watch for file changes."""
        from daw_agents.mcp.rbac import RBACPolicy

        yaml_file = tmp_path / "policies.yaml"
        yaml_file.write_text("""
roles:
  planner:
    permissions:
      - tool: search
        actions: [search]
""")

        policy = RBACPolicy.from_yaml(str(yaml_file))

        # Check that watching is supported
        assert hasattr(policy, "watch")
        assert callable(policy.watch)


# -----------------------------------------------------------------------------
# Test: Integration with MCP Gateway
# -----------------------------------------------------------------------------


class TestGatewayIntegration:
    """Tests for RBAC integration with MCP Gateway.

    Note: These tests validate that RBAC can be used alongside the gateway.
    Full gateway integration (passing rbac_policy to MCPGateway) is a future
    enhancement that will be implemented when the gateway is updated.
    """

    @pytest.mark.asyncio
    async def test_rbac_check_before_gateway(self) -> None:
        """RBAC policy can be used to check permissions before gateway call."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig
        from daw_agents.mcp.rbac import RBACPolicy, Role

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        rbac = RBACPolicy()
        gateway = MCPGateway(config=config)

        # Issue token for planner
        token = await gateway.authorize_agent(
            agent_id="planner",
            requested_scopes=["search", "read_file"],
        )

        # Check RBAC before gateway call
        rbac_result = rbac.check_permission(
            role=Role.PLANNER,
            tool="search",
            action="search",
        )

        assert rbac_result.allowed is True

        # Then validate with gateway
        result = await gateway.validate_tool_call(
            token=token.token_string,
            tool_name="search",
            params={"query": "test"},
        )

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rbac_denies_before_gateway(self) -> None:
        """RBAC policy can deny permissions before gateway call."""
        from daw_agents.mcp.gateway import MCPGateway, MCPGatewayConfig
        from daw_agents.mcp.rbac import RBACPolicy, Role

        config = MCPGatewayConfig(
            issuer="https://daw.example.com",
            audience="https://mcp.daw.example.com",
            secret_key="super-secret-key-at-least-32-chars",
        )

        rbac = RBACPolicy()
        gateway = MCPGateway(config=config)

        # Issue token for validator
        token = await gateway.authorize_agent(
            agent_id="validator",
            requested_scopes=["run_tests", "security_scan", "lint"],
        )

        # RBAC check should deny write access for validator
        rbac_result = rbac.check_permission(
            role=Role.VALIDATOR,
            tool="write_file",
            action="write",
        )

        assert rbac_result.allowed is False
        assert "not permitted" in rbac_result.reason.lower()


# -----------------------------------------------------------------------------
# Test: Exceptions
# -----------------------------------------------------------------------------


class TestRBACExceptions:
    """Tests for RBAC exception classes."""

    def test_policy_parse_error(self) -> None:
        """PolicyParseError should be properly defined."""
        from daw_agents.mcp.rbac import PolicyParseError

        error = PolicyParseError("Invalid YAML structure")
        assert "Invalid YAML structure" in str(error)

    def test_permission_denied_error(self) -> None:
        """PermissionDeniedError should be properly defined."""
        from daw_agents.mcp.rbac import PermissionDeniedError

        error = PermissionDeniedError(
            role="planner",
            tool="write_file",
            reason="Write permission not granted",
        )
        assert "planner" in str(error)
        assert "write_file" in str(error)

    def test_role_not_found_error(self) -> None:
        """RoleNotFoundError should be properly defined."""
        from daw_agents.mcp.rbac import RoleNotFoundError

        error = RoleNotFoundError("unknown_role")
        assert "unknown_role" in str(error)


# -----------------------------------------------------------------------------
# Test: Default Policy File
# -----------------------------------------------------------------------------


class TestDefaultPolicyFile:
    """Tests for the default policies.yaml file."""

    def test_default_policy_file_exists(self) -> None:
        """Default policies.yaml should exist."""
        from daw_agents.mcp.rbac import get_default_policy_path

        policy_path = get_default_policy_path()
        assert Path(policy_path).exists()

    def test_default_policy_file_is_valid(self) -> None:
        """Default policies.yaml should be valid and parseable."""
        from daw_agents.mcp.rbac import RBACPolicy

        # Should load without error
        policy = RBACPolicy.from_yaml()
        assert policy is not None

    def test_default_policy_has_all_prd_roles(self) -> None:
        """Default policies.yaml should define all PRD-specified roles."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy.from_yaml()

        # All four roles per FR-01.3.2
        assert policy.get_role_policy(Role.PLANNER) is not None
        assert policy.get_role_policy(Role.EXECUTOR) is not None
        assert policy.get_role_policy(Role.VALIDATOR) is not None
        assert policy.get_role_policy(Role.HEALER) is not None

    def test_default_planner_permissions_match_prd(self) -> None:
        """Planner permissions should match PRD FR-01.3.2."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy.from_yaml()
        planner = policy.get_role_policy(Role.PLANNER)

        # Planner: search, read_file, query_db (SELECT) - No writes
        assert planner.has_permission("search") is True
        assert planner.has_permission("read_file") is True
        assert planner.has_permission("query_db") is True
        assert planner.has_permission("write_file") is False
        assert planner.has_permission("git_commit") is False

    def test_default_executor_permissions_match_prd(self) -> None:
        """Executor permissions should match PRD FR-01.3.2."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy.from_yaml()
        executor = policy.get_role_policy(Role.EXECUTOR)

        # Executor: read_file, write_file, git_commit
        assert executor.has_permission("read_file") is True
        assert executor.has_permission("write_file") is True
        assert executor.has_permission("git_commit") is True

    def test_default_validator_permissions_match_prd(self) -> None:
        """Validator permissions should match PRD FR-01.3.2."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy.from_yaml()
        validator = policy.get_role_policy(Role.VALIDATOR)

        # Validator: run_tests, security_scan, lint - No file writes
        assert validator.has_permission("run_tests") is True
        assert validator.has_permission("security_scan") is True
        assert validator.has_permission("lint") is True
        assert validator.has_permission("write_file") is False

    def test_default_healer_permissions_match_prd(self) -> None:
        """Healer permissions should match PRD FR-01.3.2."""
        from daw_agents.mcp.rbac import RBACPolicy, Role

        policy = RBACPolicy.from_yaml()
        healer = policy.get_role_policy(Role.HEALER)

        # Healer: read_file, write_file (patches only)
        assert healer.has_permission("read_file") is True
        assert healer.has_permission("write_file") is True  # But scoped to patches
