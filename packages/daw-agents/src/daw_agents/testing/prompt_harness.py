"""Prompt Regression Testing Harness.

This module implements PROMPT-GOV-002: a testing harness that:
1. Stores golden input/output pairs in tests/prompts/goldens/
2. Runs prompt regression tests on prompt file changes
3. Uses semantic similarity scoring against golden outputs (configurable threshold)
4. Performs automated JSON schema validation for structured outputs
5. Reports prompt drift/degradation metrics

Integrates with pytest for CI execution.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Protocols for Dependencies
# =============================================================================


class ModelRouter(Protocol):
    """Protocol for model router dependency."""

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using the model."""
        ...


class EmbeddingProvider(Protocol):
    """Protocol for embedding provider dependency."""

    async def get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text."""
        ...


# =============================================================================
# Pydantic Models
# =============================================================================


class GoldenPair(BaseModel):
    """A golden input/output pair for prompt testing.

    Stores a specific prompt input and its expected output for regression testing.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt_version: str = Field(..., description="Version of the prompt template (e.g., prd_generator_v1.0)")
    input_text: str = Field(..., description="The input text/prompt to test")
    expected_output: dict[str, Any] | str = Field(..., description="Expected output (JSON or string)")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering golden pairs")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "allow"}


class PromptTestConfig(BaseModel):
    """Configuration for prompt testing.

    Defines thresholds and options for running prompt regression tests.
    """

    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum semantic similarity score required to pass",
    )
    schema_path: Path | None = Field(default=None, description="Path to JSON schema for validation")
    timeout: float = Field(default=30.0, gt=0, description="Timeout in seconds for prompt execution")
    embedding_model: str = Field(default="text-embedding-3-small", description="Model for embeddings")

    model_config = {"arbitrary_types_allowed": True}


class SimilarityScore(BaseModel):
    """Result of similarity calculation between expected and actual outputs."""

    semantic_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity from embeddings")
    structural_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Structural similarity for JSON")
    combined_score: float = Field(..., ge=0.0, le=1.0, description="Combined similarity score")
    method: str = Field(default="embedding", description="Method used for similarity calculation")


class SchemaValidationResult(BaseModel):
    """Result of JSON schema validation."""

    valid: bool = Field(..., description="Whether the output matches the schema")
    errors: list[str] = Field(default_factory=list, description="List of validation errors")
    schema_path: Path | None = Field(default=None, description="Path to the schema used")

    model_config = {"arbitrary_types_allowed": True}


class PromptTestResult(BaseModel):
    """Result of a single prompt test."""

    passed: bool = Field(..., description="Whether the test passed")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score achieved")
    schema_valid: bool = Field(..., description="Whether schema validation passed")
    errors: list[str] = Field(default_factory=list, description="List of errors encountered")
    duration_ms: int = Field(..., ge=0, description="Test duration in milliseconds")
    golden_pair_id: str = Field(..., description="ID of the golden pair tested")
    actual_output: dict[str, Any] | str | None = Field(default=None, description="Actual output from prompt")


class PromptTestSuiteResult(BaseModel):
    """Result of running a full regression test suite."""

    prompt_version: str = Field(..., description="Prompt version tested")
    results: list[PromptTestResult] = Field(default_factory=list, description="Individual test results")
    total_tests: int = Field(..., ge=0, description="Total number of tests run")
    passed_tests: int = Field(..., ge=0, description="Number of tests that passed")
    failed_tests: int = Field(..., ge=0, description="Number of tests that failed")
    avg_similarity: float = Field(..., ge=0.0, le=1.0, description="Average similarity score")
    total_duration_ms: int = Field(..., ge=0, description="Total duration in milliseconds")

    @property
    def is_passing(self) -> bool:
        """Check if the suite is passing (all tests passed)."""
        return self.failed_tests == 0 and self.total_tests > 0


class PromptDriftReport(BaseModel):
    """Report on prompt performance drift between runs."""

    prompt_version: str = Field(..., description="Prompt version being analyzed")
    previous_avg_similarity: float = Field(..., ge=0.0, le=1.0, description="Previous average similarity")
    current_avg_similarity: float = Field(..., ge=0.0, le=1.0, description="Current average similarity")
    drift_percentage: float = Field(..., description="Percentage change in similarity (negative = degradation)")
    degraded: bool = Field(..., description="Whether drift exceeds threshold")
    threshold: float = Field(..., ge=0.0, description="Degradation threshold used")


# =============================================================================
# Utility Functions
# =============================================================================


def normalize_json(obj: Any) -> Any:
    """Normalize JSON object for comparison by sorting keys recursively.

    Args:
        obj: JSON-serializable object

    Returns:
        Normalized object with sorted keys
    """
    if isinstance(obj, dict):
        return {k: normalize_json(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [normalize_json(item) for item in obj]
    return obj


def extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract JSON from text that may contain markdown code blocks.

    Args:
        text: Text that may contain JSON in code blocks

    Returns:
        Extracted JSON object or None if not found
    """
    # Try to extract from markdown code block
    patterns = [
        r"```json\s*\n([\s\S]*?)\n```",  # ```json ... ```
        r"```\s*\n([\s\S]*?)\n```",  # ``` ... ```
        r"\{[\s\S]*\}",  # Raw JSON object
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            json_str = match.group(1) if match.lastindex else match.group(0)
            try:
                result: dict[str, Any] = json.loads(json_str)
                return result
            except json.JSONDecodeError:
                continue

    # Try parsing the entire text as JSON
    try:
        parsed: dict[str, Any] = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        return None


def calculate_structural_similarity(obj1: Any, obj2: Any) -> float:
    """Calculate structural similarity between two JSON objects.

    Uses key overlap and value comparison for nested structures.

    Args:
        obj1: First JSON object
        obj2: Second JSON object

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if obj1 == obj2:
        return 1.0

    if type(obj1) is not type(obj2):
        return 0.0

    if isinstance(obj1, dict) and isinstance(obj2, dict):
        if not obj1 and not obj2:
            return 1.0
        all_keys = set(obj1.keys()) | set(obj2.keys())
        if not all_keys:
            return 1.0

        common_keys = set(obj1.keys()) & set(obj2.keys())
        key_similarity = len(common_keys) / len(all_keys)

        if not common_keys:
            return key_similarity

        value_similarities = []
        for key in common_keys:
            value_similarities.append(calculate_structural_similarity(obj1[key], obj2[key]))

        avg_value_similarity = sum(value_similarities) / len(value_similarities) if value_similarities else 0.0
        return 0.5 * key_similarity + 0.5 * avg_value_similarity

    if isinstance(obj1, list) and isinstance(obj2, list):
        if not obj1 and not obj2:
            return 1.0
        if not obj1 or not obj2:
            return 0.0

        # Compare lists element-wise
        min_len = min(len(obj1), len(obj2))
        max_len = max(len(obj1), len(obj2))

        element_similarities = []
        for i in range(min_len):
            element_similarities.append(calculate_structural_similarity(obj1[i], obj2[i]))

        if not element_similarities:
            return 0.0

        avg_element_sim = sum(element_similarities) / len(element_similarities)
        length_penalty = min_len / max_len

        return avg_element_sim * length_penalty

    # Primitive comparison (strings, numbers, etc.)
    if isinstance(obj1, str) and isinstance(obj2, str):
        # Simple character-level similarity
        if obj1 == obj2:
            return 1.0
        common_chars = set(obj1.lower()) & set(obj2.lower())
        all_chars = set(obj1.lower()) | set(obj2.lower())
        return len(common_chars) / len(all_chars) if all_chars else 1.0

    return 0.0 if obj1 != obj2 else 1.0


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity between -1.0 and 1.0
    """
    if len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1: float = sum(a * a for a in vec1) ** 0.5
    norm2: float = sum(b * b for b in vec2) ** 0.5

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


# =============================================================================
# PromptHarness Class
# =============================================================================


class PromptHarness:
    """Prompt Regression Testing Harness.

    Provides functionality for:
    - Loading golden input/output pairs
    - Running prompt tests with similarity scoring
    - Schema validation for structured outputs
    - Drift detection and reporting
    """

    def __init__(
        self,
        model_router: ModelRouter,
        embedding_provider: EmbeddingProvider,
        goldens_path: Path,
    ) -> None:
        """Initialize the prompt harness.

        Args:
            model_router: Router for LLM calls
            embedding_provider: Provider for embedding generation
            goldens_path: Path to goldens directory
        """
        self.model_router = model_router
        self.embedding_provider = embedding_provider
        self.goldens_path = goldens_path

        # Ensure goldens directory exists
        self.goldens_path.mkdir(parents=True, exist_ok=True)

    async def load_golden_pairs(
        self,
        agent_type: str,
        prompt_version: str,
        tags: list[str] | None = None,
    ) -> list[GoldenPair]:
        """Load golden pairs from the file system.

        Golden pairs are stored in the format:
        goldens_path/{agent_type}/{prompt_version}/
            input_01.txt
            expected_01.json
            metadata_01.json (optional)

        Args:
            agent_type: Type of agent (e.g., "planner", "executor")
            prompt_version: Version of the prompt template
            tags: Optional tags to filter golden pairs

        Returns:
            List of GoldenPair objects
        """
        pairs_dir = self.goldens_path / agent_type / prompt_version

        if not pairs_dir.exists():
            logger.warning(f"No golden pairs found at {pairs_dir}")
            return []

        pairs: list[GoldenPair] = []
        input_files = sorted(pairs_dir.glob("input_*.txt"))

        for input_file in input_files:
            # Extract the index from the filename
            match = re.match(r"input_(\d+)\.txt", input_file.name)
            if not match:
                continue

            index = match.group(1)
            expected_file = pairs_dir / f"expected_{index}.json"
            metadata_file = pairs_dir / f"metadata_{index}.json"

            if not expected_file.exists():
                logger.warning(f"Missing expected file for {input_file}")
                continue

            # Read input and expected output
            input_text = input_file.read_text().strip()

            try:
                expected_output = json.loads(expected_file.read_text())
            except json.JSONDecodeError:
                expected_output = expected_file.read_text().strip()

            # Read optional metadata
            pair_tags: list[str] = []
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text())
                    pair_tags = metadata.get("tags", [])
                except json.JSONDecodeError:
                    pass

            # Filter by tags if specified
            if tags and not any(tag in pair_tags for tag in tags):
                continue

            pairs.append(
                GoldenPair(
                    prompt_version=prompt_version,
                    input_text=input_text,
                    expected_output=expected_output,
                    tags=pair_tags,
                )
            )

        return pairs

    async def run_prompt_test(
        self,
        golden_pair: GoldenPair,
        config: PromptTestConfig | None = None,
    ) -> PromptTestResult:
        """Run a single prompt test against a golden pair.

        Args:
            golden_pair: The golden input/output pair to test
            config: Test configuration (uses defaults if not provided)

        Returns:
            PromptTestResult with pass/fail and metrics
        """
        config = config or PromptTestConfig()
        start_time = time.time()
        errors: list[str] = []
        actual_output: dict[str, Any] | str | None = None
        similarity_score = 0.0
        schema_valid = True

        try:
            # Generate output using model router
            raw_output = await self.model_router.generate(golden_pair.input_text)
            actual_output = extract_json_from_text(raw_output) or raw_output

            # Calculate similarity
            similarity = await self.calculate_similarity(
                expected=golden_pair.expected_output,
                actual=actual_output,
                include_structural=isinstance(golden_pair.expected_output, dict),
            )
            similarity_score = similarity.combined_score

            # Check if similarity meets threshold
            if similarity_score < config.similarity_threshold:
                errors.append(
                    f"Similarity {similarity_score:.2%} below threshold {config.similarity_threshold:.2%}"
                )

            # Validate schema if configured
            if config.schema_path:
                schema_result = await self.validate_schema(actual_output, config.schema_path)
                schema_valid = schema_result.valid
                if not schema_valid:
                    errors.extend(schema_result.errors)

        except Exception as e:
            logger.error(f"Error running prompt test: {e}")
            errors.append(f"Error during test execution: {str(e)}")
            schema_valid = False

        duration_ms = int((time.time() - start_time) * 1000)
        passed = len(errors) == 0

        return PromptTestResult(
            passed=passed,
            similarity_score=similarity_score,
            schema_valid=schema_valid,
            errors=errors,
            duration_ms=duration_ms,
            golden_pair_id=golden_pair.id,
            actual_output=actual_output,
        )

    async def calculate_similarity(
        self,
        expected: dict[str, Any] | str,
        actual: dict[str, Any] | str,
        include_structural: bool = False,
    ) -> SimilarityScore:
        """Calculate similarity between expected and actual outputs.

        Uses embedding-based semantic similarity and optionally structural
        similarity for JSON objects.

        Args:
            expected: Expected output
            actual: Actual output
            include_structural: Include structural similarity for JSON

        Returns:
            SimilarityScore with semantic and optional structural scores
        """
        # Convert to strings for embedding comparison
        expected_str = json.dumps(expected) if isinstance(expected, dict) else str(expected)
        actual_str = json.dumps(actual) if isinstance(actual, dict) else str(actual)

        try:
            # Get embeddings
            expected_embedding = await self.embedding_provider.get_embedding(expected_str)
            actual_embedding = await self.embedding_provider.get_embedding(actual_str)

            # Calculate cosine similarity
            semantic_score = _cosine_similarity(expected_embedding, actual_embedding)
            # Normalize to 0-1 range (cosine similarity can be -1 to 1)
            semantic_score = (semantic_score + 1) / 2
        except Exception as e:
            logger.error(f"Error calculating embeddings: {e}")
            semantic_score = 0.0

        structural_score = None
        combined_score = semantic_score

        if include_structural and isinstance(expected, dict) and isinstance(actual, dict):
            structural_score = calculate_structural_similarity(expected, actual)
            # Weight: 60% semantic, 40% structural
            combined_score = 0.6 * semantic_score + 0.4 * structural_score

        return SimilarityScore(
            semantic_score=semantic_score,
            structural_score=structural_score,
            combined_score=combined_score,
            method="embedding" if not include_structural else "hybrid",
        )

    async def validate_schema(
        self,
        output: Any,
        schema_path: Path | None,
    ) -> SchemaValidationResult:
        """Validate output against a JSON schema.

        Args:
            output: Output to validate
            schema_path: Path to JSON schema file

        Returns:
            SchemaValidationResult with validation status and errors
        """
        if schema_path is None:
            return SchemaValidationResult(valid=True, errors=[], schema_path=None)

        try:
            import jsonschema
        except ImportError:
            return SchemaValidationResult(
                valid=False,
                errors=["jsonschema module not installed"],
                schema_path=schema_path,
            )

        try:
            if not schema_path.exists():
                return SchemaValidationResult(
                    valid=False,
                    errors=[f"Schema file not found: {schema_path}"],
                    schema_path=schema_path,
                )

            schema = json.loads(schema_path.read_text())
            jsonschema.validate(instance=output, schema=schema)

            return SchemaValidationResult(valid=True, errors=[], schema_path=schema_path)

        except jsonschema.ValidationError as e:
            return SchemaValidationResult(
                valid=False,
                errors=[str(e.message)],
                schema_path=schema_path,
            )
        except jsonschema.SchemaError as e:
            return SchemaValidationResult(
                valid=False,
                errors=[f"Invalid schema: {e.message}"],
                schema_path=schema_path,
            )
        except Exception as e:
            return SchemaValidationResult(
                valid=False,
                errors=[f"Validation error: {str(e)}"],
                schema_path=schema_path,
            )

    async def run_regression_suite(
        self,
        agent_type: str,
        prompt_version: str,
        config: PromptTestConfig | None = None,
        tags: list[str] | None = None,
    ) -> PromptTestSuiteResult:
        """Run full regression test suite for a prompt version.

        Args:
            agent_type: Type of agent (e.g., "planner", "executor")
            prompt_version: Version of the prompt template
            config: Test configuration
            tags: Optional tags to filter golden pairs

        Returns:
            PromptTestSuiteResult with aggregated metrics
        """
        config = config or PromptTestConfig()
        start_time = time.time()

        # Load golden pairs
        golden_pairs = await self.load_golden_pairs(agent_type, prompt_version, tags)

        if not golden_pairs:
            return PromptTestSuiteResult(
                prompt_version=prompt_version,
                results=[],
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                avg_similarity=0.0,
                total_duration_ms=0,
            )

        # Run tests
        results: list[PromptTestResult] = []
        for pair in golden_pairs:
            result = await self.run_prompt_test(pair, config)
            results.append(result)

        # Aggregate results
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = len(results) - passed_tests
        avg_similarity = sum(r.similarity_score for r in results) / len(results) if results else 0.0
        total_duration_ms = int((time.time() - start_time) * 1000)

        return PromptTestSuiteResult(
            prompt_version=prompt_version,
            results=results,
            total_tests=len(results),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            avg_similarity=avg_similarity,
            total_duration_ms=total_duration_ms,
        )

    async def detect_drift(
        self,
        previous_results: PromptTestSuiteResult,
        current_results: PromptTestSuiteResult,
        threshold: float = 0.05,
    ) -> PromptDriftReport:
        """Detect performance drift between test runs.

        Args:
            previous_results: Results from previous run
            current_results: Results from current run
            threshold: Percentage threshold for degradation alert

        Returns:
            PromptDriftReport with drift analysis
        """
        previous_avg = previous_results.avg_similarity
        current_avg = current_results.avg_similarity

        if previous_avg == 0:
            drift_percentage = 0.0
        else:
            drift_percentage = ((current_avg - previous_avg) / previous_avg) * 100

        # Degraded if drift is negative and exceeds threshold
        degraded = drift_percentage < 0 and abs(drift_percentage) > (threshold * 100)

        return PromptDriftReport(
            prompt_version=current_results.prompt_version,
            previous_avg_similarity=previous_avg,
            current_avg_similarity=current_avg,
            drift_percentage=drift_percentage,
            degraded=degraded,
            threshold=threshold,
        )

    async def generate_report(
        self,
        suite_result: PromptTestSuiteResult,
        format: str = "markdown",
    ) -> str:
        """Generate a test report.

        Args:
            suite_result: Results to report
            format: Output format ("markdown" or "json")

        Returns:
            Formatted report string
        """
        if format == "json":
            return suite_result.model_dump_json(indent=2)

        # Markdown format
        lines = [
            "# Prompt Regression Test Report",
            "",
            f"**Prompt Version**: {suite_result.prompt_version}",
            f"**Total Tests**: {suite_result.total_tests}",
            f"**Passed**: {suite_result.passed_tests}",
            f"**Failed**: {suite_result.failed_tests}",
            f"**Average Similarity**: {suite_result.avg_similarity:.2%}",
            f"**Duration**: {suite_result.total_duration_ms}ms",
            "",
        ]

        if suite_result.failed_tests > 0:
            lines.append("## Failed Tests")
            lines.append("")
            for result in suite_result.results:
                if not result.passed:
                    lines.append(f"### Golden Pair: {result.golden_pair_id}")
                    lines.append(f"- Similarity: {result.similarity_score:.2%}")
                    lines.append(f"- Schema Valid: {result.schema_valid}")
                    if result.errors:
                        lines.append("- Errors:")
                        for error in result.errors:
                            lines.append(f"  - {error}")
                    lines.append("")

        return "\n".join(lines)
