"""
TDD Guard - Red-Green-Refactor Enforcement Logic.

CORE-005: Create a logic module that checks for the existence of a failing test file
before allowing 'Implementation' tools to be called. Must block writes to src/ until
tests/ file exists and fails.
"""

from __future__ import annotations

import fnmatch
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from daw_agents.tdd.exceptions import TDDViolation


@dataclass
class TestResult:
    """
    Result of running a test file.

    Attributes:
        passed: Whether all tests in the file passed.
        test_file: Path to the test file that was run.
        output: Full pytest output.
        error: Error message if tests failed.
        exit_code: Pytest exit code.
        duration_ms: Time taken to run tests in milliseconds.
    """

    passed: bool
    test_file: str
    output: str
    error: str | None = None
    exit_code: int | None = None
    duration_ms: float | None = None


WorkflowState = Literal["red", "green", "refactor"] | None


@dataclass
class TDDGuard:
    """
    TDD Guard enforces test-driven development workflow.

    This guard ensures that:
    1. A test file exists before implementation code can be written
    2. The test fails (RED phase) before implementation is allowed
    3. The test passes (GREEN phase) after implementation

    Attributes:
        project_root: Root directory of the project.
        src_dir: Name of the source directory (default: "src").
        tests_dir: Name of the tests directory (default: "tests").
        test_patterns: List of test file naming patterns.
        pytest_args: Additional arguments to pass to pytest.
        strict: If True, enforce TDD for all files without exception.
        excluded_patterns: File patterns to exclude from TDD enforcement.
    """

    project_root: Path
    src_dir: str = "src"
    tests_dir: str = "tests"
    test_patterns: list[str] = field(
        default_factory=lambda: ["test_{name}.py", "{name}_test.py"]
    )
    pytest_args: list[str] = field(default_factory=list)
    strict: bool = False
    excluded_patterns: list[str] = field(
        default_factory=lambda: ["__init__.py", "conftest.py", "__pycache__"]
    )

    # Internal state tracking
    _workflow_states: dict[str, WorkflowState] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Ensure project_root is a Path object."""
        if isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)

    def get_test_file_path(self, source_file: Path) -> Path:
        """
        Get the expected test file path for a source file.

        Args:
            source_file: Path to the source file.

        Returns:
            Path to the expected test file.
        """
        source_file = Path(source_file)

        # Extract the relative path from src directory
        try:
            relative_path = source_file.relative_to(self.project_root / self.src_dir)
        except ValueError:
            # File might be directly under project root or in a custom location
            relative_path = source_file.relative_to(self.project_root)
            if str(relative_path).startswith(self.src_dir):
                relative_path = Path(str(relative_path)[len(self.src_dir) + 1 :])

        # Build the test file path using the first pattern
        name = source_file.stem
        test_filename = self.test_patterns[0].format(name=name)

        # Handle nested modules - preserve directory structure in tests
        if relative_path.parent != Path("."):
            test_path = self.project_root / self.tests_dir / relative_path.parent / test_filename
        else:
            test_path = self.project_root / self.tests_dir / test_filename

        return test_path

    def check_test_exists(self, source_file: Path) -> bool:
        """
        Check if a test file exists for the given source file.

        Args:
            source_file: Path to the source file.

        Returns:
            True if a matching test file exists, False otherwise.
        """
        source_file = Path(source_file)
        name = source_file.stem

        # Get all possible test locations
        possible_test_dirs = self._get_possible_test_dirs(source_file)

        # Check all test patterns in all possible locations
        for pattern in self.test_patterns:
            test_filename = pattern.format(name=name)

            for test_dir in possible_test_dirs:
                test_path = test_dir / test_filename
                if test_path.exists():
                    return True

        return False

    def _get_possible_test_dirs(self, source_file: Path) -> list[Path]:
        """
        Get all possible test directory locations for a source file.

        For a source file like src/daw_agents/mcp/client.py, this returns:
        - tests/daw_agents/mcp/
        - tests/mcp/ (last significant directory)
        - tests/ (root)
        """
        source_file = Path(source_file)
        possible_dirs: list[Path] = []

        # Try to find relative path from source directory
        try:
            relative_path = source_file.relative_to(self.project_root / self.src_dir)
            parts = relative_path.parent.parts
        except ValueError:
            # Handle nested modules like src/daw_agents/mcp/client.py
            try:
                full_relative = source_file.relative_to(self.project_root)
                parts_list = list(full_relative.parts)
                if self.src_dir in parts_list:
                    idx = parts_list.index(self.src_dir)
                    parts = tuple(parts_list[idx + 1 : -1])
                else:
                    parts = ()
            except ValueError:
                parts = ()

        # Add full path in tests directory
        if parts:
            possible_dirs.append(self.project_root / self.tests_dir / Path(*parts))

            # Add just the last directory component (e.g., tests/mcp/)
            if len(parts) > 1:
                possible_dirs.append(self.project_root / self.tests_dir / parts[-1])

        # Always check root tests directory
        possible_dirs.append(self.project_root / self.tests_dir)

        return possible_dirs

    def run_test(self, test_file: Path) -> TestResult:
        """
        Run a test file and return the result.

        Args:
            test_file: Path to the test file to run.

        Returns:
            TestResult with pass/fail status and output.

        Raises:
            FileNotFoundError: If the test file does not exist.
        """
        test_file = Path(test_file)

        if not test_file.exists():
            raise FileNotFoundError(f"Test file not found: {test_file}")

        start_time = time.time()

        # Build pytest command
        cmd = ["pytest", str(test_file), "-v", "--tb=short"]
        cmd.extend(self.pytest_args)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            duration_ms = (time.time() - start_time) * 1000

            passed = result.returncode == 0
            output = result.stdout + result.stderr
            error = None if passed else self._extract_error(output)

            return TestResult(
                passed=passed,
                test_file=str(test_file),
                output=output,
                error=error,
                exit_code=result.returncode,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                passed=False,
                test_file=str(test_file),
                output="",
                error="Test execution timed out",
                exit_code=-1,
                duration_ms=duration_ms,
            )

    def _extract_error(self, output: str) -> str:
        """Extract the error message from pytest output."""
        lines = output.split("\n")
        error_lines: list[str] = []
        in_failure = False

        for line in lines:
            if "FAILED" in line or "ERROR" in line:
                in_failure = True
            if in_failure:
                error_lines.append(line)
            if "short test summary" in line.lower():
                break

        return "\n".join(error_lines) if error_lines else output

    def enforce_red_phase(self, test_file: Path) -> None:
        """
        Enforce RED phase - test must fail.

        Args:
            test_file: Path to the test file.

        Raises:
            TDDViolation: If the test passes (should fail in RED phase).
        """
        result = self.run_test(test_file)

        if result.passed:
            raise TDDViolation(
                message="Test must fail in RED phase before implementation can begin. "
                "Write a failing test that defines the expected behavior.",
                phase="red",
                test_file=str(test_file),
                test_result=result,
            )

        # Update workflow state
        self._workflow_states[str(test_file)] = "red"

    def enforce_green_phase(self, test_file: Path) -> None:
        """
        Enforce GREEN phase - test must pass.

        Args:
            test_file: Path to the test file.

        Raises:
            TDDViolation: If the test fails (should pass in GREEN phase).
        """
        result = self.run_test(test_file)

        if not result.passed:
            raise TDDViolation(
                message="Test must pass in GREEN phase. "
                "Implementation is not complete or contains errors.",
                phase="green",
                test_file=str(test_file),
                test_result=result,
            )

        # Update workflow state
        self._workflow_states[str(test_file)] = "green"

    def can_write_source(self, source_file: Path) -> bool:
        """
        Check if source file can be written according to TDD rules.

        This is the main enforcement point. It checks:
        1. Test file must exist
        2. Test must fail (RED phase)

        Args:
            source_file: Path to the source file to be written.

        Returns:
            True if writing is allowed.

        Raises:
            TDDViolation: If TDD rules are violated.
        """
        source_file = Path(source_file)

        # Check if file is excluded
        if self.is_excluded(source_file):
            return True

        # Check if test exists
        if not self.check_test_exists(source_file):
            test_path = self.get_test_file_path(source_file)
            raise TDDViolation(
                message="Test file must exist before implementing source code. "
                "Write a failing test first (RED phase).",
                phase="pre-red",
                test_file=str(test_path),
                source_file=str(source_file),
            )

        # Find the test file and verify it fails (RED phase)
        test_file = self._find_test_file(source_file)
        if test_file:
            self.enforce_red_phase(test_file)

        return True

    def _find_test_file(self, source_file: Path) -> Path | None:
        """Find the test file for a source file."""
        source_file = Path(source_file)
        name = source_file.stem

        # Get all possible test locations
        possible_test_dirs = self._get_possible_test_dirs(source_file)

        for pattern in self.test_patterns:
            test_filename = pattern.format(name=name)

            for test_dir in possible_test_dirs:
                test_path = test_dir / test_filename
                if test_path.exists():
                    return test_path

        return None

    def get_workflow_state(self, source_file: Path) -> WorkflowState:
        """
        Get the current workflow state for a source file.

        Args:
            source_file: Path to the source file.

        Returns:
            Current workflow state or None if not tracked.
        """
        test_file = self._find_test_file(source_file)
        if test_file:
            return self._workflow_states.get(str(test_file))
        return None

    def is_excluded(self, file_path: Path) -> bool:
        """
        Check if a file is excluded from TDD enforcement.

        Args:
            file_path: Path to check.

        Returns:
            True if the file should be excluded.
        """
        file_path = Path(file_path)
        filename = file_path.name

        for pattern in self.excluded_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False
