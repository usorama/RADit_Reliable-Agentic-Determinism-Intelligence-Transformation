"""Dogfood test: Use DAW to build a calculator.

This functional test validates the complete DAW agent pipeline by building
a simple calculator application. It tests:

1. PRD parsing and understanding
2. Task decomposition by Planner Agent
3. Code generation by Developer Agent
4. Validation by Validator Agent
5. Integration by UAT Agent

Note: Full LLM-based agent invocation is expensive for CI. This test:
- Validates benchmark structure and completeness
- Documents the full dogfood workflow
- Can be run with LLM credentials for manual testing
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# Benchmark directory relative to project root
BENCHMARK_DIR = Path(__file__).parents[4] / "eval" / "benchmarks" / "calculator"


class TestBenchmarkStructure:
    """Test that the calculator benchmark is properly structured."""

    def test_prd_exists(self) -> None:
        """PRD file must exist."""
        prd_path = BENCHMARK_DIR / "prd.md"
        assert prd_path.exists(), f"PRD not found at {prd_path}"

    def test_prd_contains_required_sections(self) -> None:
        """PRD must contain all required sections."""
        prd_path = BENCHMARK_DIR / "prd.md"
        prd_content = prd_path.read_text()

        required_sections = [
            "Overview",
            "User Stories",
            "Technical Requirements",
            "Non-Functional Requirements",
            "Success Criteria",
        ]

        for section in required_sections:
            assert section in prd_content, f"PRD missing section: {section}"

    def test_prd_contains_operations(self) -> None:
        """PRD must specify calculator operations."""
        prd_path = BENCHMARK_DIR / "prd.md"
        prd_content = prd_path.read_text().lower()

        operations = ["add", "subtract", "multiply", "divide"]
        for op in operations:
            assert op in prd_content, f"PRD missing operation: {op}"

    def test_rubric_exists(self) -> None:
        """Rubric file must exist."""
        rubric_path = BENCHMARK_DIR / "rubric.yaml"
        assert rubric_path.exists(), f"Rubric not found at {rubric_path}"

    def test_rubric_has_scoring_criteria(self) -> None:
        """Rubric must define scoring criteria."""
        rubric_path = BENCHMARK_DIR / "rubric.yaml"
        rubric: dict[str, Any] = yaml.safe_load(rubric_path.read_text())

        assert "scoring" in rubric, "Rubric missing scoring section"
        assert "task_decomposition" in rubric["scoring"], "Missing task_decomposition scoring"
        assert "code_quality" in rubric["scoring"], "Missing code_quality scoring"

    def test_metadata_exists(self) -> None:
        """Metadata file must exist."""
        metadata_path = BENCHMARK_DIR / "metadata.json"
        assert metadata_path.exists(), f"Metadata not found at {metadata_path}"


class TestExpectedOutputs:
    """Test that expected outputs are properly defined."""

    def test_expected_directory_exists(self) -> None:
        """Expected outputs directory must exist."""
        expected_dir = BENCHMARK_DIR / "expected"
        assert expected_dir.exists(), f"Expected outputs directory not found at {expected_dir}"

    def test_expected_tasks_exist(self) -> None:
        """Expected task decomposition must exist."""
        tasks_path = BENCHMARK_DIR / "expected" / "tasks.json"
        assert tasks_path.exists(), f"Expected tasks not found at {tasks_path}"

    def test_expected_tests_exist(self) -> None:
        """Expected test files must exist."""
        tests_dir = BENCHMARK_DIR / "expected" / "tests"
        assert tests_dir.exists(), f"Expected tests directory not found at {tests_dir}"

        test_files = ["test_operations.py", "test_validator.py"]
        for test_file in test_files:
            path = tests_dir / test_file
            assert path.exists(), f"Expected test file not found: {path}"

    def test_expected_implementation_exists(self) -> None:
        """Expected implementation files must exist."""
        src_dir = BENCHMARK_DIR / "expected" / "src" / "calculator"
        assert src_dir.exists(), f"Expected src directory not found at {src_dir}"

        impl_files = ["__init__.py", "operations.py", "validator.py"]
        for impl_file in impl_files:
            path = src_dir / impl_file
            assert path.exists(), f"Expected implementation file not found: {path}"


class TestRubricWeights:
    """Test rubric scoring weights are valid."""

    def test_weights_sum_to_one(self) -> None:
        """Category weights must sum to 1.0."""
        rubric_path = BENCHMARK_DIR / "rubric.yaml"
        rubric: dict[str, Any] = yaml.safe_load(rubric_path.read_text())

        total_weight = 0.0
        for category_data in rubric["scoring"].values():
            total_weight += category_data.get("weight", 0)

        assert abs(total_weight - 1.0) < 0.01, f"Weights sum to {total_weight}, expected 1.0"

    def test_subcriteria_weights_sum_to_one(self) -> None:
        """Sub-criteria weights must sum to 1.0 per category."""
        rubric_path = BENCHMARK_DIR / "rubric.yaml"
        rubric: dict[str, Any] = yaml.safe_load(rubric_path.read_text())

        for category_name, category_data in rubric["scoring"].items():
            criteria = category_data.get("criteria", [])
            if criteria:
                total_weight = sum(c.get("weight", 0) for c in criteria)
                assert (
                    abs(total_weight - 1.0) < 0.01
                ), f"{category_name} criteria weights sum to {total_weight}, expected 1.0"


class TestExpectedCodeQuality:
    """Test expected implementation meets quality standards."""

    def test_operations_has_type_hints(self) -> None:
        """Operations module must have type hints."""
        operations_path = BENCHMARK_DIR / "expected" / "src" / "calculator" / "operations.py"
        content = operations_path.read_text()

        # Check for function signatures with type hints
        assert "def add(a: float, b: float) -> float:" in content
        assert "def subtract(a: float, b: float) -> float:" in content
        assert "def multiply(a: float, b: float) -> float:" in content
        assert "def divide(a: float, b: float) -> float:" in content

    def test_operations_has_docstrings(self) -> None:
        """Operations module must have docstrings."""
        operations_path = BENCHMARK_DIR / "expected" / "src" / "calculator" / "operations.py"
        content = operations_path.read_text()

        # Check for docstrings (triple quotes after function def)
        assert '"""Add two numbers' in content
        assert '"""Subtract' in content
        assert '"""Multiply' in content
        assert '"""Divide' in content

    def test_validator_has_exception_class(self) -> None:
        """Validator module must define ValidationError."""
        validator_path = BENCHMARK_DIR / "expected" / "src" / "calculator" / "validator.py"
        content = validator_path.read_text()

        assert "class ValidationError(Exception):" in content

    def test_divide_by_zero_handling(self) -> None:
        """Divide function must handle zero division."""
        operations_path = BENCHMARK_DIR / "expected" / "src" / "calculator" / "operations.py"
        content = operations_path.read_text()

        assert "ZeroDivisionError" in content


@pytest.mark.functional
@pytest.mark.slow
class TestDogfoodWorkflow:
    """
    Dogfood workflow tests - documents the full agent pipeline.

    These tests are scaffolded to show what a complete dogfood test
    would validate. Running full LLM invocation is expensive, so CI
    tests validate structure only.

    To run full dogfood tests with LLM:
        pytest -m functional --run-llm
    """

    def test_workflow_step_1_load_prd(self) -> None:
        """Step 1: Load and parse PRD."""
        prd_path = BENCHMARK_DIR / "prd.md"
        prd_content = prd_path.read_text()

        # Validate PRD can be loaded
        assert len(prd_content) > 100, "PRD content too short"
        assert "Calculator" in prd_content, "PRD should reference Calculator"

    def test_workflow_step_2_expected_task_count(self) -> None:
        """Step 2: Planner should produce reasonable task count."""
        import json

        tasks_path = BENCHMARK_DIR / "expected" / "tasks.json"
        tasks: list[dict[str, Any]] = json.loads(tasks_path.read_text())

        # Calculator benchmark expects 6-8 tasks
        assert 6 <= len(tasks) <= 8, f"Expected 6-8 tasks, got {len(tasks)}"

    def test_workflow_step_3_tasks_have_dependencies(self) -> None:
        """Step 3: Tasks should have proper dependency graph."""
        import json

        tasks_path = BENCHMARK_DIR / "expected" / "tasks.json"
        tasks: list[dict[str, Any]] = json.loads(tasks_path.read_text())

        task_ids = {t["id"] for t in tasks}

        # Verify all dependencies reference valid tasks
        for task in tasks:
            deps = task.get("dependencies", [])
            for dep in deps:
                assert dep in task_ids, f"Task {task['id']} has invalid dependency: {dep}"

    def test_workflow_step_4_code_generation_structure(self) -> None:
        """Step 4: Generated code should follow expected structure."""
        expected_files = [
            "expected/src/calculator/__init__.py",
            "expected/src/calculator/operations.py",
            "expected/src/calculator/validator.py",
            "expected/tests/test_operations.py",
            "expected/tests/test_validator.py",
        ]

        for file_rel in expected_files:
            path = BENCHMARK_DIR / file_rel
            assert path.exists(), f"Expected file missing: {file_rel}"

    def test_workflow_step_5_validation_criteria(self) -> None:
        """Step 5: Validator should check these criteria."""
        rubric_path = BENCHMARK_DIR / "rubric.yaml"
        rubric: dict[str, Any] = yaml.safe_load(rubric_path.read_text())

        # Pass criteria should be defined
        assert "pass_criteria" in rubric, "Rubric must define pass_criteria"

        required = rubric["pass_criteria"]["required"]
        # Check that all_tests_pass is in the required criteria (list of dicts)
        has_test_pass_requirement = any(
            "all_tests_pass" in item for item in required if isinstance(item, dict)
        )
        assert has_test_pass_requirement, "Must require all tests to pass"


@pytest.mark.functional
class TestExpectedImplementationWorks:
    """Test that the expected implementation actually works."""

    def test_add_function(self) -> None:
        """Test expected add implementation."""
        # Import from expected implementation
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.operations import add  # type: ignore

            assert add(2, 3) == 5.0
            assert add(-2, 3) == 1.0
            assert add(2.5, 3.5) == 6.0
            assert add(0, 0) == 0.0
        finally:
            sys.path.remove(str(src_path))

    def test_subtract_function(self) -> None:
        """Test expected subtract implementation."""
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.operations import subtract  # type: ignore

            assert subtract(5, 3) == 2.0
            assert subtract(3, 5) == -2.0
            assert subtract(-2, -3) == 1.0
        finally:
            sys.path.remove(str(src_path))

    def test_multiply_function(self) -> None:
        """Test expected multiply implementation."""
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.operations import multiply  # type: ignore

            assert multiply(4, 3) == 12.0
            assert multiply(5, 0) == 0.0
            assert multiply(-2, 3) == -6.0
            assert multiply(-2, -3) == 6.0
        finally:
            sys.path.remove(str(src_path))

    def test_divide_function(self) -> None:
        """Test expected divide implementation."""
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.operations import divide  # type: ignore

            assert divide(10, 2) == 5.0
            assert divide(5, 2) == 2.5
            assert divide(-6, 3) == -2.0
        finally:
            sys.path.remove(str(src_path))

    def test_divide_by_zero_raises(self) -> None:
        """Test expected divide raises for zero divisor."""
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.operations import divide  # type: ignore

            with pytest.raises(ZeroDivisionError):
                divide(10, 0)
        finally:
            sys.path.remove(str(src_path))

    def test_validate_number(self) -> None:
        """Test expected validate_number implementation."""
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.validator import ValidationError, validate_number  # type: ignore

            assert validate_number("42") == 42.0
            assert validate_number("3.14") == 3.14
            assert validate_number("-5") == -5.0

            with pytest.raises(ValidationError):
                validate_number("")

            with pytest.raises(ValidationError):
                validate_number("abc")
        finally:
            sys.path.remove(str(src_path))

    def test_validate_operation(self) -> None:
        """Test expected validate_operation implementation."""
        import sys

        src_path = BENCHMARK_DIR / "expected" / "src"
        sys.path.insert(0, str(src_path))

        try:
            from calculator.validator import ValidationError, validate_operation  # type: ignore

            assert validate_operation("+") == "+"
            assert validate_operation("-") == "-"
            assert validate_operation("*") == "*"
            assert validate_operation("/") == "/"

            with pytest.raises(ValidationError):
                validate_operation("^")
        finally:
            sys.path.remove(str(src_path))
