"""Test suite for Agent Similarity Scoring (EVAL-003).

This test module validates the similarity scoring implementation that compares
agent outputs against golden references. The module provides:
- Embedding-based comparison for textual outputs
- AST comparison for code outputs
- Combined scoring with detailed divergence reports

Tests cover:
- SimilarityScore Pydantic model
- DivergenceReport model for breakdown details
- TextSimilarityScorer using embeddings
- CodeSimilarityScorer using AST comparison
- AgentSimilarityEvaluator combining both approaches
- 85% similarity threshold validation

TDD Phase: RED - These tests define expected behavior before implementation.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from daw_agents.eval.similarity import (
    AgentSimilarityEvaluator,
    CodeSimilarityScorer,
    DivergenceReport,
    SimilarityConfig,
    SimilarityScore,
    TextSimilarityScorer,
)

if TYPE_CHECKING:
    pass


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def similarity_config() -> SimilarityConfig:
    """Create a test SimilarityConfig with default values."""
    return SimilarityConfig(
        similarity_threshold=0.85,
        embedding_model="text-embedding-3-small",
        use_structural_weight=True,
        structural_weight=0.3,
        embedding_weight=0.7,
    )


@pytest.fixture
def sample_prd_reference() -> str:
    """Create a sample golden PRD reference."""
    return """# Calculator Application PRD

## Overview
Build a simple calculator application with basic arithmetic operations.

## Functional Requirements
- FR-01: Addition of two numbers
- FR-02: Subtraction of two numbers
- FR-03: Multiplication of two numbers
- FR-04: Division of two numbers with error handling

## Technical Requirements
- TR-01: Python implementation
- TR-02: Unit test coverage >= 80%
- TR-03: Type hints required
"""


@pytest.fixture
def sample_prd_output_high_similarity() -> str:
    """Create a sample agent output with high similarity to reference."""
    return """# Calculator Application PRD

## Overview
Build a simple calculator application with basic arithmetic operations.

## Functional Requirements
- FR-01: Addition of two numbers
- FR-02: Subtraction of two numbers
- FR-03: Multiplication of two numbers
- FR-04: Division of two numbers with proper error handling

## Technical Requirements
- TR-01: Python implementation
- TR-02: Unit test coverage >= 80%
- TR-03: Type hints required
"""


@pytest.fixture
def sample_prd_output_low_similarity() -> str:
    """Create a sample agent output with low similarity to reference."""
    return """# Todo App Documentation

## Summary
A to-do list application for managing daily tasks.

## Features
- Add tasks
- Remove tasks
- Mark complete

## Stack
- React frontend
- Node backend
"""


@pytest.fixture
def sample_code_reference() -> str:
    """Create a sample golden code reference."""
    return '''def calculate(a: int, b: int, operation: str) -> float:
    """Perform arithmetic calculation.

    Args:
        a: First operand
        b: Second operand
        operation: One of 'add', 'sub', 'mul', 'div'

    Returns:
        Result of the calculation

    Raises:
        ValueError: If operation is invalid
        ZeroDivisionError: If dividing by zero
    """
    if operation == "add":
        return a + b
    elif operation == "sub":
        return a - b
    elif operation == "mul":
        return a * b
    elif operation == "div":
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return a / b
    else:
        raise ValueError(f"Invalid operation: {operation}")
'''


@pytest.fixture
def sample_code_output_high_similarity() -> str:
    """Create a sample code output with high AST similarity."""
    return '''def calculate(a: int, b: int, operation: str) -> float:
    """Execute arithmetic operation.

    Args:
        a: First number
        b: Second number
        operation: The operation to perform

    Returns:
        Calculation result
    """
    if operation == "add":
        return a + b
    elif operation == "sub":
        return a - b
    elif operation == "mul":
        return a * b
    elif operation == "div":
        if b == 0:
            raise ZeroDivisionError("Division by zero not allowed")
        return a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")
'''


@pytest.fixture
def sample_code_output_low_similarity() -> str:
    """Create a sample code output with low AST similarity."""
    return '''def calc(x, y):
    return x + y
'''


# ============================================================================
# SimilarityScore Model Tests
# ============================================================================


class TestSimilarityScore:
    """Tests for SimilarityScore Pydantic model."""

    def test_create_similarity_score(self) -> None:
        """Test creating a SimilarityScore with all fields."""
        score = SimilarityScore(
            embedding_score=0.92,
            structural_score=0.88,
            combined_score=0.90,
            passed_threshold=True,
            threshold=0.85,
        )

        assert score.embedding_score == 0.92
        assert score.structural_score == 0.88
        assert score.combined_score == 0.90
        assert score.passed_threshold is True
        assert score.threshold == 0.85

    def test_similarity_score_default_threshold(self) -> None:
        """Test default threshold value."""
        score = SimilarityScore(
            embedding_score=0.90,
            structural_score=0.85,
            combined_score=0.87,
            passed_threshold=True,
        )

        assert score.threshold == 0.85  # Default threshold

    def test_similarity_score_pass_check(self) -> None:
        """Test that passed_threshold is correctly set."""
        passing_score = SimilarityScore(
            embedding_score=0.90,
            structural_score=0.85,
            combined_score=0.87,
            passed_threshold=True,
            threshold=0.85,
        )
        assert passing_score.passed_threshold is True

        failing_score = SimilarityScore(
            embedding_score=0.75,
            structural_score=0.70,
            combined_score=0.72,
            passed_threshold=False,
            threshold=0.85,
        )
        assert failing_score.passed_threshold is False

    def test_similarity_score_serialization(self) -> None:
        """Test serialization to dict/JSON."""
        score = SimilarityScore(
            embedding_score=0.92,
            structural_score=0.88,
            combined_score=0.90,
            passed_threshold=True,
            threshold=0.85,
        )

        data = score.model_dump()
        assert "embedding_score" in data
        assert "structural_score" in data
        assert "combined_score" in data
        assert data["combined_score"] == 0.90

    def test_similarity_score_with_breakdown(self) -> None:
        """Test SimilarityScore with divergence breakdown."""
        breakdown = DivergenceReport(
            total_differences=3,
            missing_sections=["Technical Specs"],
            extra_sections=["Appendix"],
            content_differences=[
                {"section": "Requirements", "difference": "Minor wording change"}
            ],
            structural_differences=[],
        )

        score = SimilarityScore(
            embedding_score=0.85,
            structural_score=0.82,
            combined_score=0.84,
            passed_threshold=False,
            threshold=0.85,
            breakdown=breakdown,
        )

        assert score.breakdown is not None
        assert score.breakdown.total_differences == 3
        assert len(score.breakdown.missing_sections) == 1


class TestDivergenceReport:
    """Tests for DivergenceReport model."""

    def test_create_divergence_report(self) -> None:
        """Test creating a DivergenceReport."""
        report = DivergenceReport(
            total_differences=5,
            missing_sections=["Section A", "Section B"],
            extra_sections=["Section C"],
            content_differences=[
                {"location": "line 10", "expected": "foo", "actual": "bar"}
            ],
            structural_differences=[
                {"type": "node_missing", "path": "func.args"}
            ],
        )

        assert report.total_differences == 5
        assert len(report.missing_sections) == 2
        assert len(report.extra_sections) == 1
        assert len(report.content_differences) == 1
        assert len(report.structural_differences) == 1

    def test_divergence_report_empty(self) -> None:
        """Test creating an empty DivergenceReport for perfect match."""
        report = DivergenceReport(
            total_differences=0,
            missing_sections=[],
            extra_sections=[],
            content_differences=[],
            structural_differences=[],
        )

        assert report.total_differences == 0
        assert len(report.missing_sections) == 0

    def test_divergence_report_serialization(self) -> None:
        """Test DivergenceReport serialization."""
        report = DivergenceReport(
            total_differences=2,
            missing_sections=["Overview"],
            extra_sections=[],
            content_differences=[],
            structural_differences=[],
        )

        data = report.model_dump()
        assert "total_differences" in data
        assert "missing_sections" in data
        assert data["missing_sections"] == ["Overview"]


# ============================================================================
# SimilarityConfig Tests
# ============================================================================


class TestSimilarityConfig:
    """Tests for SimilarityConfig model."""

    def test_create_config_defaults(self) -> None:
        """Test creating SimilarityConfig with default values."""
        config = SimilarityConfig()

        assert config.similarity_threshold == 0.85
        assert config.embedding_model == "text-embedding-3-small"
        assert config.use_structural_weight is True
        assert config.structural_weight == 0.3
        assert config.embedding_weight == 0.7

    def test_create_config_custom(self) -> None:
        """Test creating SimilarityConfig with custom values."""
        config = SimilarityConfig(
            similarity_threshold=0.90,
            embedding_model="text-embedding-ada-002",
            use_structural_weight=False,
            structural_weight=0.5,
            embedding_weight=0.5,
        )

        assert config.similarity_threshold == 0.90
        assert config.embedding_model == "text-embedding-ada-002"
        assert config.use_structural_weight is False

    def test_config_weights_validation(self) -> None:
        """Test that weights are properly bounded."""
        config = SimilarityConfig(
            structural_weight=0.4,
            embedding_weight=0.6,
        )

        # Weights should sum to 1.0 for proper weighted average
        assert config.structural_weight + config.embedding_weight == pytest.approx(1.0)


# ============================================================================
# TextSimilarityScorer Tests
# ============================================================================


class TestTextSimilarityScorer:
    """Tests for TextSimilarityScorer using embeddings."""

    def test_create_text_scorer(self, similarity_config: SimilarityConfig) -> None:
        """Test creating a TextSimilarityScorer."""
        scorer = TextSimilarityScorer(config=similarity_config)
        assert scorer.config == similarity_config

    def test_text_scorer_default_config(self) -> None:
        """Test creating TextSimilarityScorer with default config."""
        scorer = TextSimilarityScorer()
        assert scorer.config is not None
        assert scorer.config.similarity_threshold == 0.85

    @pytest.mark.asyncio
    async def test_score_identical_texts(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test scoring identical texts returns 1.0."""
        scorer = TextSimilarityScorer(config=similarity_config)

        text = "This is a sample document for testing."

        with patch.object(scorer, "_get_embeddings", new_callable=AsyncMock) as mock:
            # Return identical embeddings
            mock.return_value = ([0.1, 0.2, 0.3], [0.1, 0.2, 0.3])

            score = await scorer.score(reference=text, output=text)

        assert score.embedding_score == pytest.approx(1.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_score_similar_texts(
        self,
        similarity_config: SimilarityConfig,
        sample_prd_reference: str,
        sample_prd_output_high_similarity: str,
    ) -> None:
        """Test scoring similar texts returns high score."""
        scorer = TextSimilarityScorer(config=similarity_config)

        with patch.object(scorer, "_get_embeddings", new_callable=AsyncMock) as mock:
            # Return similar but not identical embeddings
            mock.return_value = (
                [0.1, 0.2, 0.3, 0.4],
                [0.12, 0.19, 0.31, 0.38],
            )

            score = await scorer.score(
                reference=sample_prd_reference,
                output=sample_prd_output_high_similarity,
            )

        assert score.embedding_score >= 0.85

    @pytest.mark.asyncio
    async def test_score_dissimilar_texts(
        self,
        similarity_config: SimilarityConfig,
        sample_prd_reference: str,
        sample_prd_output_low_similarity: str,
    ) -> None:
        """Test scoring dissimilar texts returns low score."""
        scorer = TextSimilarityScorer(config=similarity_config)

        with patch.object(scorer, "_get_embeddings", new_callable=AsyncMock) as mock:
            # Return very different embeddings
            mock.return_value = (
                [0.9, 0.1, 0.0, 0.0],
                [0.0, 0.0, 0.1, 0.9],
            )

            score = await scorer.score(
                reference=sample_prd_reference,
                output=sample_prd_output_low_similarity,
            )

        assert score.embedding_score < 0.5

    @pytest.mark.asyncio
    async def test_score_includes_breakdown(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test that score includes divergence breakdown."""
        scorer = TextSimilarityScorer(config=similarity_config)

        with patch.object(scorer, "_get_embeddings", new_callable=AsyncMock) as mock:
            mock.return_value = ([0.5, 0.5], [0.6, 0.4])

            score = await scorer.score(
                reference="## Section A\nContent A\n## Section B\nContent B",
                output="## Section A\nContent A\n## Section C\nDifferent content",
            )

        assert score.breakdown is not None
        # Should detect section differences
        assert isinstance(score.breakdown.missing_sections, list)

    @pytest.mark.asyncio
    async def test_cosine_similarity_calculation(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test cosine similarity calculation."""
        scorer = TextSimilarityScorer(config=similarity_config)

        # Test with orthogonal vectors (cosine = 0)
        emb1 = [1.0, 0.0]
        emb2 = [0.0, 1.0]
        similarity = scorer._cosine_similarity(emb1, emb2)
        assert similarity == pytest.approx(0.0, abs=0.01)

        # Test with identical vectors (cosine = 1)
        emb3 = [0.6, 0.8]
        emb4 = [0.6, 0.8]
        similarity = scorer._cosine_similarity(emb3, emb4)
        assert similarity == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_get_embeddings_calls_api(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test that _get_embeddings calls the embedding API."""
        scorer = TextSimilarityScorer(config=similarity_config)

        with patch("daw_agents.eval.similarity.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]

            embeddings = await scorer._get_embeddings("text1", "text2")

            assert mock_embed.call_count == 2
            assert len(embeddings) == 2


# ============================================================================
# CodeSimilarityScorer Tests
# ============================================================================


class TestCodeSimilarityScorer:
    """Tests for CodeSimilarityScorer using AST comparison."""

    def test_create_code_scorer(self, similarity_config: SimilarityConfig) -> None:
        """Test creating a CodeSimilarityScorer."""
        scorer = CodeSimilarityScorer(config=similarity_config)
        assert scorer.config == similarity_config

    def test_code_scorer_default_config(self) -> None:
        """Test creating CodeSimilarityScorer with default config."""
        scorer = CodeSimilarityScorer()
        assert scorer.config is not None

    def test_score_identical_code(
        self, similarity_config: SimilarityConfig, sample_code_reference: str
    ) -> None:
        """Test scoring identical code returns 1.0."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        score = scorer.score(
            reference=sample_code_reference,
            output=sample_code_reference,
        )

        assert score.structural_score == 1.0
        assert score.passed_threshold is True

    def test_score_similar_code(
        self,
        similarity_config: SimilarityConfig,
        sample_code_reference: str,
        sample_code_output_high_similarity: str,
    ) -> None:
        """Test scoring similar code (same structure, different style)."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        score = scorer.score(
            reference=sample_code_reference,
            output=sample_code_output_high_similarity,
        )

        # Same structure should give high score despite docstring differences
        assert score.structural_score >= 0.85
        assert score.passed_threshold is True

    def test_score_dissimilar_code(
        self,
        similarity_config: SimilarityConfig,
        sample_code_reference: str,
        sample_code_output_low_similarity: str,
    ) -> None:
        """Test scoring structurally different code."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        score = scorer.score(
            reference=sample_code_reference,
            output=sample_code_output_low_similarity,
        )

        # Very different structure should give low score
        assert score.structural_score < 0.50
        assert score.passed_threshold is False

    def test_score_includes_structural_breakdown(
        self,
        similarity_config: SimilarityConfig,
        sample_code_reference: str,
        sample_code_output_low_similarity: str,
    ) -> None:
        """Test that score includes structural divergence breakdown."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        score = scorer.score(
            reference=sample_code_reference,
            output=sample_code_output_low_similarity,
        )

        assert score.breakdown is not None
        assert len(score.breakdown.structural_differences) > 0

    def test_parse_code_to_ast(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test parsing code to AST."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        code = "def foo(x): return x + 1"
        tree = scorer._parse_ast(code)

        assert tree is not None
        assert isinstance(tree, ast.Module)

    def test_parse_invalid_code(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test parsing invalid code returns None."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        invalid_code = "def foo( invalid syntax"
        tree = scorer._parse_ast(invalid_code)

        assert tree is None

    def test_ast_node_comparison(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test AST node type comparison."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        code1 = "def foo(): pass"
        code2 = "def bar(): pass"  # Same structure, different name

        tree1 = scorer._parse_ast(code1)
        tree2 = scorer._parse_ast(code2)

        # Should have same node types
        types1 = scorer._get_node_types(tree1)
        types2 = scorer._get_node_types(tree2)

        assert types1 == types2

    def test_count_ast_features(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test counting AST features."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        code = """
def add(a, b):
    return a + b

def sub(a, b):
    return a - b
"""
        features = scorer._count_features(code)

        assert features["function_count"] == 2
        assert features["return_count"] == 2

    def test_score_handles_syntax_error_gracefully(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test that scorer handles syntax errors gracefully."""
        scorer = CodeSimilarityScorer(config=similarity_config)

        score = scorer.score(
            reference="def valid(): pass",
            output="def invalid( broken",
        )

        # Should return low score but not crash
        assert score.structural_score == 0.0
        assert score.passed_threshold is False
        assert score.breakdown is not None


# ============================================================================
# AgentSimilarityEvaluator Tests
# ============================================================================


class TestAgentSimilarityEvaluator:
    """Tests for AgentSimilarityEvaluator combining text and code scoring."""

    def test_create_evaluator(self, similarity_config: SimilarityConfig) -> None:
        """Test creating an AgentSimilarityEvaluator."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)
        assert evaluator.config == similarity_config
        assert evaluator.text_scorer is not None
        assert evaluator.code_scorer is not None

    def test_evaluator_default_config(self) -> None:
        """Test creating evaluator with default config."""
        evaluator = AgentSimilarityEvaluator()
        assert evaluator.config.similarity_threshold == 0.85

    @pytest.mark.asyncio
    async def test_evaluate_text_output(
        self,
        similarity_config: SimilarityConfig,
        sample_prd_reference: str,
        sample_prd_output_high_similarity: str,
    ) -> None:
        """Test evaluating text (PRD) output."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            mock.return_value = ([0.9, 0.1], [0.88, 0.12])

            score = await evaluator.evaluate(
                reference=sample_prd_reference,
                output=sample_prd_output_high_similarity,
                output_type="text",
            )

        assert score.embedding_score > 0.0
        assert score.combined_score > 0.0

    @pytest.mark.asyncio
    async def test_evaluate_code_output(
        self,
        similarity_config: SimilarityConfig,
        sample_code_reference: str,
        sample_code_output_high_similarity: str,
    ) -> None:
        """Test evaluating code output."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        score = await evaluator.evaluate(
            reference=sample_code_reference,
            output=sample_code_output_high_similarity,
            output_type="code",
        )

        assert score.structural_score > 0.0
        assert score.combined_score > 0.0

    @pytest.mark.asyncio
    async def test_evaluate_auto_detect_code(
        self,
        similarity_config: SimilarityConfig,
        sample_code_reference: str,
        sample_code_output_high_similarity: str,
    ) -> None:
        """Test auto-detection of code vs text."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        score = await evaluator.evaluate(
            reference=sample_code_reference,
            output=sample_code_output_high_similarity,
            output_type="auto",
        )

        # Should detect as code and use structural scoring
        assert score.structural_score > 0.0

    @pytest.mark.asyncio
    async def test_evaluate_auto_detect_text(
        self,
        similarity_config: SimilarityConfig,
        sample_prd_reference: str,
        sample_prd_output_high_similarity: str,
    ) -> None:
        """Test auto-detection of text content."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            mock.return_value = ([0.9, 0.1], [0.88, 0.12])

            score = await evaluator.evaluate(
                reference=sample_prd_reference,
                output=sample_prd_output_high_similarity,
                output_type="auto",
            )

        # Should detect as text and use embedding scoring
        assert score.embedding_score > 0.0

    @pytest.mark.asyncio
    async def test_evaluate_combined_scoring(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test combined scoring with weighted average."""
        config = SimilarityConfig(
            similarity_threshold=0.85,
            use_structural_weight=True,
            structural_weight=0.3,
            embedding_weight=0.7,
        )
        evaluator = AgentSimilarityEvaluator(config=config)

        # Mock both scorers
        with patch.object(
            evaluator.text_scorer, "score", new_callable=AsyncMock
        ) as mock_text:
            mock_text.return_value = SimilarityScore(
                embedding_score=0.90,
                structural_score=0.0,
                combined_score=0.90,
                passed_threshold=True,
            )

            with patch.object(evaluator.code_scorer, "score") as mock_code:
                mock_code.return_value = SimilarityScore(
                    embedding_score=0.0,
                    structural_score=0.80,
                    combined_score=0.80,
                    passed_threshold=False,
                )

                score = await evaluator.evaluate(
                    reference="code or text",
                    output="output",
                    output_type="mixed",
                )

        # Combined: 0.7 * 0.90 + 0.3 * 0.80 = 0.63 + 0.24 = 0.87
        expected_combined = 0.7 * 0.90 + 0.3 * 0.80
        assert score.combined_score == pytest.approx(expected_combined, rel=0.01)

    @pytest.mark.asyncio
    async def test_evaluate_threshold_check(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test that evaluator checks threshold correctly."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            # High similarity embeddings
            mock.return_value = ([0.9, 0.1], [0.89, 0.11])

            score = await evaluator.evaluate(
                reference="Reference text",
                output="Similar output text",
                output_type="text",
            )

        assert score.threshold == 0.85
        # passed_threshold should reflect whether combined_score >= threshold

    @pytest.mark.asyncio
    async def test_evaluate_batch(self, similarity_config: SimilarityConfig) -> None:
        """Test batch evaluation of multiple outputs."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        references = ["Ref 1", "Ref 2", "Ref 3"]
        outputs = ["Out 1", "Out 2", "Out 3"]

        with patch.object(
            evaluator, "evaluate", new_callable=AsyncMock
        ) as mock_eval:
            mock_eval.return_value = SimilarityScore(
                embedding_score=0.90,
                structural_score=0.85,
                combined_score=0.87,
                passed_threshold=True,
            )

            scores = await evaluator.evaluate_batch(
                references=references,
                outputs=outputs,
                output_type="text",
            )

        assert len(scores) == 3
        assert mock_eval.call_count == 3

    @pytest.mark.asyncio
    async def test_evaluate_batch_returns_aggregate(
        self, similarity_config: SimilarityConfig
    ) -> None:
        """Test batch evaluation returns aggregate statistics."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with patch.object(
            evaluator, "evaluate", new_callable=AsyncMock
        ) as mock_eval:
            mock_eval.side_effect = [
                SimilarityScore(
                    embedding_score=0.95, structural_score=0.90,
                    combined_score=0.92, passed_threshold=True,
                ),
                SimilarityScore(
                    embedding_score=0.88, structural_score=0.85,
                    combined_score=0.86, passed_threshold=True,
                ),
                SimilarityScore(
                    embedding_score=0.75, structural_score=0.70,
                    combined_score=0.72, passed_threshold=False,
                ),
            ]

            scores, aggregate = await evaluator.evaluate_batch_with_aggregate(
                references=["R1", "R2", "R3"],
                outputs=["O1", "O2", "O3"],
                output_type="text",
            )

        assert len(scores) == 3
        assert aggregate["total"] == 3
        assert aggregate["passed"] == 2
        assert aggregate["failed"] == 1
        assert aggregate["pass_rate"] == pytest.approx(0.667, rel=0.01)
        assert aggregate["avg_combined_score"] == pytest.approx(0.833, rel=0.01)


# ============================================================================
# Content Detection Tests
# ============================================================================


class TestContentTypeDetection:
    """Tests for automatic content type detection."""

    def test_detect_python_code(self, similarity_config: SimilarityConfig) -> None:
        """Test detection of Python code."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        python_code = """
def hello_world():
    print("Hello, World!")
    return True
"""
        detected = evaluator._detect_content_type(python_code)
        assert detected == "code"

    def test_detect_markdown_text(self, similarity_config: SimilarityConfig) -> None:
        """Test detection of Markdown text."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        markdown = """
# Project README

## Overview
This is a project description.

## Features
- Feature 1
- Feature 2
"""
        detected = evaluator._detect_content_type(markdown)
        assert detected == "text"

    def test_detect_json(self, similarity_config: SimilarityConfig) -> None:
        """Test detection of JSON content."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        # Simple one-line JSON may be detected as code due to structure
        # Multi-line markdown-like content should be detected as text
        json_content = '{"name": "test", "version": "1.0.0"}'
        detected = evaluator._detect_content_type(json_content)
        # JSON structure can be parsed as code, so either detection is valid
        assert detected in ["text", "code"]

    def test_detect_mixed_content(self, similarity_config: SimilarityConfig) -> None:
        """Test detection of mixed content."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        mixed = """
# Code Example

Here is some code:

```python
def foo():
    pass
```

And more text.
"""
        detected = evaluator._detect_content_type(mixed)
        # Mixed content should be detected appropriately
        assert detected in ["text", "mixed", "code"]


# ============================================================================
# Integration Tests
# ============================================================================


class TestSimilarityIntegration:
    """Integration tests for the complete similarity scoring workflow."""

    @pytest.mark.asyncio
    async def test_full_prd_evaluation(
        self,
        similarity_config: SimilarityConfig,
        sample_prd_reference: str,
        sample_prd_output_high_similarity: str,
    ) -> None:
        """Test complete PRD evaluation workflow."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            # Simulate high similarity embeddings
            mock.return_value = (
                [0.1, 0.2, 0.3, 0.4, 0.5],
                [0.11, 0.19, 0.31, 0.39, 0.50],
            )

            score = await evaluator.evaluate(
                reference=sample_prd_reference,
                output=sample_prd_output_high_similarity,
                output_type="text",
            )

        assert score.embedding_score >= 0.85
        assert score.passed_threshold is True
        assert score.breakdown is not None

    @pytest.mark.asyncio
    async def test_full_code_evaluation(
        self,
        similarity_config: SimilarityConfig,
        sample_code_reference: str,
        sample_code_output_high_similarity: str,
    ) -> None:
        """Test complete code evaluation workflow."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        score = await evaluator.evaluate(
            reference=sample_code_reference,
            output=sample_code_output_high_similarity,
            output_type="code",
        )

        assert score.structural_score >= 0.80
        assert score.breakdown is not None
        assert score.breakdown.structural_differences is not None

    @pytest.mark.asyncio
    async def test_threshold_enforcement(self, similarity_config: SimilarityConfig) -> None:
        """Test that 85% threshold is enforced."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        # Test case: score just above threshold
        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            # Embeddings that produce ~86% similarity
            mock.return_value = ([1.0, 0.0], [0.86, 0.51])

            score = await evaluator.evaluate(
                reference="Reference",
                output="Output",
                output_type="text",
            )

        if score.combined_score >= 0.85:
            assert score.passed_threshold is True
        else:
            assert score.passed_threshold is False

    @pytest.mark.asyncio
    async def test_divergence_report_details(
        self,
        similarity_config: SimilarityConfig,
        sample_prd_reference: str,
        sample_prd_output_low_similarity: str,
    ) -> None:
        """Test that divergence report provides useful details."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            mock.return_value = ([0.9, 0.1], [0.1, 0.9])

            score = await evaluator.evaluate(
                reference=sample_prd_reference,
                output=sample_prd_output_low_similarity,
                output_type="text",
            )

        assert score.passed_threshold is False
        assert score.breakdown is not None
        # Should have identified some differences
        assert score.breakdown.total_differences > 0


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_reference(self, similarity_config: SimilarityConfig) -> None:
        """Test handling empty reference."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        score = await evaluator.evaluate(
            reference="",
            output="Some output",
            output_type="text",
        )

        # Should return low score for empty reference
        assert score.combined_score == 0.0

    @pytest.mark.asyncio
    async def test_empty_output(self, similarity_config: SimilarityConfig) -> None:
        """Test handling empty output."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        score = await evaluator.evaluate(
            reference="Some reference",
            output="",
            output_type="text",
        )

        # Should return low score for empty output
        assert score.combined_score == 0.0

    @pytest.mark.asyncio
    async def test_very_long_content(self, similarity_config: SimilarityConfig) -> None:
        """Test handling very long content."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        long_reference = "A" * 100000
        long_output = "A" * 100000

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            mock.return_value = ([0.9, 0.1], [0.9, 0.1])

            # Should not crash and should handle chunking if needed
            score = await evaluator.evaluate(
                reference=long_reference,
                output=long_output,
                output_type="text",
            )

        assert score is not None

    @pytest.mark.asyncio
    async def test_unicode_content(self, similarity_config: SimilarityConfig) -> None:
        """Test handling Unicode content."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        unicode_ref = "Hello, World! Emoji: 🚀 Chinese: 中文 Japanese: 日本語"
        unicode_out = "Hello, World! Emoji: 🚀 Chinese: 中文 Japanese: 日本語"

        with patch.object(
            evaluator.text_scorer, "_get_embeddings", new_callable=AsyncMock
        ) as mock:
            mock.return_value = ([0.9, 0.1], [0.9, 0.1])

            score = await evaluator.evaluate(
                reference=unicode_ref,
                output=unicode_out,
                output_type="text",
            )

        assert score is not None
        assert score.embedding_score > 0.0

    def test_invalid_output_type(self, similarity_config: SimilarityConfig) -> None:
        """Test handling invalid output type."""
        evaluator = AgentSimilarityEvaluator(config=similarity_config)

        with pytest.raises(ValueError, match="Invalid output_type"):
            # This should raise synchronously in validation
            evaluator._validate_output_type("invalid_type")
