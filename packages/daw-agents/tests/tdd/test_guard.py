"""
Tests for TDD Guard - Red-Green-Refactor Enforcement Logic.

CORE-005: Create a logic module that checks for the existence of a failing test file
before allowing 'Implementation' tools to be called. Must block writes to src/ until
tests/ file exists and fails.
"""

from pathlib import Path

import pytest

from daw_agents.tdd.exceptions import TDDViolation
from daw_agents.tdd.guard import TDDGuard, TestResult


class TestTestResult:
    """Tests for the TestResult data structure."""

    def test_test_result_passed(self) -> None:
        """TestResult should correctly represent a passed test."""
        result = TestResult(passed=True, test_file="tests/test_example.py", output="OK")
        assert result.passed is True
        assert result.test_file == "tests/test_example.py"
        assert result.output == "OK"
        assert result.error is None

    def test_test_result_failed(self) -> None:
        """TestResult should correctly represent a failed test."""
        result = TestResult(
            passed=False,
            test_file="tests/test_example.py",
            output="FAILED",
            error="AssertionError: Expected 1, got 2",
        )
        assert result.passed is False
        assert result.test_file == "tests/test_example.py"
        assert result.error == "AssertionError: Expected 1, got 2"

    def test_test_result_with_exit_code(self) -> None:
        """TestResult should include exit code information."""
        result = TestResult(
            passed=False, test_file="tests/test_example.py", output="", exit_code=1
        )
        assert result.exit_code == 1

    def test_test_result_with_duration(self) -> None:
        """TestResult should include test duration."""
        result = TestResult(
            passed=True, test_file="tests/test_example.py", output="", duration_ms=150.5
        )
        assert result.duration_ms == 150.5


class TestTDDGuardCheckTestExists:
    """Tests for TDDGuard.check_test_exists() method."""

    def test_check_test_exists_returns_true_for_existing_test(
        self, tmp_path: Path
    ) -> None:
        """Should return True when test file exists for source file."""
        # Create source and test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"
        source_file.write_text("# Source code")
        test_file = tests_dir / "test_example.py"
        test_file.write_text("# Test code")

        guard = TDDGuard(project_root=tmp_path)
        assert guard.check_test_exists(source_file) is True

    def test_check_test_exists_returns_false_for_missing_test(
        self, tmp_path: Path
    ) -> None:
        """Should return False when test file does not exist."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"
        source_file.write_text("# Source code")

        guard = TDDGuard(project_root=tmp_path)
        assert guard.check_test_exists(source_file) is False

    def test_check_test_exists_handles_nested_modules(self, tmp_path: Path) -> None:
        """Should find test file for nested module paths."""
        # Create nested structure
        src_dir = tmp_path / "src" / "daw_agents" / "mcp"
        src_dir.mkdir(parents=True)
        tests_dir = tmp_path / "tests" / "mcp"
        tests_dir.mkdir(parents=True)

        source_file = src_dir / "client.py"
        source_file.write_text("# MCP Client")
        test_file = tests_dir / "test_client.py"
        test_file.write_text("# Test MCP Client")

        guard = TDDGuard(project_root=tmp_path)
        assert guard.check_test_exists(source_file) is True

    def test_check_test_exists_respects_custom_test_patterns(
        self, tmp_path: Path
    ) -> None:
        """Should support custom test file naming patterns."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"
        source_file.write_text("# Source code")
        test_file = tests_dir / "example_test.py"  # Alternative pattern
        test_file.write_text("# Test code")

        guard = TDDGuard(project_root=tmp_path, test_patterns=["test_{name}.py", "{name}_test.py"])
        assert guard.check_test_exists(source_file) is True

    def test_get_test_file_path_returns_expected_path(self, tmp_path: Path) -> None:
        """Should return the expected test file path for a source file."""
        guard = TDDGuard(project_root=tmp_path)
        source_file = tmp_path / "src" / "example.py"
        expected = tmp_path / "tests" / "test_example.py"
        assert guard.get_test_file_path(source_file) == expected


class TestTDDGuardRunTest:
    """Tests for TDDGuard.run_test() method."""

    def test_run_test_returns_pass_result(self, tmp_path: Path) -> None:
        """Should return TestResult with passed=True when test passes."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_passes():
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path)
        result = guard.run_test(test_file)

        assert isinstance(result, TestResult)
        assert result.passed is True
        assert result.test_file == str(test_file)

    def test_run_test_returns_fail_result(self, tmp_path: Path) -> None:
        """Should return TestResult with passed=False when test fails."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_fails():
    assert False, "Expected failure"
"""
        )

        guard = TDDGuard(project_root=tmp_path)
        result = guard.run_test(test_file)

        assert isinstance(result, TestResult)
        assert result.passed is False
        assert "Expected failure" in (result.error or result.output)

    def test_run_test_captures_output(self, tmp_path: Path) -> None:
        """Should capture pytest output in TestResult."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_with_output():
    print("Debug output")
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path)
        result = guard.run_test(test_file)

        assert result.output is not None
        # Output should contain test run info

    def test_run_test_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Should raise appropriate error for nonexistent test file."""
        guard = TDDGuard(project_root=tmp_path)
        nonexistent = tmp_path / "tests" / "test_nonexistent.py"

        with pytest.raises(FileNotFoundError):
            guard.run_test(nonexistent)

    def test_run_test_includes_duration(self, tmp_path: Path) -> None:
        """Should include test duration in result."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_quick():
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path)
        result = guard.run_test(test_file)

        assert result.duration_ms is not None
        assert result.duration_ms >= 0


class TestTDDGuardEnforceRedPhase:
    """Tests for TDDGuard.enforce_red_phase() method."""

    def test_enforce_red_phase_passes_when_test_fails(self, tmp_path: Path) -> None:
        """Should not raise when test fails (red phase is valid)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_not_implemented():
    assert False, "Not implemented yet"
"""
        )

        guard = TDDGuard(project_root=tmp_path)
        # Should not raise
        guard.enforce_red_phase(test_file)

    def test_enforce_red_phase_raises_when_test_passes(self, tmp_path: Path) -> None:
        """Should raise TDDViolation when test passes (invalid red phase)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_already_passes():
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path)

        with pytest.raises(TDDViolation) as exc_info:
            guard.enforce_red_phase(test_file)

        assert "Test must fail in RED phase" in str(exc_info.value)

    def test_enforce_red_phase_error_contains_test_info(self, tmp_path: Path) -> None:
        """TDDViolation should contain relevant test information."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_passes():
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path)

        with pytest.raises(TDDViolation) as exc_info:
            guard.enforce_red_phase(test_file)

        violation = exc_info.value
        assert violation.test_file == str(test_file)
        assert violation.phase == "red"


class TestTDDGuardEnforceGreenPhase:
    """Tests for TDDGuard.enforce_green_phase() method."""

    def test_enforce_green_phase_passes_when_test_passes(self, tmp_path: Path) -> None:
        """Should not raise when test passes (green phase is valid)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_now_passes():
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path)
        # Should not raise
        guard.enforce_green_phase(test_file)

    def test_enforce_green_phase_raises_when_test_fails(self, tmp_path: Path) -> None:
        """Should raise TDDViolation when test fails (invalid green phase)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_still_fails():
    assert False, "Implementation not complete"
"""
        )

        guard = TDDGuard(project_root=tmp_path)

        with pytest.raises(TDDViolation) as exc_info:
            guard.enforce_green_phase(test_file)

        assert "Test must pass in GREEN phase" in str(exc_info.value)

    def test_enforce_green_phase_error_contains_test_info(self, tmp_path: Path) -> None:
        """TDDViolation should contain relevant test information."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_fails():
    assert False
"""
        )

        guard = TDDGuard(project_root=tmp_path)

        with pytest.raises(TDDViolation) as exc_info:
            guard.enforce_green_phase(test_file)

        violation = exc_info.value
        assert violation.test_file == str(test_file)
        assert violation.phase == "green"


class TestTDDGuardCanWriteSource:
    """Tests for TDDGuard.can_write_source() method - the main enforcement point."""

    def test_can_write_source_blocks_without_test(self, tmp_path: Path) -> None:
        """Should block source writes when no test file exists."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"

        guard = TDDGuard(project_root=tmp_path)

        with pytest.raises(TDDViolation) as exc_info:
            guard.can_write_source(source_file)

        assert "Test file must exist before implementing" in str(exc_info.value)

    def test_can_write_source_blocks_when_test_passes(self, tmp_path: Path) -> None:
        """Should block source writes when test already passes (wrong phase)."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_passes():
    assert True  # Test shouldn't pass before implementation
"""
        )

        guard = TDDGuard(project_root=tmp_path)

        with pytest.raises(TDDViolation) as exc_info:
            guard.can_write_source(source_file)

        assert "Test must fail in RED phase" in str(exc_info.value)

    def test_can_write_source_allows_when_test_fails(self, tmp_path: Path) -> None:
        """Should allow source writes when test exists and fails (valid red phase)."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_not_implemented():
    assert False, "Implementation needed"
"""
        )

        guard = TDDGuard(project_root=tmp_path)

        # Should not raise - this is valid TDD workflow
        result = guard.can_write_source(source_file)
        assert result is True


class TestTDDGuardValidateWorkflow:
    """Tests for the complete TDD workflow validation."""

    def test_validate_workflow_full_cycle(self, tmp_path: Path) -> None:
        """Test a complete TDD cycle: Red -> Green -> Refactor."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "calculator.py"
        test_file = tests_dir / "test_calculator.py"

        guard = TDDGuard(project_root=tmp_path)

        # Phase 1: Write failing test (RED)
        test_file.write_text(
            """
from src.calculator import add

def test_add():
    assert add(2, 3) == 5
"""
        )

        # Should allow writing source since test fails
        assert guard.can_write_source(source_file) is True
        guard.enforce_red_phase(test_file)

        # Phase 2: Write implementation (GREEN)
        source_file.write_text(
            """
def add(a, b):
    return a + b
"""
        )

        # Create a passing test for green phase check
        test_file.write_text(
            """
def test_add():
    # Simulating that implementation works
    assert True
"""
        )
        guard.enforce_green_phase(test_file)

    def test_workflow_state_tracking(self, tmp_path: Path) -> None:
        """TDD Guard should track workflow state per file."""
        guard = TDDGuard(project_root=tmp_path)

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = src_dir / "example.py"
        test_file = tests_dir / "test_example.py"

        # Initially no state
        assert guard.get_workflow_state(source_file) is None

        # After test creation
        test_file.write_text(
            """
def test_fails():
    assert False
"""
        )
        guard.can_write_source(source_file)
        assert guard.get_workflow_state(source_file) == "red"


class TestTDDViolationException:
    """Tests for the TDDViolation exception class."""

    def test_tdd_violation_message(self) -> None:
        """TDDViolation should have clear error message."""
        violation = TDDViolation(
            message="Test file must exist before implementing",
            phase="pre-red",
            test_file="tests/test_example.py",
            source_file="src/example.py",
        )

        assert "Test file must exist" in str(violation)
        assert violation.phase == "pre-red"
        assert violation.test_file == "tests/test_example.py"
        assert violation.source_file == "src/example.py"

    def test_tdd_violation_with_test_result(self) -> None:
        """TDDViolation should optionally include TestResult."""
        result = TestResult(
            passed=True, test_file="tests/test_example.py", output="1 passed"
        )
        violation = TDDViolation(
            message="Test must fail in RED phase",
            phase="red",
            test_file="tests/test_example.py",
            test_result=result,
        )

        assert violation.test_result is not None
        assert violation.test_result.passed is True

    def test_tdd_violation_is_exception(self) -> None:
        """TDDViolation should be a proper Exception subclass."""
        violation = TDDViolation(message="Error", phase="red", test_file="test.py")
        assert isinstance(violation, Exception)

        with pytest.raises(TDDViolation):
            raise violation


class TestTDDGuardConfiguration:
    """Tests for TDD Guard configuration options."""

    def test_custom_src_directory(self, tmp_path: Path) -> None:
        """Should support custom source directory path."""
        custom_src = tmp_path / "lib"
        custom_src.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        source_file = custom_src / "example.py"
        source_file.write_text("# Source")
        test_file = tests_dir / "test_example.py"
        test_file.write_text("def test(): assert False")

        guard = TDDGuard(project_root=tmp_path, src_dir="lib")
        assert guard.check_test_exists(source_file) is True

    def test_custom_tests_directory(self, tmp_path: Path) -> None:
        """Should support custom tests directory path."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        custom_tests = tmp_path / "spec"
        custom_tests.mkdir()

        source_file = src_dir / "example.py"
        source_file.write_text("# Source")
        test_file = custom_tests / "test_example.py"
        test_file.write_text("def test(): assert False")

        guard = TDDGuard(project_root=tmp_path, tests_dir="spec")
        assert guard.check_test_exists(source_file) is True

    def test_pytest_args_configuration(self, tmp_path: Path) -> None:
        """Should support custom pytest arguments."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            """
def test_passes():
    assert True
"""
        )

        guard = TDDGuard(project_root=tmp_path, pytest_args=["-v", "--tb=short"])
        result = guard.run_test(test_file)
        assert result.passed is True

    def test_strict_mode_configuration(self, tmp_path: Path) -> None:
        """In strict mode, should enforce TDD for all files."""
        guard = TDDGuard(project_root=tmp_path, strict=True)
        assert guard.strict is True

    def test_excluded_paths_configuration(self, tmp_path: Path) -> None:
        """Should support excluding paths from TDD enforcement."""
        src_dir = tmp_path / "src" / "__init__"
        src_dir.mkdir(parents=True)
        init_file = src_dir.parent / "__init__.py"
        init_file.write_text("")

        guard = TDDGuard(
            project_root=tmp_path, excluded_patterns=["__init__.py", "conftest.py"]
        )
        # Init files should be excluded from TDD enforcement
        assert guard.is_excluded(init_file) is True
