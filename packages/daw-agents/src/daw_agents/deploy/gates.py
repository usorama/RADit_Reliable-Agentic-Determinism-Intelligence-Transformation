"""Policy-as-Code Deployment Gates implementation.

This module implements codified deployment policies that are enforced
automatically before allowing deployments to proceed.

Gates:
- Gate 1 (Code Quality - BLOCKING): Test coverage, TypeScript strict, linting
- Gate 2 (Security - BLOCKING): SAST, SCA, secrets detection
- Gate 3 (Performance - WARNING): API latency, bundle size
- Gate 4 (UAT - BLOCKING for prod): P0 journeys, visual regression

Each gate evaluates metrics against configurable thresholds and returns
a GateResult with PASS, WARN, or BLOCK status.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class GateStatus(Enum):
    """Status of a deployment gate evaluation.

    Values:
        PASS: Gate passed, deployment can proceed
        WARN: Gate has warnings but deployment can proceed
        BLOCK: Gate failed, deployment is blocked
    """

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


# =============================================================================
# Gate Result Models
# =============================================================================


class GateResult(BaseModel):
    """Result from evaluating a single deployment gate.

    Attributes:
        gate_name: Name of the gate (e.g., 'code_quality', 'security')
        status: Evaluation result (PASS, WARN, BLOCK)
        message: Human-readable explanation of the result
        details: Optional dict with detailed metrics/findings
    """

    gate_name: str
    status: GateStatus
    message: str
    details: dict[str, Any] | None = None

    @property
    def is_blocking(self) -> bool:
        """Check if this gate result is blocking deployment."""
        return self.status == GateStatus.BLOCK


class DeploymentGateResult(BaseModel):
    """Aggregate result from all deployment gates.

    Attributes:
        environment: Target deployment environment (dev/staging/production)
        gate_results: List of individual gate results
    """

    environment: str
    gate_results: list[GateResult] = Field(default_factory=list)

    @property
    def overall_status(self) -> GateStatus:
        """Compute overall status from all gate results.

        Returns BLOCK if any gate blocks, WARN if any warns, else PASS.
        """
        if any(r.status == GateStatus.BLOCK for r in self.gate_results):
            return GateStatus.BLOCK
        if any(r.status == GateStatus.WARN for r in self.gate_results):
            return GateStatus.WARN
        return GateStatus.PASS

    @property
    def can_deploy(self) -> bool:
        """Check if deployment can proceed.

        Returns True if overall status is not BLOCK.
        """
        return self.overall_status != GateStatus.BLOCK

    def get_blocking_gates(self) -> list[GateResult]:
        """Get list of gates that are blocking deployment."""
        return [r for r in self.gate_results if r.status == GateStatus.BLOCK]


# =============================================================================
# Policy Configuration Models
# =============================================================================


class GateConfig(BaseModel):
    """Configuration for a single deployment gate.

    Attributes:
        enabled: Whether this gate is enabled
        blocking: Whether failures block deployment
        thresholds: Dict of threshold values for this gate
    """

    enabled: bool = True
    blocking: bool = True
    thresholds: dict[str, Any] = Field(default_factory=dict)


class PolicyConfig(BaseModel):
    """Policy configuration loaded from YAML.

    Attributes:
        gates: Dict of gate name -> GateConfig
        environments: Optional environment-specific overrides
    """

    gates: dict[str, GateConfig] = Field(default_factory=dict)
    environments: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> PolicyConfig:
        """Parse PolicyConfig from YAML string.

        Args:
            yaml_content: YAML configuration string

        Returns:
            PolicyConfig instance
        """
        data = yaml.safe_load(yaml_content)
        gates_data = data.get("gates", {})
        environments_data = data.get("environments", {})

        gates = {}
        for name, config in gates_data.items():
            gates[name] = GateConfig(
                enabled=config.get("enabled", True),
                blocking=config.get("blocking", True),
                thresholds=config.get("thresholds", {}),
            )

        return cls(gates=gates, environments=environments_data)

    @classmethod
    def from_file(cls, path: Path) -> PolicyConfig:
        """Load PolicyConfig from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            PolicyConfig instance
        """
        content = path.read_text()
        return cls.from_yaml(content)

    def get_environment_config(self, environment: str) -> PolicyConfig:
        """Get config with environment-specific overrides applied.

        Args:
            environment: Target environment name

        Returns:
            PolicyConfig with overrides applied
        """
        if environment not in self.environments:
            return self

        # Deep copy to avoid modifying original
        new_config = deepcopy(self)
        env_overrides = self.environments[environment]

        # Apply gate overrides
        if "gates" in env_overrides:
            for gate_name, gate_overrides in env_overrides["gates"].items():
                if gate_name in new_config.gates:
                    gate = new_config.gates[gate_name]
                    if "enabled" in gate_overrides:
                        gate.enabled = gate_overrides["enabled"]
                    if "blocking" in gate_overrides:
                        gate.blocking = gate_overrides["blocking"]
                    if "thresholds" in gate_overrides:
                        gate.thresholds.update(gate_overrides["thresholds"])

        return new_config

    def is_gate_enabled(self, gate_name: str) -> bool:
        """Check if a gate is enabled.

        Args:
            gate_name: Name of the gate

        Returns:
            True if gate exists and is enabled
        """
        gate = self.gates.get(gate_name)
        return gate is not None and gate.enabled


# =============================================================================
# Metrics Input Models
# =============================================================================


class CodeQualityMetrics(BaseModel):
    """Metrics for code quality gate evaluation.

    Attributes:
        coverage_new_code: Test coverage % for new code (0-100)
        coverage_total: Total test coverage % (0-100)
        typescript_strict: Whether TypeScript strict mode is enabled
        linting_errors: Count of linting errors
    """

    coverage_new_code: float = 0.0
    coverage_total: float = 0.0
    typescript_strict: bool = False
    linting_errors: int = 0


class SecurityMetrics(BaseModel):
    """Metrics for security gate evaluation.

    Attributes:
        sast_critical: Count of critical SAST findings
        sast_high: Count of high severity SAST findings
        sast_medium: Count of medium severity SAST findings
        sca_critical: Count of critical SCA CVEs
        sca_high: Count of high severity SCA CVEs
        secrets_detected: Count of detected secrets
    """

    sast_critical: int = 0
    sast_high: int = 0
    sast_medium: int = 0
    sca_critical: int = 0
    sca_high: int = 0
    secrets_detected: int = 0


class PerformanceMetrics(BaseModel):
    """Metrics for performance gate evaluation.

    Attributes:
        api_p95_ms: API response time p95 in milliseconds
        api_p99_ms: API response time p99 in milliseconds
        bundle_size_bytes: Total bundle size in bytes
        bundle_size_increase_percent: Bundle size increase from baseline (%)
    """

    api_p95_ms: float = 0.0
    api_p99_ms: float = 0.0
    bundle_size_bytes: int = 0
    bundle_size_increase_percent: float = 0.0


class UATMetrics(BaseModel):
    """Metrics for UAT gate evaluation.

    Attributes:
        p0_journeys_total: Total number of P0 user journeys
        p0_journeys_passed: Number of P0 journeys that passed
        p1_journeys_total: Total number of P1 user journeys
        p1_journeys_passed: Number of P1 journeys that passed
        visual_regression_percent: Visual regression difference (%)
    """

    p0_journeys_total: int = 0
    p0_journeys_passed: int = 0
    p1_journeys_total: int = 0
    p1_journeys_passed: int = 0
    visual_regression_percent: float = 0.0

    @property
    def p0_pass_rate(self) -> float:
        """Calculate P0 journey pass rate."""
        if self.p0_journeys_total == 0:
            return 100.0
        return (self.p0_journeys_passed / self.p0_journeys_total) * 100


# =============================================================================
# Default Policy Configuration
# =============================================================================


DEFAULT_POLICY_YAML = """
gates:
  code_quality:
    enabled: true
    blocking: true
    thresholds:
      coverage_new_code: 80
      coverage_total: 70
      linting_errors: 0
      typescript_strict: true
  security:
    enabled: true
    blocking: true
    thresholds:
      sast_critical: 0
      sca_critical: 0
      secrets_detected: 0
  performance:
    enabled: true
    blocking: false
    thresholds:
      api_p95_ms: 500
      bundle_size_increase_percent: 10
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


# =============================================================================
# Deployment Gates Main Class
# =============================================================================


class DeploymentGates:
    """Policy-as-code deployment gates evaluator.

    Evaluates deployment readiness against configured policy gates.
    Each gate checks specific metrics against thresholds and returns
    a PASS, WARN, or BLOCK status.

    Example:
        gates = DeploymentGates()
        result = gates.evaluate_all(
            environment="production",
            code_quality=CodeQualityMetrics(coverage_new_code=85.0, ...),
            security=SecurityMetrics(sast_critical=0, ...),
            ...
        )
        if result.can_deploy:
            deploy()
    """

    def __init__(self, config: PolicyConfig | None = None) -> None:
        """Initialize DeploymentGates with policy configuration.

        Args:
            config: Optional PolicyConfig. Uses default if not provided.
        """
        if config is None:
            config = PolicyConfig.from_yaml(DEFAULT_POLICY_YAML)
        self.config = config
        logger.info("DeploymentGates initialized with %d gates", len(config.gates))

    def _get_threshold(
        self, gate_name: str, threshold_name: str, default: Any
    ) -> Any:
        """Get threshold value from config with default fallback.

        Args:
            gate_name: Name of the gate
            threshold_name: Name of the threshold
            default: Default value if not configured

        Returns:
            Configured threshold value or default
        """
        gate = self.config.gates.get(gate_name)
        if gate is None:
            return default
        return gate.thresholds.get(threshold_name, default)

    def evaluate_code_quality(
        self, metrics: CodeQualityMetrics
    ) -> GateResult:
        """Evaluate code quality gate.

        Checks:
        - Test coverage >= 80% for new code
        - Test coverage >= 70% total
        - TypeScript strict mode enabled
        - 0 linting errors

        Args:
            metrics: Code quality metrics to evaluate

        Returns:
            GateResult with status and message
        """
        issues: list[str] = []

        # Check new code coverage
        threshold_new = self._get_threshold("code_quality", "coverage_new_code", 80)
        if metrics.coverage_new_code < threshold_new:
            issues.append(
                f"New code coverage {metrics.coverage_new_code:.1f}% "
                f"< {threshold_new}% threshold"
            )

        # Check total coverage
        threshold_total = self._get_threshold("code_quality", "coverage_total", 70)
        if metrics.coverage_total < threshold_total:
            issues.append(
                f"Total coverage {metrics.coverage_total:.1f}% "
                f"< {threshold_total}% threshold"
            )

        # Check TypeScript strict mode
        if not metrics.typescript_strict:
            issues.append("TypeScript strict mode is not enabled")

        # Check linting errors
        threshold_lint = self._get_threshold("code_quality", "linting_errors", 0)
        if metrics.linting_errors > threshold_lint:
            issues.append(
                f"{metrics.linting_errors} linting errors found "
                f"(threshold: {threshold_lint})"
            )

        if issues:
            return GateResult(
                gate_name="code_quality",
                status=GateStatus.BLOCK,
                message="; ".join(issues),
                details={
                    "coverage_new_code": metrics.coverage_new_code,
                    "coverage_total": metrics.coverage_total,
                    "typescript_strict": metrics.typescript_strict,
                    "linting_errors": metrics.linting_errors,
                },
            )

        return GateResult(
            gate_name="code_quality",
            status=GateStatus.PASS,
            message="All code quality checks passed",
            details={
                "coverage_new_code": metrics.coverage_new_code,
                "coverage_total": metrics.coverage_total,
            },
        )

    def evaluate_security(self, metrics: SecurityMetrics) -> GateResult:
        """Evaluate security gate.

        Checks:
        - 0 SAST critical findings
        - 0 SCA critical CVEs
        - 0 secrets detected

        Args:
            metrics: Security metrics to evaluate

        Returns:
            GateResult with status and message
        """
        blocking_issues: list[str] = []
        warning_issues: list[str] = []

        # Check SAST critical
        threshold_sast = self._get_threshold("security", "sast_critical", 0)
        if metrics.sast_critical > threshold_sast:
            blocking_issues.append(
                f"{metrics.sast_critical} critical SAST findings found"
            )

        # Check SCA critical
        threshold_sca = self._get_threshold("security", "sca_critical", 0)
        if metrics.sca_critical > threshold_sca:
            blocking_issues.append(
                f"{metrics.sca_critical} critical SCA CVEs found"
            )

        # Check secrets
        threshold_secrets = self._get_threshold("security", "secrets_detected", 0)
        if metrics.secrets_detected > threshold_secrets:
            blocking_issues.append(
                f"{metrics.secrets_detected} secrets detected in codebase"
            )

        # Check high severity (warnings only)
        if metrics.sast_high > 0:
            warning_issues.append(f"{metrics.sast_high} high severity SAST findings")
        if metrics.sca_high > 0:
            warning_issues.append(f"{metrics.sca_high} high severity CVEs")

        if blocking_issues:
            return GateResult(
                gate_name="security",
                status=GateStatus.BLOCK,
                message="; ".join(blocking_issues),
                details={
                    "sast_critical": metrics.sast_critical,
                    "sca_critical": metrics.sca_critical,
                    "secrets_detected": metrics.secrets_detected,
                },
            )

        if warning_issues:
            return GateResult(
                gate_name="security",
                status=GateStatus.WARN,
                message="; ".join(warning_issues),
                details={
                    "sast_high": metrics.sast_high,
                    "sca_high": metrics.sca_high,
                },
            )

        return GateResult(
            gate_name="security",
            status=GateStatus.PASS,
            message="All security checks passed",
        )

    def evaluate_performance(self, metrics: PerformanceMetrics) -> GateResult:
        """Evaluate performance gate (WARNING only, not blocking).

        Checks:
        - API p95 < 500ms
        - Bundle size increase < 10%

        Args:
            metrics: Performance metrics to evaluate

        Returns:
            GateResult with status and message
        """
        warnings: list[str] = []

        # Check API latency
        threshold_p95 = self._get_threshold("performance", "api_p95_ms", 500)
        if metrics.api_p95_ms > threshold_p95:
            warnings.append(
                f"API p95 latency {metrics.api_p95_ms:.0f}ms "
                f"> {threshold_p95}ms threshold"
            )

        # Check bundle size increase
        threshold_bundle = self._get_threshold(
            "performance", "bundle_size_increase_percent", 10
        )
        if metrics.bundle_size_increase_percent > threshold_bundle:
            warnings.append(
                f"Bundle size increased by {metrics.bundle_size_increase_percent:.1f}% "
                f"> {threshold_bundle}% threshold"
            )

        if warnings:
            return GateResult(
                gate_name="performance",
                status=GateStatus.WARN,
                message="; ".join(warnings),
                details={
                    "api_p95_ms": metrics.api_p95_ms,
                    "bundle_size_increase_percent": metrics.bundle_size_increase_percent,
                },
            )

        return GateResult(
            gate_name="performance",
            status=GateStatus.PASS,
            message="All performance checks passed",
            details={
                "api_p95_ms": metrics.api_p95_ms,
                "bundle_size_increase_percent": metrics.bundle_size_increase_percent,
            },
        )

    def evaluate_uat(
        self, metrics: UATMetrics, environment: str = "staging"
    ) -> GateResult:
        """Evaluate UAT gate.

        Checks:
        - All P0 user journeys pass
        - Visual regression < 0.1%

        Blocking behavior depends on environment (blocking for production).

        Args:
            metrics: UAT metrics to evaluate
            environment: Target environment (affects blocking behavior)

        Returns:
            GateResult with status and message
        """
        # Get environment-specific config
        env_config = self.config.get_environment_config(environment)
        uat_gate = env_config.gates.get("uat")
        is_blocking = uat_gate.blocking if uat_gate else False

        issues: list[str] = []

        # Check P0 journeys
        threshold_p0 = self._get_threshold("uat", "p0_pass_rate", 100)
        if metrics.p0_pass_rate < threshold_p0:
            issues.append(
                f"P0 journey pass rate {metrics.p0_pass_rate:.1f}% "
                f"< {threshold_p0}% threshold "
                f"({metrics.p0_journeys_passed}/{metrics.p0_journeys_total})"
            )

        # Check visual regression
        threshold_visual = self._get_threshold("uat", "visual_regression", 0.1)
        if metrics.visual_regression_percent > threshold_visual:
            issues.append(
                f"Visual regression {metrics.visual_regression_percent:.2f}% "
                f"> {threshold_visual}% threshold"
            )

        if issues:
            status = GateStatus.BLOCK if is_blocking else GateStatus.WARN
            return GateResult(
                gate_name="uat",
                status=status,
                message="; ".join(issues),
                details={
                    "p0_pass_rate": metrics.p0_pass_rate,
                    "visual_regression_percent": metrics.visual_regression_percent,
                    "environment": environment,
                    "is_blocking": is_blocking,
                },
            )

        return GateResult(
            gate_name="uat",
            status=GateStatus.PASS,
            message="All UAT checks passed",
            details={
                "p0_pass_rate": metrics.p0_pass_rate,
                "visual_regression_percent": metrics.visual_regression_percent,
            },
        )

    def evaluate_all(
        self,
        environment: str,
        code_quality: CodeQualityMetrics,
        security: SecurityMetrics,
        performance: PerformanceMetrics,
        uat: UATMetrics,
    ) -> DeploymentGateResult:
        """Evaluate all deployment gates.

        Args:
            environment: Target deployment environment
            code_quality: Code quality metrics
            security: Security metrics
            performance: Performance metrics
            uat: UAT metrics

        Returns:
            DeploymentGateResult with all gate results aggregated
        """
        results: list[GateResult] = []

        # Evaluate each gate if enabled
        if self.config.is_gate_enabled("code_quality"):
            results.append(self.evaluate_code_quality(code_quality))

        if self.config.is_gate_enabled("security"):
            results.append(self.evaluate_security(security))

        if self.config.is_gate_enabled("performance"):
            results.append(self.evaluate_performance(performance))

        if self.config.is_gate_enabled("uat"):
            results.append(self.evaluate_uat(uat, environment=environment))

        return DeploymentGateResult(
            environment=environment,
            gate_results=results,
        )
