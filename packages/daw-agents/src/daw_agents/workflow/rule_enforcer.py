"""Rule Enforcement module for coding style and linting integration.

This module implements the RuleEnforcer (RULES-001) that enforces coding standards
in the Executor workflow's Green phase. It integrates with:
- Ruff for Python linting
- ESLint for TypeScript/JavaScript linting
- .cursorrules file for custom style constraints

Key Features:
- Parse .cursorrules file for style constraints
- Integrate with Ruff (Python) and ESLint (TypeScript) for automatic linting
- Auto-fix capability for minor issues where possible
- Lint check as gate in Green phase
- Configurable rule severity levels
- Rule violation reporting

Dependencies:
- EXECUTOR-001: Developer Agent Workflow (provides the Green phase context)

Usage:
    enforcer = RuleEnforcer()
    passed, result = await enforcer.gate_check(
        Path("/path/to/src"),
        auto_fix=True,
    )
    if not passed:
        print(enforcer.generate_report(result))
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RuleSeverity(IntEnum):
    """Severity levels for lint violations.

    Higher values indicate more severe violations.
    """

    INFO = 1
    WARNING = 2
    ERROR = 3


class CursorRule(BaseModel):
    """Model for a rule defined in .cursorrules file.

    Attributes:
        name: Unique identifier for the rule
        description: Human-readable description of the rule
        severity: Severity level (default WARNING)
        pattern: Optional regex pattern for custom pattern matching
        language: Optional language filter (python, typescript, etc.)
    """

    name: str
    description: str
    severity: RuleSeverity = RuleSeverity.WARNING
    pattern: str | None = None
    language: str | None = None


class LintViolation(BaseModel):
    """Model for a single lint violation.

    Attributes:
        file_path: Path to the file with the violation
        line: Line number of the violation
        column: Column number of the violation
        code: Lint rule code (e.g., E501, no-unused-vars)
        message: Human-readable description of the violation
        severity: Severity level
        fixable: Whether this violation can be auto-fixed
        fix_suggestion: Optional suggestion for how to fix
    """

    file_path: str
    line: int
    column: int
    code: str
    message: str
    severity: RuleSeverity
    fixable: bool
    fix_suggestion: str | None = None


class LintResult(BaseModel):
    """Model for lint check result.

    Attributes:
        success: Whether the lint check passed (no errors)
        violations: List of lint violations found
        files_checked: Number of files that were checked
        auto_fixes_applied: Number of auto-fixes that were applied
    """

    success: bool
    violations: list[LintViolation] = Field(default_factory=list)
    files_checked: int = 0
    auto_fixes_applied: int = 0

    @property
    def error_count(self) -> int:
        """Count violations with ERROR severity."""
        return sum(1 for v in self.violations if v.severity == RuleSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count violations with WARNING severity."""
        return sum(1 for v in self.violations if v.severity == RuleSeverity.WARNING)


class CursorRulesParser:
    """Parser for .cursorrules files.

    Supports two formats:
    1. YAML format with explicit rule definitions
    2. Markdown format with rule descriptions
    """

    def __init__(self) -> None:
        """Initialize the parser."""
        pass

    def parse(self, path: Path) -> list[CursorRule]:
        """Parse a .cursorrules file and extract rules.

        Args:
            path: Path to the .cursorrules file

        Returns:
            List of CursorRule instances
        """
        if not path.exists():
            logger.debug("Cursorrules file not found: %s", path)
            return []

        content = path.read_text()
        if not content.strip():
            return []

        # Try YAML format first
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and "rules" in data:
                return self._parse_yaml_rules(data["rules"])
        except yaml.YAMLError:
            pass

        # Fall back to markdown format
        return self._parse_markdown_rules(content)

    def _parse_yaml_rules(self, rules_data: list[dict[str, Any]]) -> list[CursorRule]:
        """Parse rules from YAML format.

        Args:
            rules_data: List of rule dictionaries

        Returns:
            List of CursorRule instances
        """
        rules = []
        for rule_dict in rules_data:
            severity_str = rule_dict.get("severity", "warning").lower()
            severity_map = {
                "info": RuleSeverity.INFO,
                "warning": RuleSeverity.WARNING,
                "error": RuleSeverity.ERROR,
            }
            severity = severity_map.get(severity_str, RuleSeverity.WARNING)

            rule = CursorRule(
                name=rule_dict.get("name", "unnamed"),
                description=rule_dict.get("description", ""),
                severity=severity,
                pattern=rule_dict.get("pattern"),
                language=rule_dict.get("language"),
            )
            rules.append(rule)
        return rules

    def _parse_markdown_rules(self, content: str) -> list[CursorRule]:
        """Parse rules from markdown format.

        Args:
            content: Markdown content of .cursorrules file

        Returns:
            List of CursorRule instances
        """
        rules = []
        lines = content.split("\n")

        current_language: str | None = None
        for line in lines:
            # Detect language sections
            if line.startswith("## "):
                section = line[3:].strip().lower()
                if "python" in section:
                    current_language = "python"
                elif "typescript" in section or "javascript" in section:
                    current_language = "typescript"
                else:
                    current_language = None

            # Parse rule items (bullet points)
            if line.startswith("- "):
                rule_text = line[2:].strip()
                if rule_text:
                    rule_name = self._generate_rule_name(rule_text)
                    rules.append(
                        CursorRule(
                            name=rule_name,
                            description=rule_text,
                            severity=RuleSeverity.WARNING,
                            language=current_language,
                        )
                    )

        return rules

    def _generate_rule_name(self, description: str) -> str:
        """Generate a rule name from description.

        Args:
            description: Rule description text

        Returns:
            Kebab-case rule name
        """
        # Convert to lowercase and replace non-alphanumeric with dashes
        name = re.sub(r"[^a-z0-9]+", "-", description.lower())
        name = name.strip("-")[:50]  # Limit length
        return name or "unnamed-rule"


@dataclass
class RuffRunner:
    """Runner for Ruff Python linter.

    Attributes:
        config_path: Optional path to pyproject.toml or ruff.toml
        select: List of rule codes to enable
        ignore: List of rule codes to ignore
    """

    config_path: Path | None = None
    select: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)

    def is_available(self) -> bool:
        """Check if ruff is available in the system.

        Returns:
            True if ruff is installed and available
        """
        import shutil

        return shutil.which("ruff") is not None

    async def check(self, path: Path) -> LintResult:
        """Run ruff check on the given path.

        Args:
            path: File or directory to check

        Returns:
            LintResult with violations found
        """
        cmd = ["ruff", "check", "--output-format=text", str(path)]

        if self.config_path:
            cmd.extend(["--config", str(self.config_path)])

        if self.select:
            cmd.extend(["--select", ",".join(self.select)])

        if self.ignore:
            cmd.extend(["--ignore", ",".join(self.ignore)])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode("utf-8")
            violations = self._parse_output(output)

            return LintResult(
                success=process.returncode == 0,
                violations=violations,
                files_checked=1 if path.is_file() else self._count_python_files(path),
                auto_fixes_applied=0,
            )
        except FileNotFoundError as e:
            logger.error("Ruff not found: %s", e)
            raise

    async def fix(self, path: Path) -> LintResult:
        """Run ruff check with --fix on the given path.

        Args:
            path: File or directory to fix

        Returns:
            LintResult with fix summary
        """
        cmd = ["ruff", "check", "--fix", "--output-format=text", str(path)]

        if self.config_path:
            cmd.extend(["--config", str(self.config_path)])

        if self.select:
            cmd.extend(["--select", ",".join(self.select)])

        if self.ignore:
            cmd.extend(["--ignore", ",".join(self.ignore)])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode("utf-8")

            # Count fixes from output (look for "Fixed X violations")
            fixes_applied = 0
            fix_match = re.search(r"Fixed (\d+)", output)
            if fix_match:
                fixes_applied = int(fix_match.group(1))

            violations = self._parse_output(output)

            return LintResult(
                success=process.returncode == 0,
                violations=violations,
                files_checked=1 if path.is_file() else self._count_python_files(path),
                auto_fixes_applied=fixes_applied,
            )
        except FileNotFoundError as e:
            logger.error("Ruff not found: %s", e)
            raise

    def _parse_output(self, output: str) -> list[LintViolation]:
        """Parse ruff text output into violations.

        Args:
            output: Raw ruff output text

        Returns:
            List of LintViolation instances
        """
        violations = []
        # Pattern: /path/file.py:10:5: E501 Message here
        # Or: /path/file.py:10:5: E501 [*] Message here (fixable)
        pattern = re.compile(
            r"^(.+?):(\d+):(\d+):\s*([A-Z]\d+)\s*(\[\*\])?\s*(.+)$",
            re.MULTILINE,
        )

        for match in pattern.finditer(output):
            file_path, line, column, code, fixable_marker, message = match.groups()

            # Determine severity based on code prefix
            severity = RuleSeverity.WARNING
            if code.startswith("E") or code.startswith("F"):
                severity = RuleSeverity.ERROR
            elif code.startswith("W") or code.startswith("I"):
                severity = RuleSeverity.WARNING

            violations.append(
                LintViolation(
                    file_path=file_path,
                    line=int(line),
                    column=int(column),
                    code=code,
                    message=message.strip(),
                    severity=severity,
                    fixable=fixable_marker is not None,
                )
            )

        return violations

    def _count_python_files(self, path: Path) -> int:
        """Count Python files in directory.

        Args:
            path: Directory path

        Returns:
            Number of .py files
        """
        if not path.is_dir():
            return 1
        return len(list(path.rglob("*.py")))


@dataclass
class ESLintRunner:
    """Runner for ESLint TypeScript/JavaScript linter.

    Attributes:
        config_path: Optional path to eslint.config.mjs
        extensions: List of file extensions to check
    """

    config_path: Path | None = None
    extensions: list[str] = field(default_factory=lambda: [".ts", ".tsx", ".js", ".jsx"])

    def is_available(self) -> bool:
        """Check if eslint is available in the system.

        Returns:
            True if eslint is installed and available
        """
        import shutil

        # Check for npx eslint or global eslint
        return shutil.which("eslint") is not None or shutil.which("npx") is not None

    async def check(self, path: Path) -> LintResult:
        """Run eslint check on the given path.

        Args:
            path: File or directory to check

        Returns:
            LintResult with violations found
        """
        # Use npx to run local eslint or fall back to global
        cmd = ["npx", "eslint", "--format=json", str(path)]

        if self.config_path:
            cmd.extend(["--config", str(self.config_path)])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode("utf-8")
            violations = self._parse_json_output(output)

            return LintResult(
                success=process.returncode == 0,
                violations=violations,
                files_checked=1 if path.is_file() else self._count_ts_files(path),
                auto_fixes_applied=0,
            )
        except FileNotFoundError:
            logger.warning("ESLint not found, skipping TypeScript linting")
            return LintResult(success=True, violations=[], files_checked=0, auto_fixes_applied=0)

    async def fix(self, path: Path) -> LintResult:
        """Run eslint with --fix on the given path.

        Args:
            path: File or directory to fix

        Returns:
            LintResult with fix summary
        """
        cmd = ["npx", "eslint", "--fix", "--format=json", str(path)]

        if self.config_path:
            cmd.extend(["--config", str(self.config_path)])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode("utf-8")
            violations = self._parse_json_output(output)

            # ESLint doesn't report fix count directly, estimate from remaining violations
            return LintResult(
                success=process.returncode == 0,
                violations=violations,
                files_checked=1 if path.is_file() else self._count_ts_files(path),
                auto_fixes_applied=0,  # Would need before/after comparison
            )
        except FileNotFoundError:
            logger.warning("ESLint not found, skipping TypeScript fixing")
            return LintResult(success=True, violations=[], files_checked=0, auto_fixes_applied=0)

    def _parse_json_output(self, output: str) -> list[LintViolation]:
        """Parse ESLint JSON output into violations.

        Args:
            output: Raw ESLint JSON output

        Returns:
            List of LintViolation instances
        """
        violations: list[LintViolation] = []

        if not output.strip():
            return violations

        try:
            results = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Failed to parse ESLint output as JSON")
            return violations

        for file_result in results:
            file_path = file_result.get("filePath", "")
            for msg in file_result.get("messages", []):
                # ESLint severity: 1 = warning, 2 = error
                eslint_severity = msg.get("severity", 1)
                severity = RuleSeverity.ERROR if eslint_severity == 2 else RuleSeverity.WARNING

                violations.append(
                    LintViolation(
                        file_path=file_path,
                        line=msg.get("line", 0),
                        column=msg.get("column", 0),
                        code=msg.get("ruleId", "unknown"),
                        message=msg.get("message", ""),
                        severity=severity,
                        fixable="fix" in msg,
                    )
                )

        return violations

    def _count_ts_files(self, path: Path) -> int:
        """Count TypeScript/JavaScript files in directory.

        Args:
            path: Directory path

        Returns:
            Number of .ts/.tsx/.js/.jsx files
        """
        if not path.is_dir():
            return 1
        count = 0
        for ext in self.extensions:
            count += len(list(path.rglob(f"*{ext}")))
        return count


class RuleEnforcer:
    """Main class for enforcing coding rules and linting.

    Integrates Ruff (Python), ESLint (TypeScript), and custom .cursorrules
    to provide a comprehensive rule enforcement system for the Developer
    Agent's Green phase.

    Attributes:
        cursorrules_path: Path to .cursorrules file
        ruff_runner: Ruff linter runner
        eslint_runner: ESLint runner
        severity_threshold: Minimum severity to fail gate check
        exclude_patterns: Glob patterns to exclude from checking
        timeout: Timeout for lint operations in seconds
    """

    def __init__(
        self,
        cursorrules_path: Path | None = None,
        ruff_runner: RuffRunner | None = None,
        eslint_runner: ESLintRunner | None = None,
        severity_threshold: RuleSeverity = RuleSeverity.ERROR,
        exclude_patterns: list[str] | None = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the RuleEnforcer.

        Args:
            cursorrules_path: Optional path to .cursorrules file
            ruff_runner: Optional RuffRunner instance
            eslint_runner: Optional ESLintRunner instance
            severity_threshold: Minimum severity to fail gate check (default ERROR)
            exclude_patterns: Glob patterns to exclude from checking
            timeout: Timeout for lint operations in seconds
        """
        self.cursorrules_path = cursorrules_path
        self.ruff_runner = ruff_runner or RuffRunner()
        self.eslint_runner = eslint_runner or ESLintRunner()
        self.severity_threshold = severity_threshold
        self.exclude_patterns = exclude_patterns or []
        self.timeout = timeout

        self._parser = CursorRulesParser()
        self._cursor_rules: list[CursorRule] = []

        logger.info("RuleEnforcer initialized with severity threshold: %s", severity_threshold.name)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> RuleEnforcer:
        """Create RuleEnforcer from configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            RuleEnforcer instance
        """
        severity_str = config.get("severity_threshold", "error").lower()
        severity_map = {
            "info": RuleSeverity.INFO,
            "warning": RuleSeverity.WARNING,
            "error": RuleSeverity.ERROR,
        }
        severity = severity_map.get(severity_str, RuleSeverity.ERROR)

        ruff_config = config.get("ruff", {})
        ruff_runner = RuffRunner(
            select=ruff_config.get("select", []),
            ignore=ruff_config.get("ignore", []),
        )

        eslint_config = config.get("eslint", {})
        eslint_runner = ESLintRunner(
            extensions=eslint_config.get("extensions", [".ts", ".tsx", ".js", ".jsx"]),
        )

        return cls(
            ruff_runner=ruff_runner,
            eslint_runner=eslint_runner,
            severity_threshold=severity,
            exclude_patterns=config.get("exclude_patterns", []),
        )

    def load_cursor_rules(self) -> list[CursorRule]:
        """Load rules from .cursorrules file.

        Returns:
            List of CursorRule instances
        """
        if self.cursorrules_path:
            try:
                self._cursor_rules = self._parser.parse(self.cursorrules_path)
            except Exception as e:
                logger.warning("Failed to parse .cursorrules: %s", e)
                self._cursor_rules = []
        return self._cursor_rules

    async def check(
        self,
        path: Path,
        apply_cursor_rules: bool = False,
    ) -> LintResult:
        """Check the given path for lint violations.

        Args:
            path: File or directory to check
            apply_cursor_rules: Whether to apply custom .cursorrules

        Returns:
            Combined LintResult from all linters
        """
        language = self._get_language(path)
        all_violations: list[LintViolation] = []
        total_files = 0
        success = True

        # Run appropriate linter based on language/file type
        if language == "python" or (path.is_dir()):
            try:
                ruff_result = await asyncio.wait_for(
                    self.ruff_runner.check(path),
                    timeout=self.timeout,
                )
                all_violations.extend(ruff_result.violations)
                total_files += ruff_result.files_checked
                if not ruff_result.success:
                    success = False
            except TimeoutError:
                logger.error("Ruff check timed out")
                raise

        if language in ("typescript", "javascript") or (path.is_dir()):
            if self.eslint_runner.is_available():
                try:
                    eslint_result = await asyncio.wait_for(
                        self.eslint_runner.check(path),
                        timeout=self.timeout,
                    )
                    all_violations.extend(eslint_result.violations)
                    total_files += eslint_result.files_checked
                    if not eslint_result.success:
                        success = False
                except TimeoutError:
                    logger.error("ESLint check timed out")
                    raise

        # Apply cursor rules if requested
        if apply_cursor_rules and self.cursorrules_path:
            cursor_violations = await self._apply_cursor_rules(path)
            all_violations.extend(cursor_violations)

        return LintResult(
            success=success and len(all_violations) == 0,
            violations=all_violations,
            files_checked=total_files,
            auto_fixes_applied=0,
        )

    async def fix(self, path: Path) -> LintResult:
        """Apply auto-fixes to the given path.

        Args:
            path: File or directory to fix

        Returns:
            Combined LintResult with fix summary
        """
        language = self._get_language(path)
        all_violations: list[LintViolation] = []
        total_files = 0
        total_fixes = 0
        success = True

        if language == "python" or path.is_dir():
            try:
                ruff_result = await asyncio.wait_for(
                    self.ruff_runner.fix(path),
                    timeout=self.timeout,
                )
                all_violations.extend(ruff_result.violations)
                total_files += ruff_result.files_checked
                total_fixes += ruff_result.auto_fixes_applied
                if not ruff_result.success:
                    success = False
            except TimeoutError:
                logger.error("Ruff fix timed out")
                raise

        if language in ("typescript", "javascript") or path.is_dir():
            if self.eslint_runner.is_available():
                try:
                    eslint_result = await asyncio.wait_for(
                        self.eslint_runner.fix(path),
                        timeout=self.timeout,
                    )
                    all_violations.extend(eslint_result.violations)
                    total_files += eslint_result.files_checked
                    total_fixes += eslint_result.auto_fixes_applied
                    if not eslint_result.success:
                        success = False
                except TimeoutError:
                    logger.error("ESLint fix timed out")
                    raise

        return LintResult(
            success=success,
            violations=all_violations,
            files_checked=total_files,
            auto_fixes_applied=total_fixes,
        )

    async def gate_check(
        self,
        path: Path,
        auto_fix: bool = False,
    ) -> tuple[bool, LintResult]:
        """Perform gate check for Developer workflow's Green phase.

        This is the main entry point for the Executor workflow integration.
        It checks for lint violations and optionally applies auto-fixes.

        Args:
            path: File or directory to check
            auto_fix: Whether to attempt auto-fixes before checking

        Returns:
            Tuple of (passed, LintResult)
        """
        logger.info("Running gate check on: %s (auto_fix=%s)", path, auto_fix)

        if auto_fix:
            await self.fix(path)

        result = await self.check(path)

        # Determine if gate passes based on severity threshold
        # Only fail if violations at or above threshold exist
        has_blocking_violations = any(
            v.severity >= self.severity_threshold for v in result.violations
        )

        passed = not has_blocking_violations

        if passed:
            logger.info("Gate check PASSED: %d files checked", result.files_checked)
        else:
            logger.warning(
                "Gate check FAILED: %d errors, %d warnings",
                result.error_count,
                result.warning_count,
            )

        return passed, result

    async def _apply_cursor_rules(self, path: Path) -> list[LintViolation]:
        """Apply custom .cursorrules patterns to files.

        Args:
            path: File or directory to check

        Returns:
            List of violations from cursor rules
        """
        if not self._cursor_rules:
            self.load_cursor_rules()

        violations = []
        files_to_check: list[Path] = []

        if path.is_file():
            files_to_check = [path]
        else:
            files_to_check = list(path.rglob("*"))
            files_to_check = [f for f in files_to_check if f.is_file()]

        for file_path in files_to_check:
            language = self._get_language(file_path)

            for rule in self._cursor_rules:
                # Skip if rule is for different language
                if rule.language and rule.language != language:
                    continue

                # Skip if no pattern to match
                if not rule.pattern:
                    continue

                try:
                    content = file_path.read_text()
                    pattern = re.compile(rule.pattern, re.MULTILINE)

                    for i, line in enumerate(content.split("\n"), 1):
                        match = pattern.search(line)
                        if match:
                            violations.append(
                                LintViolation(
                                    file_path=str(file_path),
                                    line=i,
                                    column=match.start() + 1,
                                    code=f"cursor:{rule.name}",
                                    message=rule.description,
                                    severity=rule.severity,
                                    fixable=False,
                                )
                            )
                except Exception as e:
                    logger.warning("Failed to apply cursor rule to %s: %s", file_path, e)

        return violations

    def _get_language(self, path: Path) -> str | None:
        """Determine language from file extension.

        Args:
            path: File path

        Returns:
            Language identifier or None
        """
        extension_map = {
            ".py": "python",
            ".pyi": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
        }
        return extension_map.get(path.suffix.lower())

    def generate_report(self, result: LintResult) -> str:
        """Generate a human-readable lint report.

        Args:
            result: LintResult to format

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("LINT REPORT")
        lines.append("=" * 60)
        lines.append(f"Status: {'PASSED' if result.success else 'FAILED'}")
        lines.append(f"Files checked: {result.files_checked}")
        lines.append(f"Errors: {result.error_count}")
        lines.append(f"Warnings: {result.warning_count}")
        lines.append(f"Auto-fixes applied: {result.auto_fixes_applied}")
        lines.append("")

        if result.violations:
            lines.append("VIOLATIONS:")
            lines.append("-" * 40)

            # Group by file
            violations_by_file: dict[str, list[LintViolation]] = {}
            for v in result.violations:
                if v.file_path not in violations_by_file:
                    violations_by_file[v.file_path] = []
                violations_by_file[v.file_path].append(v)

            for file_path, violations in sorted(violations_by_file.items()):
                lines.append(f"\n{file_path}:")
                for v in sorted(violations, key=lambda x: x.line):
                    severity_str = v.severity.name
                    fixable_str = " [fixable]" if v.fixable else ""
                    lines.append(
                        f"  {v.line}:{v.column} {severity_str} {v.code}: {v.message}{fixable_str}"
                    )

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
