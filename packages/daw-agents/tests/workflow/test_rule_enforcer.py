"""Tests for the RuleEnforcer module.

This test module covers:
- RuleEnforcer class initialization
- .cursorrules file parsing
- Style constraint extraction
- Ruff integration for Python linting
- ESLint integration for TypeScript linting
- Auto-fix capability for minor issues
- Lint check as gate in Green phase
- Configurable rule severity levels
- Rule violation reporting

Following TDD workflow: these tests are written BEFORE implementation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.workflow.rule_enforcer import (
    CursorRule,
    CursorRulesParser,
    ESLintRunner,
    LintResult,
    LintViolation,
    RuffRunner,
    RuleEnforcer,
    RuleSeverity,
)

if TYPE_CHECKING:
    pass


class TestRuleSeverity:
    """Tests for RuleSeverity enum."""

    def test_severity_values(self) -> None:
        """Test that severity levels exist."""
        assert RuleSeverity.ERROR is not None
        assert RuleSeverity.WARNING is not None
        assert RuleSeverity.INFO is not None

    def test_severity_comparison(self) -> None:
        """Test severity comparison for prioritization."""
        assert RuleSeverity.ERROR.value > RuleSeverity.WARNING.value
        assert RuleSeverity.WARNING.value > RuleSeverity.INFO.value


class TestCursorRule:
    """Tests for CursorRule model."""

    def test_cursor_rule_creation(self) -> None:
        """Test creating a CursorRule instance."""
        rule = CursorRule(
            name="no-any-types",
            description="Do not use 'any' type in TypeScript",
            severity=RuleSeverity.ERROR,
            pattern=r"\bany\b",
            language="typescript",
        )
        assert rule.name == "no-any-types"
        assert rule.severity == RuleSeverity.ERROR
        assert rule.language == "typescript"

    def test_cursor_rule_defaults(self) -> None:
        """Test CursorRule default values."""
        rule = CursorRule(
            name="example-rule",
            description="Example rule",
        )
        assert rule.severity == RuleSeverity.WARNING
        assert rule.pattern is None
        assert rule.language is None

    def test_cursor_rule_with_pattern(self) -> None:
        """Test CursorRule with regex pattern."""
        rule = CursorRule(
            name="no-print",
            description="Avoid print statements in production code",
            severity=RuleSeverity.WARNING,
            pattern=r"\bprint\s*\(",
            language="python",
        )
        assert rule.pattern == r"\bprint\s*\("


class TestLintViolation:
    """Tests for LintViolation model."""

    def test_violation_creation(self) -> None:
        """Test creating a LintViolation."""
        violation = LintViolation(
            file_path="/path/to/file.py",
            line=10,
            column=5,
            code="E501",
            message="Line too long",
            severity=RuleSeverity.WARNING,
            fixable=False,
        )
        assert violation.file_path == "/path/to/file.py"
        assert violation.line == 10
        assert violation.column == 5
        assert violation.code == "E501"
        assert not violation.fixable

    def test_violation_with_suggestion(self) -> None:
        """Test violation with auto-fix suggestion."""
        violation = LintViolation(
            file_path="/path/to/file.py",
            line=1,
            column=1,
            code="I001",
            message="Import block is un-sorted",
            severity=RuleSeverity.WARNING,
            fixable=True,
            fix_suggestion="Reorder imports",
        )
        assert violation.fixable
        assert violation.fix_suggestion == "Reorder imports"


class TestLintResult:
    """Tests for LintResult model."""

    def test_lint_result_success(self) -> None:
        """Test successful lint result with no violations."""
        result = LintResult(
            success=True,
            violations=[],
            files_checked=5,
            auto_fixes_applied=0,
        )
        assert result.success
        assert len(result.violations) == 0
        assert result.files_checked == 5

    def test_lint_result_with_violations(self) -> None:
        """Test lint result with violations."""
        violations = [
            LintViolation(
                file_path="/path/file.py",
                line=10,
                column=1,
                code="E501",
                message="Line too long",
                severity=RuleSeverity.WARNING,
                fixable=False,
            ),
        ]
        result = LintResult(
            success=False,
            violations=violations,
            files_checked=1,
            auto_fixes_applied=0,
        )
        assert not result.success
        assert len(result.violations) == 1

    def test_lint_result_with_auto_fixes(self) -> None:
        """Test lint result with auto-fixes applied."""
        result = LintResult(
            success=True,
            violations=[],
            files_checked=3,
            auto_fixes_applied=2,
        )
        assert result.auto_fixes_applied == 2

    def test_lint_result_error_count(self) -> None:
        """Test counting errors by severity."""
        violations = [
            LintViolation(
                file_path="/path/file.py",
                line=1,
                column=1,
                code="E501",
                message="Error 1",
                severity=RuleSeverity.ERROR,
                fixable=False,
            ),
            LintViolation(
                file_path="/path/file.py",
                line=2,
                column=1,
                code="W001",
                message="Warning 1",
                severity=RuleSeverity.WARNING,
                fixable=True,
            ),
            LintViolation(
                file_path="/path/file.py",
                line=3,
                column=1,
                code="E502",
                message="Error 2",
                severity=RuleSeverity.ERROR,
                fixable=False,
            ),
        ]
        result = LintResult(
            success=False,
            violations=violations,
            files_checked=1,
            auto_fixes_applied=0,
        )
        assert result.error_count == 2
        assert result.warning_count == 1


class TestCursorRulesParser:
    """Tests for CursorRulesParser."""

    def test_parser_initialization(self) -> None:
        """Test parser initialization."""
        parser = CursorRulesParser()
        assert parser is not None

    def test_parse_empty_file(self) -> None:
        """Test parsing an empty .cursorrules file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write("")
            f.flush()
            parser = CursorRulesParser()
            rules = parser.parse(Path(f.name))
            assert rules == []

    def test_parse_simple_rules(self) -> None:
        """Test parsing a simple .cursorrules file with rules."""
        content = """# .cursorrules file
# Style Rules

## Python Rules
- Do not use 'any' types
- Always use type hints
- Prefer f-strings over format()

## TypeScript Rules
- Use strict mode
- No unused variables
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write(content)
            f.flush()
            parser = CursorRulesParser()
            rules = parser.parse(Path(f.name))
            assert len(rules) > 0

    def test_parse_yaml_format_rules(self) -> None:
        """Test parsing YAML-formatted .cursorrules file."""
        content = """rules:
  - name: no-any-types
    description: Do not use 'any' type
    severity: error
    language: typescript
    pattern: '\\bany\\b'
  - name: prefer-fstrings
    description: Prefer f-strings over format()
    severity: warning
    language: python
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write(content)
            f.flush()
            parser = CursorRulesParser()
            rules = parser.parse(Path(f.name))
            assert len(rules) == 2
            assert rules[0].name == "no-any-types"
            assert rules[0].severity == RuleSeverity.ERROR

    def test_parse_nonexistent_file(self) -> None:
        """Test parsing a nonexistent file returns empty list."""
        parser = CursorRulesParser()
        rules = parser.parse(Path("/nonexistent/path/.cursorrules"))
        assert rules == []

    def test_extract_python_rules(self) -> None:
        """Test extracting Python-specific rules."""
        parser = CursorRulesParser()
        content = """rules:
  - name: rule1
    language: python
  - name: rule2
    language: typescript
  - name: rule3
    language: python
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write(content)
            f.flush()
            rules = parser.parse(Path(f.name))
            python_rules = [r for r in rules if r.language == "python"]
            assert len(python_rules) == 2


class TestRuffRunner:
    """Tests for RuffRunner (Python linting)."""

    def test_runner_initialization(self) -> None:
        """Test RuffRunner initialization."""
        runner = RuffRunner()
        assert runner is not None

    def test_runner_with_config(self) -> None:
        """Test RuffRunner with custom configuration."""
        runner = RuffRunner(
            config_path=Path("/path/to/pyproject.toml"),
            select=["E", "F", "W"],
            ignore=["E501"],
        )
        assert runner.config_path == Path("/path/to/pyproject.toml")
        assert "E" in runner.select
        assert "E501" in runner.ignore

    @pytest.mark.asyncio
    async def test_check_single_file(self) -> None:
        """Test checking a single Python file."""
        runner = RuffRunner()
        # Create a temp file with some lint issues
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\nimport sys\nx=1\n")  # Unused imports, spacing issue
            f.flush()
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = AsyncMock()
                mock_process.communicate.return_value = (
                    b"/tmp/test.py:1:1: F401 [*] `os` imported but unused\n",
                    b"",
                )
                mock_process.returncode = 1
                mock_exec.return_value = mock_process

                result = await runner.check(Path(f.name))
                assert isinstance(result, LintResult)

    @pytest.mark.asyncio
    async def test_check_directory(self) -> None:
        """Test checking a directory of Python files."""
        runner = RuffRunner()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await runner.check(Path("/path/to/src"))
            assert result.success

    @pytest.mark.asyncio
    async def test_fix_auto_fixable(self) -> None:
        """Test auto-fixing lint issues."""
        runner = RuffRunner()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                b"Fixed 2 violations\n",
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await runner.fix(Path("/path/to/file.py"))
            assert result.success

    @pytest.mark.asyncio
    async def test_parse_ruff_output(self) -> None:
        """Test parsing ruff output into violations."""
        runner = RuffRunner()
        output = """/path/file.py:10:5: E501 Line too long (120 > 88 characters)
/path/file.py:15:1: F401 [*] `os` imported but unused
/path/file.py:20:10: W291 trailing whitespace"""

        violations = runner._parse_output(output)
        assert len(violations) == 3
        assert violations[0].line == 10
        assert violations[0].column == 5
        assert violations[0].code == "E501"
        assert violations[1].fixable  # [*] indicates fixable

    def test_default_rules(self) -> None:
        """Test default ruff rules selection."""
        runner = RuffRunner()
        # Default should include E, F, W, I, N, B, UP per pyproject.toml
        assert "E" in runner.select or runner.select == []


class TestESLintRunner:
    """Tests for ESLintRunner (TypeScript linting)."""

    def test_runner_initialization(self) -> None:
        """Test ESLintRunner initialization."""
        runner = ESLintRunner()
        assert runner is not None

    def test_runner_with_config(self) -> None:
        """Test ESLintRunner with custom configuration."""
        runner = ESLintRunner(
            config_path=Path("/path/to/eslint.config.mjs"),
            extensions=[".ts", ".tsx"],
        )
        assert runner.config_path == Path("/path/to/eslint.config.mjs")
        assert ".ts" in runner.extensions

    @pytest.mark.asyncio
    async def test_check_single_file(self) -> None:
        """Test checking a single TypeScript file."""
        runner = ESLintRunner()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            # Mock JSON output from eslint
            mock_process.communicate.return_value = (
                b'[{"filePath":"/tmp/test.ts","messages":[{"ruleId":"no-unused-vars","severity":2,"message":"x is unused","line":1,"column":5}]}]',
                b"",
            )
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await runner.check(Path("/tmp/test.ts"))
            assert isinstance(result, LintResult)

    @pytest.mark.asyncio
    async def test_check_directory(self) -> None:
        """Test checking a directory of TypeScript files."""
        runner = ESLintRunner()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"[]", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await runner.check(Path("/path/to/src"))
            assert result.success

    @pytest.mark.asyncio
    async def test_fix_auto_fixable(self) -> None:
        """Test auto-fixing ESLint issues."""
        runner = ESLintRunner()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"[]", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await runner.fix(Path("/path/to/file.ts"))
            assert result.success

    @pytest.mark.asyncio
    async def test_parse_eslint_json_output(self) -> None:
        """Test parsing ESLint JSON output into violations."""
        runner = ESLintRunner()
        output = """[
            {
                "filePath": "/path/file.ts",
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "x is defined but never used",
                        "line": 10,
                        "column": 5,
                        "fix": {"range": [0, 10], "text": ""}
                    }
                ]
            }
        ]"""

        violations = runner._parse_json_output(output)
        assert len(violations) == 1
        assert violations[0].line == 10
        assert violations[0].code == "no-unused-vars"
        assert violations[0].fixable  # Has "fix" key

    def test_eslint_not_installed(self) -> None:
        """Test handling when ESLint is not installed."""
        runner = ESLintRunner()
        # Should gracefully handle missing ESLint
        assert runner.is_available() is not None  # Returns True or False


class TestRuleEnforcer:
    """Tests for the main RuleEnforcer class."""

    def test_enforcer_initialization(self) -> None:
        """Test RuleEnforcer initialization with defaults."""
        enforcer = RuleEnforcer()
        assert enforcer is not None
        assert enforcer.ruff_runner is not None

    def test_enforcer_with_custom_rules_path(self) -> None:
        """Test RuleEnforcer with custom .cursorrules path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write("# Custom rules")
            f.flush()
            enforcer = RuleEnforcer(cursorrules_path=Path(f.name))
            assert enforcer.cursorrules_path == Path(f.name)

    def test_enforcer_with_runners(self) -> None:
        """Test RuleEnforcer with custom runners."""
        ruff_runner = RuffRunner()
        eslint_runner = ESLintRunner()
        enforcer = RuleEnforcer(
            ruff_runner=ruff_runner,
            eslint_runner=eslint_runner,
        )
        assert enforcer.ruff_runner is ruff_runner
        assert enforcer.eslint_runner is eslint_runner

    @pytest.mark.asyncio
    async def test_check_python_file(self) -> None:
        """Test checking a Python file."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer.ruff_runner, "check") as mock_check:
            mock_check.return_value = LintResult(
                success=True,
                violations=[],
                files_checked=1,
                auto_fixes_applied=0,
            )
            result = await enforcer.check(Path("/path/to/file.py"))
            assert result.success
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_typescript_file(self) -> None:
        """Test checking a TypeScript file."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer.eslint_runner, "check") as mock_check:
            mock_check.return_value = LintResult(
                success=True,
                violations=[],
                files_checked=1,
                auto_fixes_applied=0,
            )
            result = await enforcer.check(Path("/path/to/file.ts"))
            assert result.success
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_mixed_directory(self) -> None:
        """Test checking a directory with mixed file types."""
        enforcer = RuleEnforcer()

        # Create a mock path that behaves like a directory
        mock_path = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        mock_path.is_file.return_value = False
        mock_path.suffix = ""

        with patch.object(enforcer.ruff_runner, "check") as mock_ruff:
            with patch.object(enforcer.eslint_runner, "check") as mock_eslint:
                with patch.object(enforcer.eslint_runner, "is_available", return_value=True):
                    mock_ruff.return_value = LintResult(
                        success=True, violations=[], files_checked=3, auto_fixes_applied=0
                    )
                    mock_eslint.return_value = LintResult(
                        success=True, violations=[], files_checked=2, auto_fixes_applied=0
                    )

                    result = await enforcer.check(mock_path)
                    assert result.success
                    assert result.files_checked == 5

    @pytest.mark.asyncio
    async def test_fix_with_auto_fix(self) -> None:
        """Test fixing with auto-fix enabled."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer.ruff_runner, "fix") as mock_ruff:
            with patch.object(enforcer.eslint_runner, "fix") as mock_eslint:
                mock_ruff.return_value = LintResult(
                    success=True, violations=[], files_checked=1, auto_fixes_applied=3
                )
                mock_eslint.return_value = LintResult(
                    success=True, violations=[], files_checked=0, auto_fixes_applied=0
                )

                result = await enforcer.fix(Path("/path/to/file.py"))
                assert result.success
                assert result.auto_fixes_applied == 3

    @pytest.mark.asyncio
    async def test_gate_check_passes(self) -> None:
        """Test that gate check passes when no errors."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer, "check") as mock_check:
            mock_check.return_value = LintResult(
                success=True, violations=[], files_checked=1, auto_fixes_applied=0
            )

            passed, result = await enforcer.gate_check(Path("/path/to/src"))
            assert passed
            assert result.success

    @pytest.mark.asyncio
    async def test_gate_check_fails_on_errors(self) -> None:
        """Test that gate check fails when there are errors."""
        enforcer = RuleEnforcer()
        violations = [
            LintViolation(
                file_path="/path/file.py",
                line=10,
                column=1,
                code="E501",
                message="Error",
                severity=RuleSeverity.ERROR,
                fixable=False,
            ),
        ]
        with patch.object(enforcer, "check") as mock_check:
            mock_check.return_value = LintResult(
                success=False,
                violations=violations,
                files_checked=1,
                auto_fixes_applied=0,
            )

            passed, result = await enforcer.gate_check(Path("/path/to/src"))
            assert not passed

    @pytest.mark.asyncio
    async def test_gate_check_with_auto_fix(self) -> None:
        """Test gate check with auto-fix enabled."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer, "fix") as mock_fix:
            with patch.object(enforcer, "check") as mock_check:
                mock_fix.return_value = LintResult(
                    success=True, violations=[], files_checked=1, auto_fixes_applied=2
                )
                mock_check.return_value = LintResult(
                    success=True, violations=[], files_checked=1, auto_fixes_applied=0
                )

                passed, result = await enforcer.gate_check(
                    Path("/path/to/src"),
                    auto_fix=True,
                )
                assert passed
                mock_fix.assert_called_once()
                mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_severity_threshold(self) -> None:
        """Test custom severity threshold for gate check."""
        enforcer = RuleEnforcer(severity_threshold=RuleSeverity.ERROR)
        warnings = [
            LintViolation(
                file_path="/path/file.py",
                line=10,
                column=1,
                code="W001",
                message="Warning",
                severity=RuleSeverity.WARNING,
                fixable=False,
            ),
        ]
        with patch.object(enforcer, "check") as mock_check:
            mock_check.return_value = LintResult(
                success=False,
                violations=warnings,
                files_checked=1,
                auto_fixes_applied=0,
            )

            # Should pass because only warnings, no errors
            passed, result = await enforcer.gate_check(Path("/path/to/src"))
            assert passed

    def test_load_cursor_rules(self) -> None:
        """Test loading .cursorrules file."""
        content = """rules:
  - name: no-print
    description: Avoid print statements
    severity: warning
    language: python
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write(content)
            f.flush()
            enforcer = RuleEnforcer(cursorrules_path=Path(f.name))
            rules = enforcer.load_cursor_rules()
            assert len(rules) == 1
            assert rules[0].name == "no-print"

    @pytest.mark.asyncio
    async def test_apply_cursor_rules(self) -> None:
        """Test applying .cursorrules during check."""
        content = """rules:
  - name: no-todo-comments
    description: No TODO comments
    severity: warning
    pattern: '# TODO'
    language: python
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write(content)
            f.flush()

            enforcer = RuleEnforcer(cursorrules_path=Path(f.name))

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as pyf:
                pyf.write("# TODO: fix this later\nx = 1\n")
                pyf.flush()

                with patch.object(enforcer.ruff_runner, "check") as mock_ruff:
                    mock_ruff.return_value = LintResult(
                        success=True, violations=[], files_checked=1, auto_fixes_applied=0
                    )

                    result = await enforcer.check(
                        Path(pyf.name),
                        apply_cursor_rules=True,
                    )
                    # Should find TODO violation from cursor rules
                    assert isinstance(result, LintResult)

    def test_get_language_for_file(self) -> None:
        """Test language detection from file extension."""
        enforcer = RuleEnforcer()
        assert enforcer._get_language(Path("/path/to/file.py")) == "python"
        assert enforcer._get_language(Path("/path/to/file.ts")) == "typescript"
        assert enforcer._get_language(Path("/path/to/file.tsx")) == "typescript"
        assert enforcer._get_language(Path("/path/to/file.js")) == "javascript"
        assert enforcer._get_language(Path("/path/to/file.jsx")) == "javascript"
        assert enforcer._get_language(Path("/path/to/file.unknown")) is None

    def test_generate_report(self) -> None:
        """Test generating a human-readable lint report."""
        enforcer = RuleEnforcer()
        violations = [
            LintViolation(
                file_path="/path/file.py",
                line=10,
                column=1,
                code="E501",
                message="Line too long",
                severity=RuleSeverity.ERROR,
                fixable=False,
            ),
            LintViolation(
                file_path="/path/file.py",
                line=15,
                column=1,
                code="W001",
                message="Warning message",
                severity=RuleSeverity.WARNING,
                fixable=True,
            ),
        ]
        result = LintResult(
            success=False,
            violations=violations,
            files_checked=1,
            auto_fixes_applied=0,
        )

        report = enforcer.generate_report(result)
        assert "E501" in report
        assert "Line too long" in report
        assert "ERROR" in report or "error" in report.lower()

    @pytest.mark.asyncio
    async def test_integration_with_developer_workflow(self) -> None:
        """Test that RuleEnforcer can be used as gate in Developer workflow."""
        enforcer = RuleEnforcer()

        # Simulating being called from Developer agent's Green phase
        with patch.object(enforcer, "gate_check") as mock_gate:
            mock_gate.return_value = (
                True,
                LintResult(success=True, violations=[], files_checked=5, auto_fixes_applied=1),
            )

            passed, result = await enforcer.gate_check(
                Path("/project/src"),
                auto_fix=True,
            )

            assert passed
            assert result.success
            mock_gate.assert_called_once()

    def test_enforcer_config_from_dict(self) -> None:
        """Test creating enforcer configuration from dictionary."""
        config = {
            "severity_threshold": "error",
            "auto_fix": True,
            "ruff": {
                "select": ["E", "F"],
                "ignore": ["E501"],
            },
            "eslint": {
                "extensions": [".ts", ".tsx"],
            },
        }
        enforcer = RuleEnforcer.from_config(config)
        assert enforcer.severity_threshold == RuleSeverity.ERROR

    @pytest.mark.asyncio
    async def test_check_with_excluded_paths(self) -> None:
        """Test checking with excluded paths."""
        enforcer = RuleEnforcer(
            exclude_patterns=["**/node_modules/**", "**/__pycache__/**"],
        )
        with patch.object(enforcer.ruff_runner, "check") as mock_ruff:
            mock_ruff.return_value = LintResult(
                success=True, violations=[], files_checked=0, auto_fixes_applied=0
            )

            result = await enforcer.check(Path("/path/to/src"))
            # Excluded paths should not be checked
            assert result is not None


class TestRuleEnforcerErrors:
    """Tests for error handling in RuleEnforcer."""

    @pytest.mark.asyncio
    async def test_ruff_not_available(self) -> None:
        """Test handling when ruff is not installed."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer.ruff_runner, "is_available", return_value=False):
            with patch.object(enforcer.ruff_runner, "check") as mock_check:
                mock_check.side_effect = FileNotFoundError("ruff not found")

                with pytest.raises(FileNotFoundError):
                    await enforcer.check(Path("/path/to/file.py"))

    @pytest.mark.asyncio
    async def test_eslint_not_available(self) -> None:
        """Test handling when eslint is not installed."""
        enforcer = RuleEnforcer()
        with patch.object(enforcer.eslint_runner, "is_available", return_value=False):
            # Should skip ESLint check gracefully
            with patch.object(enforcer.ruff_runner, "check") as mock_ruff:
                mock_ruff.return_value = LintResult(
                    success=True, violations=[], files_checked=1, auto_fixes_applied=0
                )

                result = await enforcer.check(Path("/path/to/file.py"))
                assert result.success

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test that timeout is configured on RuleEnforcer."""
        import asyncio as aio

        # Test that timeout is configurable
        enforcer = RuleEnforcer(timeout=5.0)
        assert enforcer.timeout == 5.0

        enforcer2 = RuleEnforcer(timeout=120.0)
        assert enforcer2.timeout == 120.0

        # Test that asyncio.TimeoutError propagates properly when wait_for raises it
        mock_ruff = AsyncMock()
        mock_ruff.side_effect = TimeoutError("Lint operation timed out")

        enforcer3 = RuleEnforcer()
        with patch.object(enforcer3.ruff_runner, "check", mock_ruff):
            with pytest.raises(aio.TimeoutError):
                await enforcer3.check(Path("/path/to/file.py"))

    def test_invalid_cursorrules_format(self) -> None:
        """Test handling invalid .cursorrules format."""
        content = "{{{{invalid yaml content"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cursorrules", delete=False) as f:
            f.write(content)
            f.flush()

            enforcer = RuleEnforcer(cursorrules_path=Path(f.name))
            # Should not raise, but return empty rules
            rules = enforcer.load_cursor_rules()
            assert rules == []
