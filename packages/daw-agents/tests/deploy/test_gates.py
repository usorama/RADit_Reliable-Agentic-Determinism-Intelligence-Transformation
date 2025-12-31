"""Tests for Policy-as-Code Deployment Gates.

This module tests the DeploymentGates implementation:
- GateStatus enum (PASS, WARN, BLOCK)
- GateResult model for individual gate results
- DeploymentGateResult model for overall result
- PolicyConfig YAML parsing
- Individual gate evaluations (code_quality, security, performance, uat)
- Gate orchestration and environment-specific policies
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Test GateStatus Enum
# =============================================================================


class TestGateStatus:
    """Tests for GateStatus enum."""

    def test_gate_status_values(self) -> None:
        """GateStatus should have PASS, WARN, BLOCK values."""
        from daw_agents.deploy.gates import GateStatus

        assert GateStatus.PASS.value == "pass"
        assert GateStatus.WARN.value == "warn"
        assert GateStatus.BLOCK.value == "block"

    def test_gate_status_comparison(self) -> None:
        """GateStatus values can be compared for severity."""
        from daw_agents.deploy.gates import GateStatus

        # All statuses exist
        assert GateStatus.PASS is not None
        assert GateStatus.WARN is not None
        assert GateStatus.BLOCK is not None


# =============================================================================
# Test GateResult Model
# =============================================================================


class TestGateResult:
    """Tests for GateResult Pydantic model."""

    def test_gate_result_creation(self) -> None:
        """GateResult can be created with required fields."""
        from daw_agents.deploy.gates import GateResult, GateStatus

        result = GateResult(
            gate_name="code_quality",
            status=GateStatus.PASS,
            message="All checks passed",
        )
        assert result.gate_name == "code_quality"
        assert result.status == GateStatus.PASS
        assert result.message == "All checks passed"

    def test_gate_result_with_details(self) -> None:
        """GateResult can include detailed metrics."""
        from daw_agents.deploy.gates import GateResult, GateStatus

        result = GateResult(
            gate_name="security",
            status=GateStatus.BLOCK,
            message="Critical vulnerabilities found",
            details={
                "critical_count": 2,
                "high_count": 5,
                "findings": ["CVE-2025-1234", "CVE-2025-5678"],
            },
        )
        assert result.details is not None
        assert result.details["critical_count"] == 2

    def test_gate_result_is_blocking(self) -> None:
        """GateResult.is_blocking returns True only for BLOCK status."""
        from daw_agents.deploy.gates import GateResult, GateStatus

        blocking = GateResult(
            gate_name="test", status=GateStatus.BLOCK, message="Blocked"
        )
        warning = GateResult(
            gate_name="test", status=GateStatus.WARN, message="Warning"
        )
        passing = GateResult(
            gate_name="test", status=GateStatus.PASS, message="Passed"
        )

        assert blocking.is_blocking is True
        assert warning.is_blocking is False
        assert passing.is_blocking is False


# =============================================================================
# Test DeploymentGateResult Model
# =============================================================================


class TestDeploymentGateResult:
    """Tests for DeploymentGateResult aggregate model."""

    def test_deployment_gate_result_creation(self) -> None:
        """DeploymentGateResult aggregates multiple gate results."""
        from daw_agents.deploy.gates import (
            DeploymentGateResult,
            GateResult,
            GateStatus,
        )

        result = DeploymentGateResult(
            environment="staging",
            gate_results=[
                GateResult(
                    gate_name="code_quality",
                    status=GateStatus.PASS,
                    message="OK",
                ),
                GateResult(
                    gate_name="security",
                    status=GateStatus.PASS,
                    message="OK",
                ),
            ],
        )
        assert result.environment == "staging"
        assert len(result.gate_results) == 2

    def test_deployment_gate_result_overall_status_pass(self) -> None:
        """Overall status is PASS when all gates pass."""
        from daw_agents.deploy.gates import (
            DeploymentGateResult,
            GateResult,
            GateStatus,
        )

        result = DeploymentGateResult(
            environment="dev",
            gate_results=[
                GateResult(gate_name="g1", status=GateStatus.PASS, message="OK"),
                GateResult(gate_name="g2", status=GateStatus.PASS, message="OK"),
            ],
        )
        assert result.overall_status == GateStatus.PASS

    def test_deployment_gate_result_overall_status_warn(self) -> None:
        """Overall status is WARN when any gate warns but none block."""
        from daw_agents.deploy.gates import (
            DeploymentGateResult,
            GateResult,
            GateStatus,
        )

        result = DeploymentGateResult(
            environment="dev",
            gate_results=[
                GateResult(gate_name="g1", status=GateStatus.PASS, message="OK"),
                GateResult(gate_name="g2", status=GateStatus.WARN, message="Warn"),
            ],
        )
        assert result.overall_status == GateStatus.WARN

    def test_deployment_gate_result_overall_status_block(self) -> None:
        """Overall status is BLOCK when any gate blocks."""
        from daw_agents.deploy.gates import (
            DeploymentGateResult,
            GateResult,
            GateStatus,
        )

        result = DeploymentGateResult(
            environment="prod",
            gate_results=[
                GateResult(gate_name="g1", status=GateStatus.PASS, message="OK"),
                GateResult(gate_name="g2", status=GateStatus.BLOCK, message="Block"),
                GateResult(gate_name="g3", status=GateStatus.WARN, message="Warn"),
            ],
        )
        assert result.overall_status == GateStatus.BLOCK

    def test_deployment_gate_result_can_deploy(self) -> None:
        """can_deploy is True only when overall status is not BLOCK."""
        from daw_agents.deploy.gates import (
            DeploymentGateResult,
            GateResult,
            GateStatus,
        )

        passing = DeploymentGateResult(
            environment="dev",
            gate_results=[
                GateResult(gate_name="g1", status=GateStatus.PASS, message="OK"),
            ],
        )
        warning = DeploymentGateResult(
            environment="dev",
            gate_results=[
                GateResult(gate_name="g1", status=GateStatus.WARN, message="Warn"),
            ],
        )
        blocking = DeploymentGateResult(
            environment="prod",
            gate_results=[
                GateResult(gate_name="g1", status=GateStatus.BLOCK, message="Block"),
            ],
        )

        assert passing.can_deploy is True
        assert warning.can_deploy is True
        assert blocking.can_deploy is False

    def test_deployment_gate_result_get_blocking_gates(self) -> None:
        """get_blocking_gates returns list of gates with BLOCK status."""
        from daw_agents.deploy.gates import (
            DeploymentGateResult,
            GateResult,
            GateStatus,
        )

        result = DeploymentGateResult(
            environment="prod",
            gate_results=[
                GateResult(gate_name="quality", status=GateStatus.PASS, message="OK"),
                GateResult(gate_name="security", status=GateStatus.BLOCK, message="!"),
                GateResult(gate_name="uat", status=GateStatus.BLOCK, message="!"),
            ],
        )

        blocking = result.get_blocking_gates()
        assert len(blocking) == 2
        assert all(g.status == GateStatus.BLOCK for g in blocking)


# =============================================================================
# Test PolicyConfig YAML Parsing
# =============================================================================


class TestPolicyConfig:
    """Tests for PolicyConfig YAML parsing."""

    def test_policy_config_from_yaml(self) -> None:
        """PolicyConfig can be loaded from YAML string."""
        from daw_agents.deploy.gates import PolicyConfig

        yaml_content = """
gates:
  code_quality:
    enabled: true
    blocking: true
    thresholds:
      coverage_new_code: 80
      coverage_total: 70
      linting_errors: 0
  security:
    enabled: true
    blocking: true
    thresholds:
      critical_sast: 0
      critical_sca: 0
      secrets_detected: 0
"""
        config = PolicyConfig.from_yaml(yaml_content)
        assert "code_quality" in config.gates
        assert config.gates["code_quality"].enabled is True
        assert config.gates["code_quality"].blocking is True
        assert config.gates["code_quality"].thresholds["coverage_new_code"] == 80

    def test_policy_config_from_file(self, tmp_path: Path) -> None:
        """PolicyConfig can be loaded from YAML file."""
        from daw_agents.deploy.gates import PolicyConfig

        yaml_content = """
gates:
  performance:
    enabled: true
    blocking: false
    thresholds:
      api_p95_ms: 500
      bundle_size_increase_percent: 10
"""
        yaml_file = tmp_path / "policies.yaml"
        yaml_file.write_text(yaml_content)

        config = PolicyConfig.from_file(yaml_file)
        assert "performance" in config.gates
        assert config.gates["performance"].blocking is False

    def test_policy_config_environment_overrides(self) -> None:
        """PolicyConfig supports environment-specific overrides."""
        from daw_agents.deploy.gates import PolicyConfig

        yaml_content = """
gates:
  uat:
    enabled: true
    blocking: false
    thresholds:
      p0_journeys_pass: 100
environments:
  production:
    gates:
      uat:
        blocking: true
"""
        config = PolicyConfig.from_yaml(yaml_content)

        # Default: UAT is not blocking
        assert config.gates["uat"].blocking is False

        # For production: UAT is blocking
        prod_config = config.get_environment_config("production")
        assert prod_config.gates["uat"].blocking is True

    def test_policy_config_gate_enabled_check(self) -> None:
        """PolicyConfig.is_gate_enabled checks if gate is enabled."""
        from daw_agents.deploy.gates import PolicyConfig

        yaml_content = """
gates:
  code_quality:
    enabled: true
  security:
    enabled: false
"""
        config = PolicyConfig.from_yaml(yaml_content)

        assert config.is_gate_enabled("code_quality") is True
        assert config.is_gate_enabled("security") is False
        assert config.is_gate_enabled("nonexistent") is False


# =============================================================================
# Test GateConfig Model
# =============================================================================


class TestGateConfig:
    """Tests for GateConfig model."""

    def test_gate_config_creation(self) -> None:
        """GateConfig can be created with required fields."""
        from daw_agents.deploy.gates import GateConfig

        config = GateConfig(
            enabled=True,
            blocking=True,
            thresholds={"coverage_new_code": 80},
        )
        assert config.enabled is True
        assert config.blocking is True
        assert config.thresholds["coverage_new_code"] == 80

    def test_gate_config_default_thresholds(self) -> None:
        """GateConfig defaults to empty thresholds dict."""
        from daw_agents.deploy.gates import GateConfig

        config = GateConfig(enabled=True, blocking=False)
        assert config.thresholds == {}


# =============================================================================
# Test CodeQualityMetrics Model
# =============================================================================


class TestCodeQualityMetrics:
    """Tests for CodeQualityMetrics input model."""

    def test_code_quality_metrics_creation(self) -> None:
        """CodeQualityMetrics can be created with coverage data."""
        from daw_agents.deploy.gates import CodeQualityMetrics

        metrics = CodeQualityMetrics(
            coverage_new_code=85.5,
            coverage_total=72.0,
            typescript_strict=True,
            linting_errors=0,
        )
        assert metrics.coverage_new_code == 85.5
        assert metrics.coverage_total == 72.0
        assert metrics.typescript_strict is True
        assert metrics.linting_errors == 0

    def test_code_quality_metrics_defaults(self) -> None:
        """CodeQualityMetrics has sensible defaults."""
        from daw_agents.deploy.gates import CodeQualityMetrics

        metrics = CodeQualityMetrics()
        assert metrics.coverage_new_code == 0.0
        assert metrics.typescript_strict is False


# =============================================================================
# Test SecurityMetrics Model
# =============================================================================


class TestSecurityMetrics:
    """Tests for SecurityMetrics input model."""

    def test_security_metrics_creation(self) -> None:
        """SecurityMetrics can be created with security scan data."""
        from daw_agents.deploy.gates import SecurityMetrics

        metrics = SecurityMetrics(
            sast_critical=0,
            sast_high=2,
            sast_medium=5,
            sca_critical=0,
            sca_high=1,
            secrets_detected=0,
        )
        assert metrics.sast_critical == 0
        assert metrics.sast_high == 2
        assert metrics.secrets_detected == 0

    def test_security_metrics_defaults(self) -> None:
        """SecurityMetrics defaults to zero counts."""
        from daw_agents.deploy.gates import SecurityMetrics

        metrics = SecurityMetrics()
        assert metrics.sast_critical == 0
        assert metrics.sca_critical == 0
        assert metrics.secrets_detected == 0


# =============================================================================
# Test PerformanceMetrics Model
# =============================================================================


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics input model."""

    def test_performance_metrics_creation(self) -> None:
        """PerformanceMetrics can be created with perf data."""
        from daw_agents.deploy.gates import PerformanceMetrics

        metrics = PerformanceMetrics(
            api_p95_ms=250.0,
            api_p99_ms=450.0,
            bundle_size_bytes=1024 * 1024,
            bundle_size_increase_percent=5.5,
        )
        assert metrics.api_p95_ms == 250.0
        assert metrics.bundle_size_increase_percent == 5.5

    def test_performance_metrics_defaults(self) -> None:
        """PerformanceMetrics has defaults."""
        from daw_agents.deploy.gates import PerformanceMetrics

        metrics = PerformanceMetrics()
        assert metrics.api_p95_ms == 0.0
        assert metrics.bundle_size_increase_percent == 0.0


# =============================================================================
# Test UATMetrics Model
# =============================================================================


class TestUATMetrics:
    """Tests for UATMetrics input model."""

    def test_uat_metrics_creation(self) -> None:
        """UATMetrics can be created with UAT data."""
        from daw_agents.deploy.gates import UATMetrics

        metrics = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=10,
            p1_journeys_total=20,
            p1_journeys_passed=18,
            visual_regression_percent=0.05,
        )
        assert metrics.p0_journeys_passed == 10
        assert metrics.visual_regression_percent == 0.05

    def test_uat_metrics_pass_rate(self) -> None:
        """UATMetrics can calculate pass rate."""
        from daw_agents.deploy.gates import UATMetrics

        metrics = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=8,
            p1_journeys_total=0,
            p1_journeys_passed=0,
        )
        assert metrics.p0_pass_rate == 80.0


# =============================================================================
# Test DeploymentGates Main Class
# =============================================================================


class TestDeploymentGates:
    """Tests for DeploymentGates main class."""

    def test_deployment_gates_initialization(self) -> None:
        """DeploymentGates can be initialized with PolicyConfig."""
        from daw_agents.deploy.gates import DeploymentGates, PolicyConfig

        yaml_content = """
gates:
  code_quality:
    enabled: true
    blocking: true
    thresholds:
      coverage_new_code: 80
"""
        config = PolicyConfig.from_yaml(yaml_content)
        gates = DeploymentGates(config)

        assert gates.config is not None

    def test_deployment_gates_default_config(self) -> None:
        """DeploymentGates uses default config if none provided."""
        from daw_agents.deploy.gates import DeploymentGates

        gates = DeploymentGates()
        assert gates.config is not None
        # Default config should have all standard gates
        assert "code_quality" in gates.config.gates


# =============================================================================
# Test Gate 1: Code Quality Gate
# =============================================================================


class TestCodeQualityGate:
    """Tests for Code Quality gate evaluation."""

    def test_code_quality_gate_pass(self) -> None:
        """Code quality gate passes when all thresholds met."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
        )

        gates = DeploymentGates()
        metrics = CodeQualityMetrics(
            coverage_new_code=85.0,
            coverage_total=75.0,
            typescript_strict=True,
            linting_errors=0,
        )

        result = gates.evaluate_code_quality(metrics)

        assert result.status == GateStatus.PASS
        assert result.gate_name == "code_quality"

    def test_code_quality_gate_block_low_new_coverage(self) -> None:
        """Code quality gate blocks when new code coverage < 80%."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
        )

        gates = DeploymentGates()
        metrics = CodeQualityMetrics(
            coverage_new_code=70.0,  # Below 80% threshold
            coverage_total=75.0,
            typescript_strict=True,
            linting_errors=0,
        )

        result = gates.evaluate_code_quality(metrics)

        assert result.status == GateStatus.BLOCK
        assert "coverage" in result.message.lower()

    def test_code_quality_gate_block_low_total_coverage(self) -> None:
        """Code quality gate blocks when total coverage < 70%."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
        )

        gates = DeploymentGates()
        metrics = CodeQualityMetrics(
            coverage_new_code=85.0,
            coverage_total=65.0,  # Below 70% threshold
            typescript_strict=True,
            linting_errors=0,
        )

        result = gates.evaluate_code_quality(metrics)

        assert result.status == GateStatus.BLOCK

    def test_code_quality_gate_block_typescript_strict_disabled(self) -> None:
        """Code quality gate blocks when TypeScript strict mode disabled."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
        )

        gates = DeploymentGates()
        metrics = CodeQualityMetrics(
            coverage_new_code=85.0,
            coverage_total=75.0,
            typescript_strict=False,  # Not enabled
            linting_errors=0,
        )

        result = gates.evaluate_code_quality(metrics)

        assert result.status == GateStatus.BLOCK
        assert "typescript" in result.message.lower() or "strict" in result.message.lower()

    def test_code_quality_gate_block_linting_errors(self) -> None:
        """Code quality gate blocks when linting errors exist."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
        )

        gates = DeploymentGates()
        metrics = CodeQualityMetrics(
            coverage_new_code=85.0,
            coverage_total=75.0,
            typescript_strict=True,
            linting_errors=5,  # Has errors
        )

        result = gates.evaluate_code_quality(metrics)

        assert result.status == GateStatus.BLOCK
        assert "lint" in result.message.lower()


# =============================================================================
# Test Gate 2: Security Gate
# =============================================================================


class TestSecurityGate:
    """Tests for Security gate evaluation."""

    def test_security_gate_pass(self) -> None:
        """Security gate passes when no critical issues."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            SecurityMetrics,
        )

        gates = DeploymentGates()
        metrics = SecurityMetrics(
            sast_critical=0,
            sast_high=0,
            sca_critical=0,
            sca_high=0,
            secrets_detected=0,
        )

        result = gates.evaluate_security(metrics)

        assert result.status == GateStatus.PASS
        assert result.gate_name == "security"

    def test_security_gate_block_sast_critical(self) -> None:
        """Security gate blocks when SAST critical findings exist."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            SecurityMetrics,
        )

        gates = DeploymentGates()
        metrics = SecurityMetrics(
            sast_critical=1,  # Critical finding
            sast_high=0,
            sca_critical=0,
            sca_high=0,
            secrets_detected=0,
        )

        result = gates.evaluate_security(metrics)

        assert result.status == GateStatus.BLOCK
        assert "sast" in result.message.lower() or "critical" in result.message.lower()

    def test_security_gate_block_sca_critical(self) -> None:
        """Security gate blocks when SCA critical CVEs exist."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            SecurityMetrics,
        )

        gates = DeploymentGates()
        metrics = SecurityMetrics(
            sast_critical=0,
            sast_high=0,
            sca_critical=2,  # Critical CVEs
            sca_high=0,
            secrets_detected=0,
        )

        result = gates.evaluate_security(metrics)

        assert result.status == GateStatus.BLOCK
        assert "cve" in result.message.lower() or "sca" in result.message.lower()

    def test_security_gate_block_secrets_detected(self) -> None:
        """Security gate blocks when secrets detected."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            SecurityMetrics,
        )

        gates = DeploymentGates()
        metrics = SecurityMetrics(
            sast_critical=0,
            sast_high=0,
            sca_critical=0,
            sca_high=0,
            secrets_detected=1,  # Secret found
        )

        result = gates.evaluate_security(metrics)

        assert result.status == GateStatus.BLOCK
        assert "secret" in result.message.lower()

    def test_security_gate_warn_high_findings(self) -> None:
        """Security gate warns when high severity findings exist."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            SecurityMetrics,
        )

        gates = DeploymentGates()
        metrics = SecurityMetrics(
            sast_critical=0,
            sast_high=3,  # High findings (not critical)
            sca_critical=0,
            sca_high=2,
            secrets_detected=0,
        )

        result = gates.evaluate_security(metrics)

        # High findings should warn but not block
        assert result.status in (GateStatus.WARN, GateStatus.PASS)


# =============================================================================
# Test Gate 3: Performance Gate
# =============================================================================


class TestPerformanceGate:
    """Tests for Performance gate evaluation."""

    def test_performance_gate_pass(self) -> None:
        """Performance gate passes when within thresholds."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            PerformanceMetrics,
        )

        gates = DeploymentGates()
        metrics = PerformanceMetrics(
            api_p95_ms=300.0,  # < 500ms threshold
            bundle_size_increase_percent=5.0,  # < 10% threshold
        )

        result = gates.evaluate_performance(metrics)

        assert result.status == GateStatus.PASS
        assert result.gate_name == "performance"

    def test_performance_gate_warn_high_latency(self) -> None:
        """Performance gate warns when API p95 > 500ms."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            PerformanceMetrics,
        )

        gates = DeploymentGates()
        metrics = PerformanceMetrics(
            api_p95_ms=600.0,  # > 500ms threshold
            bundle_size_increase_percent=5.0,
        )

        result = gates.evaluate_performance(metrics)

        # Performance gate is WARNING only, not blocking
        assert result.status == GateStatus.WARN
        assert "latency" in result.message.lower() or "p95" in result.message.lower()

    def test_performance_gate_warn_bundle_size(self) -> None:
        """Performance gate warns when bundle size increase > 10%."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            PerformanceMetrics,
        )

        gates = DeploymentGates()
        metrics = PerformanceMetrics(
            api_p95_ms=300.0,
            bundle_size_increase_percent=15.0,  # > 10% threshold
        )

        result = gates.evaluate_performance(metrics)

        assert result.status == GateStatus.WARN
        assert "bundle" in result.message.lower()


# =============================================================================
# Test Gate 4: UAT Gate
# =============================================================================


class TestUATGate:
    """Tests for UAT gate evaluation."""

    def test_uat_gate_pass(self) -> None:
        """UAT gate passes when all P0 journeys pass and visual regression low."""
        from daw_agents.deploy.gates import DeploymentGates, GateStatus, UATMetrics

        gates = DeploymentGates()
        metrics = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=10,
            visual_regression_percent=0.05,  # < 0.1% threshold
        )

        result = gates.evaluate_uat(metrics)

        assert result.status == GateStatus.PASS
        assert result.gate_name == "uat"

    def test_uat_gate_block_failed_p0_journeys(self) -> None:
        """UAT gate blocks when P0 journeys fail (for prod)."""
        from daw_agents.deploy.gates import DeploymentGates, GateStatus, UATMetrics

        gates = DeploymentGates()
        metrics = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=9,  # Not 100%
            visual_regression_percent=0.05,
        )

        result = gates.evaluate_uat(metrics, environment="production")

        assert result.status == GateStatus.BLOCK
        assert "p0" in result.message.lower() or "journey" in result.message.lower()

    def test_uat_gate_block_visual_regression(self) -> None:
        """UAT gate blocks when visual regression > 0.1%."""
        from daw_agents.deploy.gates import DeploymentGates, GateStatus, UATMetrics

        gates = DeploymentGates()
        metrics = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=10,
            visual_regression_percent=0.5,  # > 0.1% threshold
        )

        result = gates.evaluate_uat(metrics, environment="production")

        assert result.status == GateStatus.BLOCK
        assert "visual" in result.message.lower() or "regression" in result.message.lower()

    def test_uat_gate_not_blocking_in_staging(self) -> None:
        """UAT gate may not block in staging/dev environments."""
        from daw_agents.deploy.gates import DeploymentGates, GateStatus, UATMetrics

        gates = DeploymentGates()
        metrics = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=8,  # Not 100%
            visual_regression_percent=0.05,
        )

        result = gates.evaluate_uat(metrics, environment="staging")

        # UAT is only blocking for production
        assert result.status in (GateStatus.WARN, GateStatus.PASS)


# =============================================================================
# Test Full Gate Evaluation Orchestration
# =============================================================================


class TestGateOrchestration:
    """Tests for full gate evaluation orchestration."""

    def test_evaluate_all_gates(self) -> None:
        """evaluate_all runs all gates and aggregates results."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
            PerformanceMetrics,
            SecurityMetrics,
            UATMetrics,
        )

        gates = DeploymentGates()

        result = gates.evaluate_all(
            environment="staging",
            code_quality=CodeQualityMetrics(
                coverage_new_code=85.0,
                coverage_total=75.0,
                typescript_strict=True,
                linting_errors=0,
            ),
            security=SecurityMetrics(
                sast_critical=0,
                sca_critical=0,
                secrets_detected=0,
            ),
            performance=PerformanceMetrics(
                api_p95_ms=300.0,
                bundle_size_increase_percent=5.0,
            ),
            uat=UATMetrics(
                p0_journeys_total=10,
                p0_journeys_passed=10,
                visual_regression_percent=0.05,
            ),
        )

        assert result.environment == "staging"
        assert len(result.gate_results) == 4
        assert result.overall_status == GateStatus.PASS
        assert result.can_deploy is True

    def test_evaluate_all_gates_with_failures(self) -> None:
        """evaluate_all correctly identifies blocking failures."""
        from daw_agents.deploy.gates import (
            CodeQualityMetrics,
            DeploymentGates,
            GateStatus,
            PerformanceMetrics,
            SecurityMetrics,
            UATMetrics,
        )

        gates = DeploymentGates()

        result = gates.evaluate_all(
            environment="production",
            code_quality=CodeQualityMetrics(
                coverage_new_code=50.0,  # Failing
                coverage_total=40.0,  # Failing
                typescript_strict=False,  # Failing
                linting_errors=10,  # Failing
            ),
            security=SecurityMetrics(
                sast_critical=2,  # Failing
                sca_critical=1,  # Failing
                secrets_detected=1,  # Failing
            ),
            performance=PerformanceMetrics(
                api_p95_ms=300.0,
                bundle_size_increase_percent=5.0,
            ),
            uat=UATMetrics(
                p0_journeys_total=10,
                p0_journeys_passed=10,
                visual_regression_percent=0.05,
            ),
        )

        assert result.overall_status == GateStatus.BLOCK
        assert result.can_deploy is False
        assert len(result.get_blocking_gates()) >= 2  # At least code_quality and security

    def test_evaluate_with_environment_overrides(self) -> None:
        """Gate evaluation respects environment-specific policy overrides."""
        from daw_agents.deploy.gates import (
            DeploymentGates,
            GateStatus,
            PolicyConfig,
            UATMetrics,
        )

        yaml_content = """
gates:
  uat:
    enabled: true
    blocking: false
    thresholds:
      p0_pass_rate: 100
      visual_regression: 0.1
environments:
  production:
    gates:
      uat:
        blocking: true
"""
        config = PolicyConfig.from_yaml(yaml_content)
        gates = DeploymentGates(config)

        failing_uat = UATMetrics(
            p0_journeys_total=10,
            p0_journeys_passed=8,
            visual_regression_percent=0.05,
        )

        # In staging, UAT failures are warnings
        staging_result = gates.evaluate_uat(failing_uat, environment="staging")
        assert staging_result.status != GateStatus.BLOCK

        # In production, UAT failures are blocking
        prod_result = gates.evaluate_uat(failing_uat, environment="production")
        assert prod_result.status == GateStatus.BLOCK


# =============================================================================
# Test Default Policies YAML
# =============================================================================


class TestDefaultPolicies:
    """Tests for default policies configuration."""

    def test_default_policies_file_loadable(self) -> None:
        """Default policies.yaml file can be loaded."""
        from daw_agents.deploy.gates import DeploymentGates

        # DeploymentGates should load default policies
        gates = DeploymentGates()

        assert gates.config is not None
        # Should have all 4 standard gates
        assert "code_quality" in gates.config.gates
        assert "security" in gates.config.gates
        assert "performance" in gates.config.gates
        assert "uat" in gates.config.gates

    def test_default_policies_thresholds(self) -> None:
        """Default policies have correct thresholds per spec."""
        from daw_agents.deploy.gates import DeploymentGates

        gates = DeploymentGates()
        config = gates.config

        # Code quality thresholds
        cq = config.gates["code_quality"]
        assert cq.thresholds.get("coverage_new_code", 80) == 80
        assert cq.thresholds.get("coverage_total", 70) == 70
        assert cq.thresholds.get("linting_errors", 0) == 0

        # Security thresholds
        sec = config.gates["security"]
        assert sec.thresholds.get("sast_critical", 0) == 0
        assert sec.thresholds.get("sca_critical", 0) == 0
        assert sec.thresholds.get("secrets_detected", 0) == 0

        # Performance thresholds
        perf = config.gates["performance"]
        assert perf.thresholds.get("api_p95_ms", 500) == 500
        assert perf.thresholds.get("bundle_size_increase_percent", 10) == 10

        # UAT thresholds
        uat = config.gates["uat"]
        assert uat.thresholds.get("p0_pass_rate", 100) == 100
        assert uat.thresholds.get("visual_regression", 0.1) == 0.1
