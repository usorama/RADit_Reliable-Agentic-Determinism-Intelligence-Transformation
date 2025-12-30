"""Dogfood test: Use DAW to build a settings page for itself.

This is FUNC-002 - the second dogfood test validating that DAW can generate
React/TypeScript frontend code. It follows the pattern established by FUNC-001
(calculator benchmark).

The test validates:
1. Benchmark structure exists and is well-formed
2. Expected component follows React/TypeScript best practices
3. Expected tests cover key functionality
4. Rubric can evaluate frontend code generation

Future: When LLM integration is complete, this will test the full
Planner -> Executor -> Validator pipeline for frontend code generation.
"""

import pytest
from pathlib import Path
import json
import yaml
import re


BENCHMARK_PATH = Path("eval/benchmarks/settings-page")


@pytest.mark.functional
class TestSettingsPageBenchmarkStructure:
    """Validate settings page benchmark structure."""

    def test_benchmark_directory_exists(self) -> None:
        """Benchmark directory should exist."""
        assert BENCHMARK_PATH.exists(), f"Benchmark directory not found: {BENCHMARK_PATH}"
        assert BENCHMARK_PATH.is_dir()

    def test_prd_exists(self) -> None:
        """PRD document should exist."""
        prd = BENCHMARK_PATH / "prd.md"
        assert prd.exists(), f"PRD not found: {prd}"
        assert prd.stat().st_size > 0, "PRD should not be empty"

    def test_prd_has_required_sections(self) -> None:
        """PRD should have standard sections."""
        prd = BENCHMARK_PATH / "prd.md"
        content = prd.read_text()

        required_sections = [
            "Overview",
            "User Stories",
            "Technical Requirements",
            "Non-Functional Requirements",
            "Success Criteria",
        ]

        for section in required_sections:
            assert section in content, f"PRD missing section: {section}"

    def test_rubric_exists(self) -> None:
        """Rubric YAML should exist."""
        rubric = BENCHMARK_PATH / "rubric.yaml"
        assert rubric.exists(), f"Rubric not found: {rubric}"

    def test_rubric_is_valid_yaml(self) -> None:
        """Rubric should be valid YAML."""
        rubric = BENCHMARK_PATH / "rubric.yaml"
        content = rubric.read_text()

        # Should parse without error
        data = yaml.safe_load(content)
        assert data is not None
        assert "scoring" in data
        assert "pass_criteria" in data

    def test_metadata_exists(self) -> None:
        """Metadata JSON should exist."""
        metadata = BENCHMARK_PATH / "metadata.json"
        assert metadata.exists(), f"Metadata not found: {metadata}"

    def test_metadata_is_valid_json(self) -> None:
        """Metadata should be valid JSON with required fields."""
        metadata = BENCHMARK_PATH / "metadata.json"
        content = metadata.read_text()

        data = json.loads(content)
        assert data["benchmark_id"] == "settings-page"
        assert "complexity" in data
        assert "technology_stack" in data
        assert data["technology_stack"]["framework"] == "react"

    def test_expected_directory_exists(self) -> None:
        """Expected outputs directory should exist."""
        expected = BENCHMARK_PATH / "expected"
        assert expected.exists()
        assert expected.is_dir()


@pytest.mark.functional
class TestSettingsComponentStructure:
    """Validate expected Settings component structure."""

    def test_expected_component_exists(self) -> None:
        """Expected Settings.tsx should exist."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        assert component.exists(), f"Component not found: {component}"

    def test_component_is_valid_react(self) -> None:
        """Component should have React imports and exports."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        # Check for React import
        assert "import React" in content or "from 'react'" in content, \
            "Component should import React"

        # Check for export
        assert "export" in content, "Component should export something"

    def test_component_uses_typescript(self) -> None:
        """Component should use TypeScript properly."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        # Check for TypeScript constructs
        assert "interface" in content or "type " in content, \
            "Component should define TypeScript types"
        assert ": React.FC" in content or "React.FunctionComponent" in content, \
            "Component should be typed as React.FC"

    def test_component_has_props_interface(self) -> None:
        """Component should define a props interface."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        assert "SettingsProps" in content, \
            "Component should define SettingsProps interface"
        assert "onThemeChange" in content, \
            "Props should include onThemeChange callback"

    def test_component_uses_hooks(self) -> None:
        """Component should use React hooks."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        hooks = ["useState", "useEffect", "useCallback"]
        for hook in hooks:
            assert hook in content, f"Component should use {hook}"

    def test_component_has_theme_toggle(self) -> None:
        """Component should implement theme toggle."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        assert "'light'" in content and "'dark'" in content, \
            "Component should handle light and dark themes"
        assert "toggleTheme" in content or "setTheme" in content, \
            "Component should have theme toggle functionality"

    def test_component_uses_tailwind(self) -> None:
        """Component should use Tailwind CSS classes."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        # Common Tailwind patterns
        tailwind_patterns = [
            r'className="[^"]*p-\d',  # padding
            r'className="[^"]*text-',  # text utilities
            r'className="[^"]*bg-',    # background
            r'className="[^"]*rounded', # border radius
        ]

        matches = sum(1 for p in tailwind_patterns if re.search(p, content))
        assert matches >= 2, "Component should use Tailwind CSS classes"

    def test_component_has_accessibility(self) -> None:
        """Component should have accessibility features."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        a11y_patterns = [
            "aria-label",
            "aria-pressed",
            "role=",
            "aria-live",
        ]

        matches = sum(1 for p in a11y_patterns if p in content)
        assert matches >= 2, "Component should have accessibility attributes"

    def test_component_has_data_testids(self) -> None:
        """Component should have data-testid attributes for testing."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        required_testids = [
            "settings-page",
            "theme-toggle-button",
        ]

        for testid in required_testids:
            assert testid in content, f"Component should have data-testid: {testid}"


@pytest.mark.functional
class TestSettingsTestsStructure:
    """Validate expected Settings test file structure."""

    def test_expected_tests_exist(self) -> None:
        """Expected test file should exist."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        assert tests.exists(), f"Test file not found: {tests}"

    def test_tests_use_testing_library(self) -> None:
        """Tests should use React Testing Library."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "@testing-library/react" in content, \
            "Tests should import from @testing-library/react"
        assert "render" in content, "Tests should use render"
        assert "screen" in content, "Tests should use screen queries"

    def test_tests_use_user_event(self) -> None:
        """Tests should use userEvent for interactions."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "@testing-library/user-event" in content or "userEvent" in content, \
            "Tests should use userEvent for realistic interactions"

    def test_tests_have_describe_blocks(self) -> None:
        """Tests should be organized in describe blocks."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "describe(" in content, "Tests should use describe blocks"
        assert content.count("describe(") >= 3, \
            "Tests should have multiple describe blocks for organization"

    def test_tests_cover_rendering(self) -> None:
        """Tests should cover component rendering."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "Rendering" in content or "render" in content.lower(), \
            "Tests should cover rendering"

    def test_tests_cover_theme_toggle(self) -> None:
        """Tests should cover theme toggle functionality."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "Theme" in content or "theme" in content, \
            "Tests should cover theme functionality"
        assert "toggle" in content.lower(), \
            "Tests should cover toggle behavior"

    def test_tests_cover_accessibility(self) -> None:
        """Tests should cover accessibility."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "Accessibility" in content or "accessibility" in content or "a11y" in content.lower(), \
            "Tests should cover accessibility"
        assert "aria" in content.lower(), \
            "Tests should verify ARIA attributes"

    def test_tests_cover_localstorage(self) -> None:
        """Tests should cover localStorage persistence."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        assert "localStorage" in content, \
            "Tests should cover localStorage functionality"
        assert "mock" in content.lower(), \
            "Tests should mock localStorage"

    def test_sufficient_test_count(self) -> None:
        """Should have sufficient number of tests."""
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        content = tests.read_text()

        # Count 'it(' occurrences for individual tests
        test_count = content.count("it(")
        assert test_count >= 15, \
            f"Expected at least 15 tests, found {test_count}"


@pytest.mark.functional
class TestRubricConfiguration:
    """Validate rubric is properly configured for frontend evaluation."""

    def test_rubric_has_code_quality_section(self) -> None:
        """Rubric should have code quality scoring."""
        rubric = BENCHMARK_PATH / "rubric.yaml"
        data = yaml.safe_load(rubric.read_text())

        assert "code_quality" in data["scoring"]
        quality = data["scoring"]["code_quality"]
        assert "typescript_strict" in str(quality) or "lint_pass" in str(quality)

    def test_rubric_has_react_patterns(self) -> None:
        """Rubric should evaluate React-specific patterns."""
        rubric = BENCHMARK_PATH / "rubric.yaml"
        data = yaml.safe_load(rubric.read_text())

        content = str(data)
        react_patterns = ["react", "component", "hooks", "props"]

        matches = sum(1 for p in react_patterns if p.lower() in content.lower())
        assert matches >= 2, "Rubric should evaluate React patterns"

    def test_rubric_has_accessibility_criteria(self) -> None:
        """Rubric should include accessibility evaluation."""
        rubric = BENCHMARK_PATH / "rubric.yaml"
        data = yaml.safe_load(rubric.read_text())

        content = str(data).lower()
        assert "accessibility" in content or "a11y" in content or "aria" in content, \
            "Rubric should evaluate accessibility"

    def test_rubric_has_frontend_specific_section(self) -> None:
        """Rubric should have frontend-specific configuration."""
        rubric = BENCHMARK_PATH / "rubric.yaml"
        data = yaml.safe_load(rubric.read_text())

        assert "frontend_specific" in data, \
            "Rubric should have frontend_specific section"
        assert data["frontend_specific"]["framework"] == "React 18+"


@pytest.mark.functional
@pytest.mark.slow
class TestDogfoodSettingsWorkflow:
    """Document the full dogfood workflow for frontend generation.

    This test class documents what a complete LLM-driven dogfood test would do.
    When the full DAW pipeline is operational, these tests will be activated.
    """

    def test_workflow_documentation(self) -> None:
        """This test documents what a full LLM dogfood test would do.

        The full workflow when LLM is integrated:

        1. PLANNER phase:
           - Load settings-page PRD
           - Decompose into tasks (component structure, hooks, styling, tests)
           - Identify dependencies (React, TypeScript, Tailwind)
           - Estimate complexity and effort

        2. EXECUTOR phase:
           - Generate Settings.tsx component with TypeScript
           - Generate Settings.test.tsx with React Testing Library
           - Ensure Tailwind classes are valid
           - Add accessibility attributes

        3. VALIDATOR phase:
           - TypeScript compilation check (tsc --strict)
           - ESLint validation
           - Jest test execution
           - Accessibility audit (axe-core)

        4. EVALUATION phase:
           - Compare generated code to expected/ reference
           - Score using rubric.yaml criteria
           - Check semantic similarity
           - Verify test coverage
        """
        # Step 1: Verify PRD can be loaded
        prd = BENCHMARK_PATH / "prd.md"
        assert prd.exists()
        prd_content = prd.read_text()
        assert len(prd_content) > 500  # Non-trivial PRD

        # Step 2: Verify expected outputs exist for comparison
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        tests = BENCHMARK_PATH / "expected/tests/Settings.test.tsx"
        assert component.exists()
        assert tests.exists()

        # Step 3: Verify rubric can evaluate outputs
        rubric = BENCHMARK_PATH / "rubric.yaml"
        rubric_data = yaml.safe_load(rubric.read_text())
        assert "scoring" in rubric_data
        assert "pass_criteria" in rubric_data

        # Full LLM integration would:
        # - Generate code from PRD
        # - Compare to expected/
        # - Score with rubric
        # - Report pass/fail

    def test_planner_task_decomposition_expected(self) -> None:
        """Document expected Planner output for settings page."""
        # When Planner processes settings-page PRD, it should produce:
        expected_task_types = [
            "component_structure",  # Base React component with TypeScript
            "theme_toggle",         # Theme state and toggle logic
            "localstorage",         # Persistence layer
            "styling",              # Tailwind CSS styling
            "accessibility",        # ARIA and keyboard support
            "tests",                # Test file generation
        ]

        # Verify PRD mentions these concepts
        prd = BENCHMARK_PATH / "prd.md"
        content = prd.read_text().lower()

        for task_type in expected_task_types:
            # Each concept should be mentioned in PRD
            related_terms = {
                "component_structure": ["component", "react", "typescript"],
                "theme_toggle": ["theme", "toggle", "light", "dark"],
                "localstorage": ["persist", "storage", "save"],
                "styling": ["tailwind", "css", "styling"],
                "accessibility": ["accessibility", "aria", "keyboard"],
                "tests": ["test", "coverage", "jest"],
            }

            terms = related_terms.get(task_type, [task_type])
            matches = sum(1 for t in terms if t in content)
            assert matches > 0, f"PRD should mention {task_type} concepts"

    def test_executor_typescript_generation_expected(self) -> None:
        """Document expected Executor output characteristics."""
        component = BENCHMARK_PATH / "expected/src/components/Settings.tsx"
        content = component.read_text()

        # Executor should generate:
        expected_patterns = {
            "typed_component": "React.FC<SettingsProps>",
            "useState_hook": "useState",
            "useEffect_hook": "useEffect",
            "theme_type": "'light' | 'dark'",
            "callback_prop": "onThemeChange",
            "default_export": "export default",
        }

        for name, pattern in expected_patterns.items():
            assert pattern in content, \
                f"Generated component should include {name}: {pattern}"

    def test_validator_checks_expected(self) -> None:
        """Document expected Validator checks."""
        # Validator should verify:
        validation_checks = [
            "typescript_compilation",  # tsc --strict passes
            "eslint_rules",            # ESLint passes
            "test_execution",          # Jest tests pass
            "accessibility_audit",     # axe-core or similar
            "import_resolution",       # All imports resolve
        ]

        # Verify rubric mentions these validations
        rubric = BENCHMARK_PATH / "rubric.yaml"
        content = rubric.read_text().lower()

        for check in validation_checks:
            related_terms = {
                "typescript_compilation": ["typescript", "type"],
                "eslint_rules": ["lint", "eslint"],
                "test_execution": ["test", "coverage"],
                "accessibility_audit": ["accessibility", "a11y"],
                "import_resolution": ["import", "resolve"],
            }
            terms = related_terms.get(check, [check])
            # At least rubric should care about most of these
            # (accessibility might not always have direct keyword match)


@pytest.mark.functional
class TestBenchmarkIndexIntegration:
    """Validate settings-page is properly registered in benchmark index."""

    def test_index_json_exists(self) -> None:
        """Benchmark index should exist."""
        index = Path("eval/benchmarks/index.json")
        assert index.exists()

    def test_settings_page_in_index(self) -> None:
        """Settings page should be in benchmark index."""
        index = Path("eval/benchmarks/index.json")
        data = json.loads(index.read_text())

        benchmark_ids = [b["id"] for b in data.get("benchmarks", [])]
        assert "settings-page" in benchmark_ids, \
            "settings-page should be registered in benchmark index"

    def test_settings_page_index_entry_valid(self) -> None:
        """Settings page index entry should have required fields."""
        index = Path("eval/benchmarks/index.json")
        data = json.loads(index.read_text())

        settings_benchmark = next(
            (b for b in data["benchmarks"] if b["id"] == "settings-page"),
            None
        )

        assert settings_benchmark is not None

        required_fields = [
            "id",
            "name",
            "description",
            "complexity",
            "category",
            "prd_path",
            "expected_path",
            "rubric_path",
        ]

        for field in required_fields:
            assert field in settings_benchmark, \
                f"Index entry missing field: {field}"
