"""Agent Similarity Scoring module (EVAL-003).

This module provides similarity scoring for agent outputs against golden references:
- Embedding-based comparison for textual outputs (PRDs, documentation)
- AST comparison for code outputs
- Combined scoring with configurable weights
- Detailed divergence reports for debugging

Key components:
- SimilarityScore: Pydantic model for scores with breakdown
- DivergenceReport: Details of where outputs diverge
- TextSimilarityScorer: Embedding-based text comparison
- CodeSimilarityScorer: AST-based code comparison
- AgentSimilarityEvaluator: Combined evaluator for all output types

Threshold: Agents must achieve >= 85% similarity score to pass.
"""

from __future__ import annotations

import ast
import logging
import math
import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================


class DivergenceReport(BaseModel):
    """Report detailing where outputs diverge from reference.

    Attributes:
        total_differences: Total number of differences found
        missing_sections: Sections present in reference but missing from output
        extra_sections: Sections present in output but not in reference
        content_differences: List of content-level differences
        structural_differences: List of structural differences (for code)
    """

    total_differences: int = 0
    missing_sections: list[str] = Field(default_factory=list)
    extra_sections: list[str] = Field(default_factory=list)
    content_differences: list[dict[str, Any]] = Field(default_factory=list)
    structural_differences: list[dict[str, Any]] = Field(default_factory=list)


class SimilarityScore(BaseModel):
    """Result of similarity scoring between reference and output.

    Attributes:
        embedding_score: Cosine similarity of embeddings (0-1)
        structural_score: AST/structural similarity (0-1)
        combined_score: Weighted combination of scores (0-1)
        passed_threshold: Whether combined_score meets threshold
        threshold: The threshold value used (default 0.85)
        breakdown: Optional detailed divergence report
    """

    embedding_score: float = 0.0
    structural_score: float = 0.0
    combined_score: float = 0.0
    passed_threshold: bool = False
    threshold: float = 0.85
    breakdown: DivergenceReport | None = None


class SimilarityConfig(BaseModel):
    """Configuration for similarity scoring.

    Attributes:
        similarity_threshold: Minimum combined score to pass (default 0.85)
        embedding_model: OpenAI embedding model to use
        use_structural_weight: Whether to use weighted combination
        structural_weight: Weight for structural/AST score (default 0.3)
        embedding_weight: Weight for embedding score (default 0.7)
    """

    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    embedding_model: str = "text-embedding-3-small"
    use_structural_weight: bool = True
    structural_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    embedding_weight: float = Field(default=0.7, ge=0.0, le=1.0)


# ============================================================================
# Helper Functions
# ============================================================================


async def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Get embedding for text using OpenAI API.

    Args:
        text: Text to embed
        model: Embedding model to use

    Returns:
        List of floats representing the embedding vector

    Note:
        In production, this would call the OpenAI API.
        For testing, this should be mocked.
    """
    # This is a placeholder that will be overridden in tests
    # In production, would use: openai.embeddings.create(input=text, model=model)
    try:
        from litellm import embedding

        response = embedding(model=model, input=[text])
        embedding_data: list[float] = response.data[0]["embedding"]
        return embedding_data
    except Exception as e:
        logger.warning(f"Failed to get embedding: {e}")
        # Return a zero vector as fallback
        return [0.0] * 1536


def extract_sections(text: str) -> dict[str, str]:
    """Extract markdown sections from text.

    Args:
        text: Markdown text with ## headers

    Returns:
        Dictionary mapping section names to content
    """
    sections: dict[str, str] = {}
    current_section = "preamble"
    current_content: list[str] = []

    for line in text.split("\n"):
        # Match markdown headers (## Section Name)
        match = re.match(r"^##\s+(.+)$", line)
        if match:
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = match.group(1).strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


# ============================================================================
# TextSimilarityScorer
# ============================================================================


class TextSimilarityScorer:
    """Scorer for textual content using embedding-based comparison.

    Uses cosine similarity between text embeddings to measure semantic
    similarity. Also extracts section-level differences for the breakdown.
    """

    def __init__(self, config: SimilarityConfig | None = None) -> None:
        """Initialize the text similarity scorer.

        Args:
            config: Configuration for scoring. Uses defaults if not provided.
        """
        self.config = config or SimilarityConfig()

    async def score(self, reference: str, output: str) -> SimilarityScore:
        """Score similarity between reference and output text.

        Args:
            reference: The golden reference text
            output: The agent's output text

        Returns:
            SimilarityScore with embedding score and breakdown
        """
        # Handle empty inputs
        if not reference.strip() or not output.strip():
            return SimilarityScore(
                embedding_score=0.0,
                structural_score=0.0,
                combined_score=0.0,
                passed_threshold=False,
                threshold=self.config.similarity_threshold,
                breakdown=DivergenceReport(total_differences=1),
            )

        # Get embeddings
        ref_embedding, out_embedding = await self._get_embeddings(reference, output)

        # Calculate cosine similarity
        embedding_score = self._cosine_similarity(ref_embedding, out_embedding)

        # Generate breakdown
        breakdown = self._generate_breakdown(reference, output)

        # Create score
        combined_score = embedding_score  # Text-only uses embedding score
        passed = combined_score >= self.config.similarity_threshold

        return SimilarityScore(
            embedding_score=embedding_score,
            structural_score=0.0,
            combined_score=combined_score,
            passed_threshold=passed,
            threshold=self.config.similarity_threshold,
            breakdown=breakdown,
        )

    async def _get_embeddings(
        self, text1: str, text2: str
    ) -> tuple[list[float], list[float]]:
        """Get embeddings for two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Tuple of embedding vectors
        """
        emb1 = await get_embedding(text1, self.config.embedding_model)
        emb2 = await get_embedding(text2, self.config.embedding_model)
        return emb1, emb2

    def _cosine_similarity(
        self, vec1: list[float], vec2: list[float]
    ) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _generate_breakdown(self, reference: str, output: str) -> DivergenceReport:
        """Generate divergence breakdown between reference and output.

        Args:
            reference: Reference text
            output: Output text

        Returns:
            DivergenceReport with section-level differences
        """
        ref_sections = extract_sections(reference)
        out_sections = extract_sections(output)

        ref_keys = set(ref_sections.keys())
        out_keys = set(out_sections.keys())

        missing = list(ref_keys - out_keys)
        extra = list(out_keys - ref_keys)

        content_diffs = []
        for section in ref_keys & out_keys:
            if ref_sections[section] != out_sections[section]:
                content_diffs.append({
                    "section": section,
                    "difference": "Content differs",
                })

        total = len(missing) + len(extra) + len(content_diffs)

        return DivergenceReport(
            total_differences=total,
            missing_sections=missing,
            extra_sections=extra,
            content_differences=content_diffs,
            structural_differences=[],
        )


# ============================================================================
# CodeSimilarityScorer
# ============================================================================


class CodeSimilarityScorer:
    """Scorer for code using AST-based comparison.

    Compares the abstract syntax tree structure of code to measure
    structural similarity, independent of variable names and comments.
    """

    def __init__(self, config: SimilarityConfig | None = None) -> None:
        """Initialize the code similarity scorer.

        Args:
            config: Configuration for scoring. Uses defaults if not provided.
        """
        self.config = config or SimilarityConfig()

    def score(self, reference: str, output: str) -> SimilarityScore:
        """Score structural similarity between reference and output code.

        Args:
            reference: The golden reference code
            output: The agent's output code

        Returns:
            SimilarityScore with structural score and breakdown
        """
        # Parse ASTs
        ref_ast = self._parse_ast(reference)
        out_ast = self._parse_ast(output)

        # Handle parse failures
        if ref_ast is None or out_ast is None:
            return SimilarityScore(
                embedding_score=0.0,
                structural_score=0.0,
                combined_score=0.0,
                passed_threshold=False,
                threshold=self.config.similarity_threshold,
                breakdown=DivergenceReport(
                    total_differences=1,
                    structural_differences=[{"error": "Failed to parse AST"}],
                ),
            )

        # Compare AST structures
        structural_score = self._compare_asts(ref_ast, out_ast)

        # Generate breakdown
        breakdown = self._generate_breakdown(ref_ast, out_ast, reference, output)

        # Create score
        combined_score = structural_score  # Code-only uses structural score
        passed = combined_score >= self.config.similarity_threshold

        return SimilarityScore(
            embedding_score=0.0,
            structural_score=structural_score,
            combined_score=combined_score,
            passed_threshold=passed,
            threshold=self.config.similarity_threshold,
            breakdown=breakdown,
        )

    def _parse_ast(self, code: str) -> ast.Module | None:
        """Parse code into an AST.

        Args:
            code: Python code string

        Returns:
            AST Module node or None if parsing fails
        """
        try:
            return ast.parse(code)
        except SyntaxError as e:
            logger.debug(f"Failed to parse code: {e}")
            return None

    def _compare_asts(self, ref_ast: ast.Module, out_ast: ast.Module) -> float:
        """Compare two ASTs for structural similarity.

        Args:
            ref_ast: Reference AST
            out_ast: Output AST

        Returns:
            Similarity score (0-1)
        """
        # Get node type sequences
        ref_types = self._get_node_types(ref_ast)
        out_types = self._get_node_types(out_ast)

        # Count matching nodes using bag-of-nodes comparison
        ref_counter = Counter(ref_types)
        out_counter = Counter(out_types)

        # Calculate Jaccard-like similarity
        intersection = sum((ref_counter & out_counter).values())
        union = sum((ref_counter | out_counter).values())

        if union == 0:
            return 1.0 if intersection == 0 else 0.0

        return intersection / union

    def _get_node_types(self, tree: ast.AST) -> list[str]:
        """Get sequence of node types from AST.

        Args:
            tree: AST node

        Returns:
            List of node type names
        """
        types = []
        for node in ast.walk(tree):
            types.append(type(node).__name__)
        return types

    def _count_features(self, code: str) -> dict[str, int]:
        """Count structural features in code.

        Args:
            code: Python code string

        Returns:
            Dictionary of feature counts
        """
        tree = self._parse_ast(code)
        if tree is None:
            return {"function_count": 0, "return_count": 0}

        features = {
            "function_count": 0,
            "return_count": 0,
            "class_count": 0,
            "if_count": 0,
            "for_count": 0,
            "while_count": 0,
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                features["function_count"] += 1
            elif isinstance(node, ast.Return):
                features["return_count"] += 1
            elif isinstance(node, ast.ClassDef):
                features["class_count"] += 1
            elif isinstance(node, ast.If):
                features["if_count"] += 1
            elif isinstance(node, ast.For):
                features["for_count"] += 1
            elif isinstance(node, ast.While):
                features["while_count"] += 1

        return features

    def _generate_breakdown(
        self,
        ref_ast: ast.Module,
        out_ast: ast.Module,
        ref_code: str,
        out_code: str,
    ) -> DivergenceReport:
        """Generate structural divergence breakdown.

        Args:
            ref_ast: Reference AST
            out_ast: Output AST
            ref_code: Reference code string
            out_code: Output code string

        Returns:
            DivergenceReport with structural differences
        """
        ref_features = self._count_features(ref_code)
        out_features = self._count_features(out_code)

        structural_diffs = []
        for feature, ref_count in ref_features.items():
            out_count = out_features.get(feature, 0)
            if ref_count != out_count:
                structural_diffs.append({
                    "feature": feature,
                    "reference": ref_count,
                    "output": out_count,
                    "difference": out_count - ref_count,
                })

        return DivergenceReport(
            total_differences=len(structural_diffs),
            missing_sections=[],
            extra_sections=[],
            content_differences=[],
            structural_differences=structural_diffs,
        )


# ============================================================================
# AgentSimilarityEvaluator
# ============================================================================


OutputType = Literal["text", "code", "mixed", "auto"]


class AgentSimilarityEvaluator:
    """Combined evaluator for agent outputs.

    Automatically selects between text and code scoring based on content type,
    or can use both with weighted combination for mixed content.
    """

    def __init__(self, config: SimilarityConfig | None = None) -> None:
        """Initialize the evaluator.

        Args:
            config: Configuration for scoring. Uses defaults if not provided.
        """
        self.config = config or SimilarityConfig()
        self.text_scorer = TextSimilarityScorer(config=self.config)
        self.code_scorer = CodeSimilarityScorer(config=self.config)

    def _validate_output_type(self, output_type: str) -> None:
        """Validate output type parameter.

        Args:
            output_type: The output type to validate

        Raises:
            ValueError: If output type is invalid
        """
        valid_types = {"text", "code", "mixed", "auto"}
        if output_type not in valid_types:
            raise ValueError(
                f"Invalid output_type: {output_type}. "
                f"Must be one of: {valid_types}"
            )

    def _detect_content_type(self, content: str) -> str:
        """Detect whether content is code or text.

        Args:
            content: The content to analyze

        Returns:
            "code" if content appears to be code, "text" otherwise
        """
        # Heuristics for detecting code
        code_indicators = [
            r"^\s*def\s+\w+\s*\(",  # Function definition
            r"^\s*class\s+\w+",  # Class definition
            r"^\s*import\s+",  # Import statement
            r"^\s*from\s+\w+\s+import",  # From import
            r"^\s*@\w+",  # Decorator
            r"^\s*if\s+__name__\s*==",  # Main guard
        ]

        text_indicators = [
            r"^#\s+",  # Markdown header
            r"^\*\s+",  # Bullet point
            r"^\d+\.\s+",  # Numbered list
            r"^##\s+",  # Markdown h2
        ]

        code_matches = 0
        text_matches = 0

        for line in content.split("\n"):
            for pattern in code_indicators:
                if re.match(pattern, line):
                    code_matches += 1
                    break

            for pattern in text_indicators:
                if re.match(pattern, line):
                    text_matches += 1
                    break

        # Also try parsing as Python
        try:
            ast.parse(content)
            code_matches += 5  # Bonus for valid Python
        except SyntaxError:
            pass

        if code_matches > text_matches:
            return "code"
        elif text_matches > code_matches:
            return "text"
        else:
            return "text"  # Default to text

    async def evaluate(
        self,
        reference: str,
        output: str,
        output_type: OutputType = "auto",
    ) -> SimilarityScore:
        """Evaluate similarity between reference and output.

        Args:
            reference: The golden reference
            output: The agent's output
            output_type: Type of output ("text", "code", "mixed", "auto")

        Returns:
            SimilarityScore with combined score and breakdown
        """
        # Handle empty inputs
        if not reference.strip() or not output.strip():
            return SimilarityScore(
                embedding_score=0.0,
                structural_score=0.0,
                combined_score=0.0,
                passed_threshold=False,
                threshold=self.config.similarity_threshold,
                breakdown=DivergenceReport(total_differences=1),
            )

        # Validate output type
        self._validate_output_type(output_type)

        # Auto-detect content type
        detected_type: OutputType = output_type
        if output_type == "auto":
            detected = self._detect_content_type(reference)
            detected_type = "code" if detected == "code" else "text"

        if detected_type == "text":
            return await self.text_scorer.score(reference, output)
        elif detected_type == "code":
            return self.code_scorer.score(reference, output)
        elif detected_type == "mixed":
            return await self._evaluate_mixed(reference, output)
        else:
            # Should not reach here due to validation
            return await self.text_scorer.score(reference, output)

    async def _evaluate_mixed(
        self, reference: str, output: str
    ) -> SimilarityScore:
        """Evaluate mixed content using weighted combination.

        Args:
            reference: The golden reference
            output: The agent's output

        Returns:
            SimilarityScore with weighted combined score
        """
        # Get both scores
        text_score = await self.text_scorer.score(reference, output)
        code_score = self.code_scorer.score(reference, output)

        # Calculate weighted combination
        embedding_score = text_score.embedding_score
        structural_score = code_score.structural_score

        combined_score = (
            self.config.embedding_weight * embedding_score
            + self.config.structural_weight * structural_score
        )

        passed = combined_score >= self.config.similarity_threshold

        # Merge breakdowns
        breakdown = DivergenceReport(
            total_differences=(
                (text_score.breakdown.total_differences if text_score.breakdown else 0)
                + (code_score.breakdown.total_differences if code_score.breakdown else 0)
            ),
            missing_sections=text_score.breakdown.missing_sections if text_score.breakdown else [],
            extra_sections=text_score.breakdown.extra_sections if text_score.breakdown else [],
            content_differences=text_score.breakdown.content_differences if text_score.breakdown else [],
            structural_differences=code_score.breakdown.structural_differences if code_score.breakdown else [],
        )

        return SimilarityScore(
            embedding_score=embedding_score,
            structural_score=structural_score,
            combined_score=combined_score,
            passed_threshold=passed,
            threshold=self.config.similarity_threshold,
            breakdown=breakdown,
        )

    async def evaluate_batch(
        self,
        references: list[str],
        outputs: list[str],
        output_type: OutputType = "auto",
    ) -> list[SimilarityScore]:
        """Evaluate multiple reference-output pairs.

        Args:
            references: List of golden references
            outputs: List of agent outputs
            output_type: Type of output

        Returns:
            List of SimilarityScore for each pair
        """
        if len(references) != len(outputs):
            raise ValueError("References and outputs must have same length")

        scores = []
        for ref, out in zip(references, outputs, strict=True):
            score = await self.evaluate(ref, out, output_type)
            scores.append(score)

        return scores

    async def evaluate_batch_with_aggregate(
        self,
        references: list[str],
        outputs: list[str],
        output_type: OutputType = "auto",
    ) -> tuple[list[SimilarityScore], dict[str, Any]]:
        """Evaluate batch and return aggregate statistics.

        Args:
            references: List of golden references
            outputs: List of agent outputs
            output_type: Type of output

        Returns:
            Tuple of (list of scores, aggregate statistics dict)
        """
        scores = await self.evaluate_batch(references, outputs, output_type)

        total = len(scores)
        passed = sum(1 for s in scores if s.passed_threshold)
        failed = total - passed

        avg_combined = sum(s.combined_score for s in scores) / total if total > 0 else 0.0

        aggregate = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "avg_combined_score": avg_combined,
        }

        return scores, aggregate
