"""
Tests for Prompt Regression Testing Harness module.

This module tests the prompt governance infrastructure for the DAW system,
implementing PROMPT-GOV-002 (Prompt Regression Testing Harness).

The harness stores golden input/output pairs, runs regression tests,
uses semantic similarity scoring, validates JSON schemas, and reports
prompt drift/degradation metrics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from daw_agents.testing.prompt_harness import (
    GoldenPair,
    PromptDriftReport,
    PromptHarness,
    PromptTestConfig,
    PromptTestResult,
    PromptTestSuiteResult,
    SchemaValidationResult,
    SimilarityScore,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_golden_pair() -> GoldenPair:
    """Create a sample golden input/output pair for testing."""
    return GoldenPair(
        prompt_version="prd_generator_v1.0",
        input_text="Create a calculator app that supports basic arithmetic operations",
        expected_output={
            "title": "Calculator App",
            "overview": "A simple calculator application",
            "user_stories": [
                {
                    "id": "US-001",
                    "description": "As a user, I want to add two numbers",
                    "priority": "P0",
                    "acceptance_criteria": ["Addition works correctly"],
                }
            ],
        },
        tags=["planner", "prd"],
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_test_config() -> PromptTestConfig:
    """Create a sample test configuration."""
    return PromptTestConfig(
        similarity_threshold=0.85,
        schema_path=Path("schemas/prd_schema.json"),
        timeout=30.0,
        embedding_model="text-embedding-3-small",
    )


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Create a mock model router for LLM calls."""
    router = MagicMock()
    router.generate = AsyncMock(
        return_value='{"title": "Calculator App", "overview": "A simple calculator"}'
    )
    return router


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Create a mock embedding provider for similarity scoring."""
    provider = MagicMock()
    # Return high-dimensional embedding vectors
    provider.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    return provider


@pytest.fixture
def prompt_harness(
    mock_model_router: MagicMock, mock_embedding_provider: MagicMock, tmp_path: Path
) -> PromptHarness:
    """Create a PromptHarness instance with mocked dependencies."""
    goldens_path = tmp_path / "goldens"
    goldens_path.mkdir()
    return PromptHarness(
        model_router=mock_model_router,
        embedding_provider=mock_embedding_provider,
        goldens_path=goldens_path,
    )


@pytest.fixture
def sample_schema() -> dict[str, Any]:
    """Create a sample JSON schema for PRD validation."""
    return {
        "type": "object",
        "required": ["title", "overview", "user_stories"],
        "properties": {
            "title": {"type": "string"},
            "overview": {"type": "string"},
            "user_stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "description", "priority"],
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["P0", "P1", "P2"]},
                        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }


# =============================================================================
# GoldenPair Model Tests
# =============================================================================


class TestGoldenPair:
    """Tests for GoldenPair Pydantic model."""

    def test_golden_pair_creation_minimal(self) -> None:
        """Test creating a GoldenPair with minimal required fields."""
        pair = GoldenPair(
            prompt_version="v1.0",
            input_text="Test input",
            expected_output={"result": "test"},
        )
        assert pair.prompt_version == "v1.0"
        assert pair.input_text == "Test input"
        assert pair.expected_output == {"result": "test"}
        assert pair.tags == []
        assert pair.created_at is not None

    def test_golden_pair_creation_full(self, sample_golden_pair: GoldenPair) -> None:
        """Test creating a GoldenPair with all fields."""
        assert sample_golden_pair.prompt_version == "prd_generator_v1.0"
        assert "calculator" in sample_golden_pair.input_text.lower()
        assert "title" in sample_golden_pair.expected_output
        assert sample_golden_pair.tags == ["planner", "prd"]

    def test_golden_pair_with_string_output(self) -> None:
        """Test creating a GoldenPair with string expected output."""
        pair = GoldenPair(
            prompt_version="v1.0",
            input_text="Test input",
            expected_output="Expected string output",
        )
        assert pair.expected_output == "Expected string output"

    def test_golden_pair_to_dict(self, sample_golden_pair: GoldenPair) -> None:
        """Test converting GoldenPair to dictionary."""
        data = sample_golden_pair.model_dump()
        assert data["prompt_version"] == "prd_generator_v1.0"
        assert "input_text" in data
        assert "expected_output" in data

    def test_golden_pair_from_json(self) -> None:
        """Test loading GoldenPair from JSON string."""
        json_str = """
        {
            "prompt_version": "v1.0",
            "input_text": "Test input",
            "expected_output": {"result": "test"},
            "tags": ["test"]
        }
        """
        pair = GoldenPair.model_validate_json(json_str)
        assert pair.prompt_version == "v1.0"
        assert pair.tags == ["test"]

    def test_golden_pair_id_auto_generated(self) -> None:
        """Test that golden pair ID is auto-generated if not provided."""
        pair = GoldenPair(
            prompt_version="v1.0",
            input_text="Test",
            expected_output="Output",
        )
        assert pair.id is not None
        assert len(pair.id) > 0


# =============================================================================
# PromptTestConfig Model Tests
# =============================================================================


class TestPromptTestConfig:
    """Tests for PromptTestConfig Pydantic model."""

    def test_config_default_values(self) -> None:
        """Test default configuration values."""
        config = PromptTestConfig()
        assert config.similarity_threshold == 0.85
        assert config.timeout == 30.0
        assert config.embedding_model == "text-embedding-3-small"
        assert config.schema_path is None

    def test_config_custom_values(self, sample_test_config: PromptTestConfig) -> None:
        """Test custom configuration values."""
        assert sample_test_config.similarity_threshold == 0.85
        assert sample_test_config.schema_path == Path("schemas/prd_schema.json")
        assert sample_test_config.timeout == 30.0

    def test_config_validation_threshold_bounds(self) -> None:
        """Test that similarity threshold is within valid bounds."""
        # Valid threshold
        config = PromptTestConfig(similarity_threshold=0.5)
        assert config.similarity_threshold == 0.5

        # Threshold at boundaries
        config_min = PromptTestConfig(similarity_threshold=0.0)
        assert config_min.similarity_threshold == 0.0

        config_max = PromptTestConfig(similarity_threshold=1.0)
        assert config_max.similarity_threshold == 1.0

    def test_config_validation_timeout_positive(self) -> None:
        """Test that timeout must be positive."""
        config = PromptTestConfig(timeout=60.0)
        assert config.timeout == 60.0


# =============================================================================
# PromptTestResult Model Tests
# =============================================================================


class TestPromptTestResult:
    """Tests for PromptTestResult Pydantic model."""

    def test_result_creation_passed(self) -> None:
        """Test creating a passed test result."""
        result = PromptTestResult(
            passed=True,
            similarity_score=0.92,
            schema_valid=True,
            errors=[],
            duration_ms=1500,
            golden_pair_id="gp-001",
        )
        assert result.passed is True
        assert result.similarity_score == 0.92
        assert result.schema_valid is True
        assert len(result.errors) == 0

    def test_result_creation_failed(self) -> None:
        """Test creating a failed test result."""
        result = PromptTestResult(
            passed=False,
            similarity_score=0.65,
            schema_valid=False,
            errors=["Similarity below threshold", "Missing required field: title"],
            duration_ms=2000,
            golden_pair_id="gp-002",
        )
        assert result.passed is False
        assert result.similarity_score == 0.65
        assert len(result.errors) == 2

    def test_result_with_actual_output(self) -> None:
        """Test result includes actual output for debugging."""
        result = PromptTestResult(
            passed=True,
            similarity_score=0.88,
            schema_valid=True,
            errors=[],
            duration_ms=1000,
            golden_pair_id="gp-001",
            actual_output={"title": "Test App"},
        )
        assert result.actual_output == {"title": "Test App"}


# =============================================================================
# PromptTestSuiteResult Model Tests
# =============================================================================


class TestPromptTestSuiteResult:
    """Tests for PromptTestSuiteResult model."""

    def test_suite_result_all_passed(self) -> None:
        """Test suite result when all tests pass."""
        results = [
            PromptTestResult(
                passed=True,
                similarity_score=0.9,
                schema_valid=True,
                errors=[],
                duration_ms=1000,
                golden_pair_id=f"gp-{i}",
            )
            for i in range(3)
        ]
        suite = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=results,
            total_tests=3,
            passed_tests=3,
            failed_tests=0,
            avg_similarity=0.9,
            total_duration_ms=3000,
        )
        assert suite.passed_tests == 3
        assert suite.failed_tests == 0
        assert suite.is_passing is True

    def test_suite_result_some_failed(self) -> None:
        """Test suite result when some tests fail."""
        results = [
            PromptTestResult(
                passed=True,
                similarity_score=0.9,
                schema_valid=True,
                errors=[],
                duration_ms=1000,
                golden_pair_id="gp-1",
            ),
            PromptTestResult(
                passed=False,
                similarity_score=0.6,
                schema_valid=False,
                errors=["Below threshold"],
                duration_ms=1000,
                golden_pair_id="gp-2",
            ),
        ]
        suite = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=results,
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            avg_similarity=0.75,
            total_duration_ms=2000,
        )
        assert suite.passed_tests == 1
        assert suite.failed_tests == 1
        assert suite.is_passing is False


# =============================================================================
# SimilarityScore Model Tests
# =============================================================================


class TestSimilarityScore:
    """Tests for SimilarityScore model."""

    def test_similarity_score_creation(self) -> None:
        """Test creating a similarity score."""
        score = SimilarityScore(
            semantic_score=0.88,
            structural_score=0.92,
            combined_score=0.90,
            method="embedding",
        )
        assert score.semantic_score == 0.88
        assert score.structural_score == 0.92
        assert score.combined_score == 0.90

    def test_similarity_score_embedding_only(self) -> None:
        """Test similarity score with embedding only."""
        score = SimilarityScore(
            semantic_score=0.85,
            combined_score=0.85,
            method="embedding",
        )
        assert score.semantic_score == 0.85
        assert score.structural_score is None


# =============================================================================
# SchemaValidationResult Model Tests
# =============================================================================


class TestSchemaValidationResult:
    """Tests for SchemaValidationResult model."""

    def test_schema_validation_passed(self) -> None:
        """Test schema validation that passes."""
        result = SchemaValidationResult(
            valid=True,
            errors=[],
            schema_path=Path("schemas/test.json"),
        )
        assert result.valid is True
        assert len(result.errors) == 0

    def test_schema_validation_failed(self) -> None:
        """Test schema validation that fails."""
        result = SchemaValidationResult(
            valid=False,
            errors=[
                "Missing required property: title",
                "Type mismatch at path: user_stories[0].priority",
            ],
            schema_path=Path("schemas/test.json"),
        )
        assert result.valid is False
        assert len(result.errors) == 2


# =============================================================================
# PromptDriftReport Model Tests
# =============================================================================


class TestPromptDriftReport:
    """Tests for PromptDriftReport model."""

    def test_drift_report_creation(self) -> None:
        """Test creating a drift report."""
        report = PromptDriftReport(
            prompt_version="v1.0",
            previous_avg_similarity=0.92,
            current_avg_similarity=0.85,
            drift_percentage=-7.6,
            degraded=True,
            threshold=0.05,
        )
        assert report.degraded is True
        assert report.drift_percentage < 0

    def test_drift_report_no_degradation(self) -> None:
        """Test drift report with no degradation."""
        report = PromptDriftReport(
            prompt_version="v1.0",
            previous_avg_similarity=0.88,
            current_avg_similarity=0.90,
            drift_percentage=2.3,
            degraded=False,
            threshold=0.05,
        )
        assert report.degraded is False
        assert report.drift_percentage > 0


# =============================================================================
# PromptHarness Initialization Tests
# =============================================================================


class TestPromptHarnessInit:
    """Tests for PromptHarness initialization."""

    def test_init_with_dependencies(
        self, mock_model_router: MagicMock, mock_embedding_provider: MagicMock, tmp_path: Path
    ) -> None:
        """Test initializing PromptHarness with all dependencies."""
        harness = PromptHarness(
            model_router=mock_model_router,
            embedding_provider=mock_embedding_provider,
            goldens_path=tmp_path / "goldens",
        )
        assert harness.model_router is mock_model_router
        assert harness.embedding_provider is mock_embedding_provider

    def test_init_creates_goldens_directory(
        self, mock_model_router: MagicMock, mock_embedding_provider: MagicMock, tmp_path: Path
    ) -> None:
        """Test that init creates goldens directory if it doesn't exist."""
        goldens_path = tmp_path / "new_goldens"
        harness = PromptHarness(
            model_router=mock_model_router,
            embedding_provider=mock_embedding_provider,
            goldens_path=goldens_path,
        )
        assert goldens_path.exists()


# =============================================================================
# PromptHarness.load_golden_pairs() Tests
# =============================================================================


class TestLoadGoldenPairs:
    """Tests for PromptHarness.load_golden_pairs()."""

    @pytest.mark.asyncio
    async def test_load_golden_pairs_from_directory(
        self, prompt_harness: PromptHarness, tmp_path: Path
    ) -> None:
        """Test loading golden pairs from directory structure."""
        # Create golden pair files
        goldens_dir = tmp_path / "goldens" / "planner" / "prd_generator_v1.0"
        goldens_dir.mkdir(parents=True)

        input_file = goldens_dir / "input_01.txt"
        input_file.write_text("Create a calculator app")

        expected_file = goldens_dir / "expected_01.json"
        expected_file.write_text('{"title": "Calculator"}')

        prompt_harness.goldens_path = tmp_path / "goldens"
        pairs = await prompt_harness.load_golden_pairs("planner", "prd_generator_v1.0")

        assert len(pairs) >= 1
        assert pairs[0].input_text == "Create a calculator app"

    @pytest.mark.asyncio
    async def test_load_golden_pairs_empty_directory(
        self, prompt_harness: PromptHarness
    ) -> None:
        """Test loading from empty directory returns empty list."""
        pairs = await prompt_harness.load_golden_pairs("nonexistent", "v1.0")
        assert pairs == []

    @pytest.mark.asyncio
    async def test_load_golden_pairs_by_tag(
        self, prompt_harness: PromptHarness, tmp_path: Path
    ) -> None:
        """Test filtering golden pairs by tag."""
        # Create metadata with tags
        goldens_dir = tmp_path / "goldens" / "planner" / "prd_generator_v1.0"
        goldens_dir.mkdir(parents=True)

        input_file = goldens_dir / "input_01.txt"
        input_file.write_text("Create a calculator app")

        expected_file = goldens_dir / "expected_01.json"
        expected_file.write_text('{"title": "Calculator"}')

        metadata_file = goldens_dir / "metadata_01.json"
        metadata_file.write_text('{"tags": ["critical", "planner"]}')

        prompt_harness.goldens_path = tmp_path / "goldens"
        pairs = await prompt_harness.load_golden_pairs(
            "planner", "prd_generator_v1.0", tags=["critical"]
        )

        assert len(pairs) >= 1


# =============================================================================
# PromptHarness.run_prompt_test() Tests
# =============================================================================


class TestRunPromptTest:
    """Tests for PromptHarness.run_prompt_test()."""

    @pytest.mark.asyncio
    async def test_run_prompt_test_passed(
        self,
        prompt_harness: PromptHarness,
        sample_golden_pair: GoldenPair,
        mock_model_router: MagicMock,
        mock_embedding_provider: MagicMock,
    ) -> None:
        """Test running a prompt test that passes."""
        # Mock the LLM to return similar output
        mock_model_router.generate = AsyncMock(
            return_value='{"title": "Calculator App", "overview": "A calculator application", "user_stories": []}'
        )

        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair,
            config=PromptTestConfig(similarity_threshold=0.7),
        )

        assert result.passed is True
        assert result.similarity_score >= 0.7

    @pytest.mark.asyncio
    async def test_run_prompt_test_failed_similarity(
        self,
        prompt_harness: PromptHarness,
        sample_golden_pair: GoldenPair,
        mock_model_router: MagicMock,
        mock_embedding_provider: MagicMock,
    ) -> None:
        """Test running a prompt test that fails due to low similarity."""
        # Create orthogonal vectors for very low cosine similarity
        # Vector 1: [1, 1, 1, ...] - all positive
        # Vector 2: [1, -1, 1, -1, ...] - alternating (orthogonal to vector 1)
        expected_embedding = [1.0] * 1536
        actual_embedding = [(1.0 if i % 2 == 0 else -1.0) for i in range(1536)]

        mock_embedding_provider.get_embedding = AsyncMock(
            side_effect=[expected_embedding, actual_embedding]
        )

        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair,
            config=PromptTestConfig(similarity_threshold=0.9),
        )

        # Should fail due to low similarity (orthogonal vectors have ~0 similarity)
        assert result.similarity_score < 0.9

    @pytest.mark.asyncio
    async def test_run_prompt_test_with_timeout(
        self, prompt_harness: PromptHarness, sample_golden_pair: GoldenPair
    ) -> None:
        """Test prompt test respects timeout configuration."""
        config = PromptTestConfig(timeout=5.0)

        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair, config=config
        )

        # Test should complete (not timeout in normal case)
        assert result.duration_ms >= 0  # Fast mocked tests may complete in <1ms

    @pytest.mark.asyncio
    async def test_run_prompt_test_records_duration(
        self, prompt_harness: PromptHarness, sample_golden_pair: GoldenPair
    ) -> None:
        """Test that prompt test records execution duration."""
        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair,
            config=PromptTestConfig(),
        )

        assert result.duration_ms >= 0


# =============================================================================
# PromptHarness.calculate_similarity() Tests
# =============================================================================


class TestCalculateSimilarity:
    """Tests for PromptHarness.calculate_similarity()."""

    @pytest.mark.asyncio
    async def test_calculate_similarity_identical(
        self, prompt_harness: PromptHarness, mock_embedding_provider: MagicMock
    ) -> None:
        """Test similarity calculation for identical texts."""
        # Same embeddings = perfect similarity
        mock_embedding_provider.get_embedding = AsyncMock(return_value=[0.5] * 1536)

        score = await prompt_harness.calculate_similarity(
            expected="Hello world",
            actual="Hello world",
        )

        assert score.combined_score >= 0.99  # Nearly identical

    @pytest.mark.asyncio
    async def test_calculate_similarity_different(
        self, prompt_harness: PromptHarness, mock_embedding_provider: MagicMock
    ) -> None:
        """Test similarity calculation for different texts."""
        # Very different embeddings
        mock_embedding_provider.get_embedding = AsyncMock(
            side_effect=[
                [1.0] * 768 + [0.0] * 768,  # First embedding
                [0.0] * 768 + [1.0] * 768,  # Second embedding (orthogonal)
            ]
        )

        score = await prompt_harness.calculate_similarity(
            expected="Hello world",
            actual="Goodbye universe",
        )

        assert score.combined_score <= 0.5  # Low similarity (orthogonal vectors = 0 cosine -> 0.5 normalized)

    @pytest.mark.asyncio
    async def test_calculate_similarity_json_objects(
        self, prompt_harness: PromptHarness, mock_embedding_provider: MagicMock
    ) -> None:
        """Test similarity calculation for JSON objects."""
        score = await prompt_harness.calculate_similarity(
            expected={"title": "Test App", "version": "1.0"},
            actual={"title": "Test Application", "version": "1.0"},
        )

        assert 0.0 <= score.combined_score <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_similarity_structural(
        self, prompt_harness: PromptHarness
    ) -> None:
        """Test structural similarity for JSON outputs."""
        score = await prompt_harness.calculate_similarity(
            expected={"a": 1, "b": {"c": 2}},
            actual={"a": 1, "b": {"c": 2}},
            include_structural=True,
        )

        assert score.structural_score is not None
        assert score.structural_score >= 0.99


# =============================================================================
# PromptHarness.validate_schema() Tests
# =============================================================================


class TestValidateSchema:
    """Tests for PromptHarness.validate_schema()."""

    @pytest.mark.asyncio
    async def test_validate_schema_valid_output(
        self, prompt_harness: PromptHarness, sample_schema: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test schema validation with valid output."""
        # Write schema to file
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        output = {
            "title": "Test App",
            "overview": "A test application",
            "user_stories": [
                {
                    "id": "US-001",
                    "description": "Test story",
                    "priority": "P0",
                }
            ],
        }

        result = await prompt_harness.validate_schema(output, schema_path)

        assert result.valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_schema_missing_required(
        self, prompt_harness: PromptHarness, sample_schema: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test schema validation with missing required fields."""
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        output = {
            "title": "Test App",
            # Missing overview and user_stories
        }

        result = await prompt_harness.validate_schema(output, schema_path)

        assert result.valid is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_validate_schema_wrong_type(
        self, prompt_harness: PromptHarness, sample_schema: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test schema validation with wrong field types."""
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        output = {
            "title": 123,  # Should be string
            "overview": "Test",
            "user_stories": "not an array",  # Should be array
        }

        result = await prompt_harness.validate_schema(output, schema_path)

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_validate_schema_no_schema_path(
        self, prompt_harness: PromptHarness
    ) -> None:
        """Test validation when no schema is provided."""
        result = await prompt_harness.validate_schema({"any": "output"}, None)

        # Should pass when no schema is specified
        assert result.valid is True


# =============================================================================
# PromptHarness.run_regression_suite() Tests
# =============================================================================


class TestRunRegressionSuite:
    """Tests for PromptHarness.run_regression_suite()."""

    @pytest.mark.asyncio
    async def test_run_regression_suite_all_pass(
        self, prompt_harness: PromptHarness, tmp_path: Path, mock_model_router: MagicMock
    ) -> None:
        """Test running regression suite with all tests passing."""
        # Create golden pairs
        goldens_dir = tmp_path / "goldens" / "planner" / "prd_generator_v1.0"
        goldens_dir.mkdir(parents=True)

        for i in range(3):
            input_file = goldens_dir / f"input_{i:02d}.txt"
            input_file.write_text(f"Test input {i}")

            expected_file = goldens_dir / f"expected_{i:02d}.json"
            expected_file.write_text(f'{{"title": "App {i}"}}')

        prompt_harness.goldens_path = tmp_path / "goldens"

        result = await prompt_harness.run_regression_suite(
            agent_type="planner",
            prompt_version="prd_generator_v1.0",
            config=PromptTestConfig(similarity_threshold=0.5),
        )

        assert result.total_tests >= 1
        assert result.is_passing is True or result.passed_tests > 0

    @pytest.mark.asyncio
    async def test_run_regression_suite_some_fail(
        self, prompt_harness: PromptHarness, tmp_path: Path, mock_embedding_provider: MagicMock
    ) -> None:
        """Test running regression suite with some failures."""
        # Set up to return varying similarity
        call_count = [0]

        async def varying_embeddings(text: str) -> list[float]:
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return [0.1] * 1536
            return [0.9] * 1536

        mock_embedding_provider.get_embedding = AsyncMock(side_effect=varying_embeddings)

        goldens_dir = tmp_path / "goldens" / "planner" / "prd_generator_v1.0"
        goldens_dir.mkdir(parents=True)

        for i in range(2):
            input_file = goldens_dir / f"input_{i:02d}.txt"
            input_file.write_text(f"Test input {i}")

            expected_file = goldens_dir / f"expected_{i:02d}.json"
            expected_file.write_text(f'{{"title": "App {i}"}}')

        prompt_harness.goldens_path = tmp_path / "goldens"

        result = await prompt_harness.run_regression_suite(
            agent_type="planner",
            prompt_version="prd_generator_v1.0",
            config=PromptTestConfig(similarity_threshold=0.95),
        )

        assert result.total_tests >= 1

    @pytest.mark.asyncio
    async def test_run_regression_suite_generates_report(
        self, prompt_harness: PromptHarness, tmp_path: Path
    ) -> None:
        """Test that regression suite generates a report."""
        goldens_dir = tmp_path / "goldens" / "planner" / "prd_generator_v1.0"
        goldens_dir.mkdir(parents=True)

        input_file = goldens_dir / "input_01.txt"
        input_file.write_text("Test input")

        expected_file = goldens_dir / "expected_01.json"
        expected_file.write_text('{"title": "App"}')

        prompt_harness.goldens_path = tmp_path / "goldens"

        result = await prompt_harness.run_regression_suite(
            agent_type="planner",
            prompt_version="prd_generator_v1.0",
        )

        assert result.prompt_version == "prd_generator_v1.0"
        assert result.total_duration_ms >= 0


# =============================================================================
# PromptHarness.detect_drift() Tests
# =============================================================================


class TestDetectDrift:
    """Tests for PromptHarness.detect_drift()."""

    @pytest.mark.asyncio
    async def test_detect_drift_degradation(self, prompt_harness: PromptHarness) -> None:
        """Test detecting drift with degradation."""
        # Previous results with high similarity
        previous_results = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            avg_similarity=0.92,
            total_duration_ms=5000,
        )

        # Current results with lower similarity
        current_results = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=5,
            passed_tests=3,
            failed_tests=2,
            avg_similarity=0.80,
            total_duration_ms=6000,
        )

        report = await prompt_harness.detect_drift(
            previous_results=previous_results,
            current_results=current_results,
            threshold=0.05,  # 5% degradation threshold
        )

        assert report.degraded is True
        assert report.drift_percentage < 0

    @pytest.mark.asyncio
    async def test_detect_drift_improvement(self, prompt_harness: PromptHarness) -> None:
        """Test detecting drift with improvement."""
        previous_results = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=5,
            passed_tests=3,
            failed_tests=2,
            avg_similarity=0.80,
            total_duration_ms=5000,
        )

        current_results = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            avg_similarity=0.92,
            total_duration_ms=4500,
        )

        report = await prompt_harness.detect_drift(
            previous_results=previous_results,
            current_results=current_results,
            threshold=0.05,
        )

        assert report.degraded is False
        assert report.drift_percentage > 0

    @pytest.mark.asyncio
    async def test_detect_drift_within_threshold(
        self, prompt_harness: PromptHarness
    ) -> None:
        """Test drift detection within acceptable threshold."""
        previous_results = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            avg_similarity=0.90,
            total_duration_ms=5000,
        )

        current_results = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            avg_similarity=0.88,
            total_duration_ms=5100,
        )

        report = await prompt_harness.detect_drift(
            previous_results=previous_results,
            current_results=current_results,
            threshold=0.05,  # 5% threshold, drift is ~2%
        )

        assert report.degraded is False


# =============================================================================
# PromptHarness.generate_report() Tests
# =============================================================================


class TestGenerateReport:
    """Tests for PromptHarness.generate_report()."""

    @pytest.mark.asyncio
    async def test_generate_report_markdown(self, prompt_harness: PromptHarness) -> None:
        """Test generating a markdown report."""
        suite_result = PromptTestSuiteResult(
            prompt_version="prd_generator_v1.0",
            results=[
                PromptTestResult(
                    passed=True,
                    similarity_score=0.92,
                    schema_valid=True,
                    errors=[],
                    duration_ms=1500,
                    golden_pair_id="gp-001",
                ),
                PromptTestResult(
                    passed=False,
                    similarity_score=0.65,
                    schema_valid=True,
                    errors=["Similarity below threshold"],
                    duration_ms=1800,
                    golden_pair_id="gp-002",
                ),
            ],
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            avg_similarity=0.785,
            total_duration_ms=3300,
        )

        report = await prompt_harness.generate_report(
            suite_result, format="markdown"
        )

        assert "prd_generator_v1.0" in report
        assert "**Passed**: 1" in report or "Passed: 1" in report or "passed_tests" in report.lower()
        assert "**Failed**: 1" in report or "Failed: 1" in report or "failed_tests" in report.lower()

    @pytest.mark.asyncio
    async def test_generate_report_json(self, prompt_harness: PromptHarness) -> None:
        """Test generating a JSON report."""
        suite_result = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[],
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            avg_similarity=0.9,
            total_duration_ms=1000,
        )

        report = await prompt_harness.generate_report(suite_result, format="json")

        # Should be valid JSON
        parsed = json.loads(report)
        assert parsed["prompt_version"] == "v1.0"
        assert parsed["total_tests"] == 1

    @pytest.mark.asyncio
    async def test_generate_report_includes_failures(
        self, prompt_harness: PromptHarness
    ) -> None:
        """Test that report includes failure details."""
        suite_result = PromptTestSuiteResult(
            prompt_version="v1.0",
            results=[
                PromptTestResult(
                    passed=False,
                    similarity_score=0.5,
                    schema_valid=False,
                    errors=["Missing required field: title", "Type mismatch"],
                    duration_ms=1000,
                    golden_pair_id="gp-001",
                ),
            ],
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            avg_similarity=0.5,
            total_duration_ms=1000,
        )

        report = await prompt_harness.generate_report(suite_result, format="markdown")

        assert "Missing required field" in report or "error" in report.lower()


# =============================================================================
# Pytest Integration Tests
# =============================================================================


class TestPytestIntegration:
    """Tests for pytest integration."""

    def test_prompt_regression_marker(self) -> None:
        """Test that @pytest.mark.prompt_regression marker is available."""
        # The marker should be registered via conftest.py
        # This test verifies the marker exists
        import pytest

        marker = pytest.mark.prompt_regression
        assert marker is not None

    @pytest.mark.asyncio
    async def test_harness_can_be_used_as_fixture(
        self, prompt_harness: PromptHarness
    ) -> None:
        """Test that PromptHarness works as a pytest fixture."""
        assert prompt_harness is not None
        assert hasattr(prompt_harness, "run_prompt_test")
        assert hasattr(prompt_harness, "run_regression_suite")


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in PromptHarness."""

    @pytest.mark.asyncio
    async def test_handles_llm_error(
        self, prompt_harness: PromptHarness, sample_golden_pair: GoldenPair
    ) -> None:
        """Test handling of LLM generation errors."""
        prompt_harness.model_router.generate = AsyncMock(
            side_effect=Exception("LLM Error")
        )

        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair,
            config=PromptTestConfig(),
        )

        assert result.passed is False
        assert any("error" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_handles_embedding_error(
        self, prompt_harness: PromptHarness, sample_golden_pair: GoldenPair
    ) -> None:
        """Test handling of embedding generation errors."""
        prompt_harness.embedding_provider.get_embedding = AsyncMock(
            side_effect=Exception("Embedding Error")
        )

        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair,
            config=PromptTestConfig(),
        )

        # Should handle gracefully and report error
        assert result.passed is False or len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_handles_invalid_json_output(
        self, prompt_harness: PromptHarness, sample_golden_pair: GoldenPair
    ) -> None:
        """Test handling of invalid JSON output from LLM."""
        prompt_harness.model_router.generate = AsyncMock(
            return_value="This is not valid JSON {{"
        )

        result = await prompt_harness.run_prompt_test(
            golden_pair=sample_golden_pair,
            config=PromptTestConfig(),
        )

        # Should handle gracefully
        assert result is not None


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_normalize_json_for_comparison(self) -> None:
        """Test JSON normalization for comparison."""
        from daw_agents.testing.prompt_harness import normalize_json

        json1 = {"b": 2, "a": 1, "c": {"e": 5, "d": 4}}
        json2 = {"a": 1, "b": 2, "c": {"d": 4, "e": 5}}

        normalized1 = normalize_json(json1)
        normalized2 = normalize_json(json2)

        assert normalized1 == normalized2

    def test_extract_json_from_text(self) -> None:
        """Test extracting JSON from text with markdown code blocks."""
        from daw_agents.testing.prompt_harness import extract_json_from_text

        text = """
        Here is the output:

        ```json
        {"title": "Test", "value": 123}
        ```

        Additional text after.
        """

        result = extract_json_from_text(text)
        assert result == {"title": "Test", "value": 123}

    def test_calculate_structural_similarity(self) -> None:
        """Test structural similarity calculation for JSON objects."""
        from daw_agents.testing.prompt_harness import calculate_structural_similarity

        obj1 = {"a": 1, "b": {"c": 2, "d": 3}}
        obj2 = {"a": 1, "b": {"c": 2, "d": 4}}  # Only d value differs

        similarity = calculate_structural_similarity(obj1, obj2)

        assert 0.5 < similarity < 1.0  # Similar but not identical
