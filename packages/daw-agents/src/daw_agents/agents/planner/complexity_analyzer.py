"""Complexity Analysis Engine for DAW Workbench.

This module implements the ComplexityAnalyzer that:
1. Analyzes PRD documents to extract features
2. Calculates cognitive load scores (1-10) per feature
3. Builds dependency graphs with risk ratings
4. Recommends model tiers per task
5. Detects architectural bottlenecks with mitigations

The analysis MUST complete successfully before task generation proceeds.
Integrates with FR-02.4 Task Decomposition to inform task sizing in tasks.json.

Task: COMPLEXITY-001
Dependencies: PLANNER-001, CORE-003
Reference: FR-02.5 in PRD

Example output:
    {
        "features": [
            {"name": "Authentication", "cognitive_load": 7, "risk": "medium"},
            {"name": "Payment Processing", "cognitive_load": 9, "risk": "critical"}
        ],
        "dependencies": {...},
        "model_recommendations": [
            {"task": "auth-design", "tier": "planning", "model": "o1"}
        ],
        "bottleneck_warnings": [...]
    }
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from daw_agents.mcp.client import MCPClient
from daw_agents.models.router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class RiskRating(str, Enum):
    """Risk rating levels for features and dependencies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ModelTier(str, Enum):
    """Model tiers for task routing.

    Based on MODEL-001 router configuration:
    - PLANNING: o1/Claude Opus for high reasoning tasks
    - CODING: Claude Sonnet/GPT-4o for implementation
    - VALIDATION: Different model for cross-validation
    - FAST: Claude Haiku/GPT-4o-mini for quick tasks
    """

    PLANNING = "planning"
    CODING = "coding"
    VALIDATION = "validation"
    FAST = "fast"


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------


class ComplexityScore(BaseModel):
    """Represents the complexity score for a single feature.

    Attributes:
        feature: Name of the feature
        cognitive_load: Score from 1-10 (1=trivial, 10=extremely complex)
        risk_rating: Overall risk level for this feature
        description: Optional description of complexity factors
    """

    feature: str = Field(..., description="Name of the feature")
    cognitive_load: int = Field(
        ..., ge=1, le=10, description="Cognitive load score (1-10)"
    )
    risk_rating: RiskRating = Field(..., description="Risk rating level")
    description: str | None = Field(
        default=None, description="Description of complexity factors"
    )

    @field_validator("cognitive_load")
    @classmethod
    def validate_cognitive_load(cls, v: int) -> int:
        """Validate cognitive load is within bounds."""
        if v < 1 or v > 10:
            raise ValueError("cognitive_load must be between 1 and 10")
        return v


class DependencyNode(BaseModel):
    """Represents a node in the dependency graph.

    Attributes:
        id: Unique identifier for the node
        name: Human-readable name
        dependencies: List of node IDs this node depends on
        dependents: List of node IDs that depend on this node
        risk_rating: Risk level for this node
    """

    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Human-readable name")
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of nodes this depends on"
    )
    dependents: list[str] = Field(
        default_factory=list, description="IDs of nodes that depend on this"
    )
    risk_rating: RiskRating = Field(
        default=RiskRating.LOW, description="Risk level for this node"
    )


class DependencyGraph(BaseModel):
    """Represents the full dependency graph.

    Attributes:
        nodes: List of all dependency nodes
    """

    nodes: list[DependencyNode] = Field(
        default_factory=list, description="All nodes in the graph"
    )

    def get_node(self, node_id: str) -> DependencyNode | None:
        """Get a node by its ID.

        Args:
            node_id: The ID to search for

        Returns:
            The matching node or None if not found
        """
        for node in self.nodes:
            if node.id == node_id or node.name == node_id:
                return node
        return None

    def get_critical_nodes(self) -> list[DependencyNode]:
        """Get all nodes with critical risk rating.

        Returns:
            List of critical risk nodes
        """
        return [n for n in self.nodes if n.risk_rating == RiskRating.CRITICAL]


class ArchitecturalWarning(BaseModel):
    """Represents a warning about architectural issues.

    Attributes:
        warning_type: Type of warning (bottleneck, circular_dependency, etc.)
        feature: The feature or component affected
        description: Detailed description of the issue
        severity: How severe the issue is
        mitigation: Recommended mitigation strategy
    """

    warning_type: str = Field(..., description="Type of warning")
    feature: str = Field(..., description="Affected feature or component")
    description: str = Field(..., description="Detailed description of the issue")
    severity: RiskRating = Field(..., description="Severity level")
    mitigation: str = Field(..., description="Recommended mitigation strategy")


class ModelRecommendation(BaseModel):
    """Recommends a model tier for a specific task.

    Attributes:
        task_id: The task identifier
        task_description: Description of the task
        tier: Recommended model tier
        recommended_model: Specific model recommendation
        reasoning: Why this model was recommended
    """

    task_id: str = Field(..., description="Task identifier")
    task_description: str = Field(..., description="Task description")
    tier: ModelTier = Field(..., description="Recommended model tier")
    recommended_model: str = Field(..., description="Specific model recommendation")
    reasoning: str = Field(..., description="Reasoning for this recommendation")


class ComplexityAnalysis(BaseModel):
    """Complete complexity analysis output.

    This is the main output structure that matches the required
    complexity_analysis.json format from FR-02.5.

    Attributes:
        prd_title: Title of the analyzed PRD
        features: List of feature complexity scores
        dependency_graph: The dependency graph
        model_recommendations: Model tier recommendations per task
        bottleneck_warnings: List of architectural warnings
    """

    prd_title: str = Field(..., description="Title of the analyzed PRD")
    features: list[ComplexityScore] = Field(
        default_factory=list, description="Feature complexity scores"
    )
    dependency_graph: DependencyGraph = Field(
        default_factory=DependencyGraph, description="Dependency graph"
    )
    model_recommendations: list[ModelRecommendation] = Field(
        default_factory=list, description="Model tier recommendations"
    )
    bottleneck_warnings: list[ArchitecturalWarning] = Field(
        default_factory=list, description="Architectural warnings"
    )

    @property
    def overall_cognitive_load(self) -> float:
        """Calculate the average cognitive load across all features.

        Returns:
            Average cognitive load score
        """
        if not self.features:
            return 0.0
        return sum(f.cognitive_load for f in self.features) / len(self.features)

    def to_json(self) -> str:
        """Serialize the analysis to JSON format.

        Returns:
            JSON string representation
        """
        return self.model_dump_json(indent=2)


# -----------------------------------------------------------------------------
# Prompt Templates
# -----------------------------------------------------------------------------


FEATURE_EXTRACTION_PROMPT = """Analyze this PRD and extract all features with their complexity.

PRD:
{prd}

For each feature, provide:
1. name: Feature name
2. cognitive_load: Score 1-10 (1=trivial, 10=extremely complex)
3. risk: "low", "medium", "high", or "critical"
4. dependencies: List of other features this depends on

Consider these factors for cognitive load:
- Technical complexity
- Integration requirements
- Security implications
- Performance considerations
- Error handling needs
- State management complexity

Output JSON format:
{{
    "features": [
        {{
            "name": "Feature Name",
            "cognitive_load": 7,
            "risk": "medium",
            "dependencies": ["Other Feature"]
        }}
    ]
}}

Output ONLY valid JSON, no additional text."""


COGNITIVE_LOAD_PROMPT = """Analyze the cognitive load for implementing this feature:

Feature: {feature}

Score from 1-10 where:
1-2: Trivial (simple CRUD, basic UI)
3-4: Low (standard patterns, well-documented)
5-6: Medium (some complexity, requires design)
7-8: High (significant complexity, security/performance critical)
9-10: Very High (novel algorithms, complex integrations)

Consider:
- Technical complexity
- Integration requirements
- Security implications
- Error handling needs
- Testing complexity

Output JSON:
{{"score": 5, "reasoning": "Brief explanation"}}

Output ONLY valid JSON."""


# -----------------------------------------------------------------------------
# ComplexityAnalyzer
# -----------------------------------------------------------------------------


class ComplexityAnalyzer:
    """Analyzes PRD documents to produce complexity analysis.

    The analyzer:
    1. Extracts features from PRD using LLM
    2. Calculates cognitive load per feature
    3. Builds dependency graph with risk ratings
    4. Recommends model tiers per task type
    5. Detects architectural bottlenecks

    Integrates with:
    - MODEL-001 (ModelRouter) for LLM calls
    - CORE-003 (MCPClient) for optional codebase analysis

    Example:
        ```python
        analyzer = ComplexityAnalyzer()
        analysis = await analyzer.analyze_prd(prd_content)
        print(analysis.to_json())
        ```
    """

    # Threshold for identifying bottlenecks (nodes with many dependents)
    BOTTLENECK_THRESHOLD = 3

    # Model mappings for recommendations
    TIER_MODEL_MAP: dict[ModelTier, str] = {
        ModelTier.PLANNING: "o1",
        ModelTier.CODING: "sonnet",
        ModelTier.VALIDATION: "gpt-4o",
        ModelTier.FAST: "haiku",
    }

    def __init__(
        self,
        model_router: ModelRouter | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        """Initialize the ComplexityAnalyzer.

        Args:
            model_router: Optional custom model router. Creates default if None.
            mcp_client: Optional MCP client for codebase analysis.
        """
        self._model_router = model_router or ModelRouter()
        self._mcp_client = mcp_client

    async def analyze_prd(self, prd: str) -> ComplexityAnalysis:
        """Perform complete complexity analysis on a PRD.

        This is the main entry point that:
        1. Extracts features from the PRD
        2. Builds dependency graph
        3. Generates model recommendations
        4. Detects bottlenecks

        Args:
            prd: The PRD content to analyze

        Returns:
            ComplexityAnalysis with all analysis results
        """
        logger.info("Starting complexity analysis for PRD")

        # Extract title from PRD if possible
        prd_title = self._extract_title(prd)

        # Extract features using LLM
        features_data = await self._extract_features(prd)

        # Build complexity scores
        features = self._build_complexity_scores(features_data)

        # Build dependency graph
        dependency_graph = self.build_dependency_graph(features_data)

        # Generate model recommendations for inferred tasks
        tasks = self._infer_tasks_from_features(features_data)
        model_recommendations = self.recommend_models(tasks)

        # Detect bottlenecks
        bottleneck_warnings = self.detect_bottlenecks(dependency_graph)

        analysis = ComplexityAnalysis(
            prd_title=prd_title,
            features=features,
            dependency_graph=dependency_graph,
            model_recommendations=model_recommendations,
            bottleneck_warnings=bottleneck_warnings,
        )

        logger.info(
            "Complexity analysis complete: %d features, %d warnings",
            len(features),
            len(bottleneck_warnings),
        )

        return analysis

    def _extract_title(self, prd: str) -> str:
        """Extract the title from a PRD.

        Args:
            prd: PRD content

        Returns:
            Extracted title or default
        """
        lines = prd.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                # Remove markdown heading markers
                return line.lstrip("#").strip()
            if line and not line.startswith("*") and not line.startswith("-"):
                return line[:100]
        return "Untitled PRD"

    async def _extract_features(self, prd: str) -> list[dict[str, Any]]:
        """Extract features from PRD using LLM.

        Args:
            prd: PRD content

        Returns:
            List of feature dictionaries
        """
        if not prd.strip():
            return []

        prompt = FEATURE_EXTRACTION_PROMPT.format(prd=prd)

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert software architect analyzing PRDs.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            # Parse JSON response
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            features: list[dict[str, Any]] = data.get("features", [])
            return features

        except json.JSONDecodeError as e:
            logger.error("Failed to parse features JSON: %s", str(e))
            return []
        except Exception as e:
            logger.error("Feature extraction failed: %s", str(e))
            return []

    def _extract_json(self, text: str) -> str:
        """Extract JSON from a text response.

        Args:
            text: Raw text that may contain JSON

        Returns:
            Extracted JSON string
        """
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find JSON directly
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            if start >= 0:
                depth = 0
                for i, char in enumerate(text[start:], start):
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            return text[start : i + 1]

        return text

    def _build_complexity_scores(
        self, features_data: list[dict[str, Any]]
    ) -> list[ComplexityScore]:
        """Build ComplexityScore objects from feature data.

        Args:
            features_data: List of feature dictionaries

        Returns:
            List of ComplexityScore objects
        """
        scores: list[ComplexityScore] = []

        for feature in features_data:
            try:
                name = feature.get("name", "Unknown")
                cognitive_load = feature.get("cognitive_load", 5)
                risk_str = feature.get("risk", "medium")

                # Ensure cognitive_load is in bounds
                cognitive_load = max(1, min(10, int(cognitive_load)))

                # Parse risk rating
                risk_rating = self._parse_risk_rating(risk_str)

                score = ComplexityScore(
                    feature=name,
                    cognitive_load=cognitive_load,
                    risk_rating=risk_rating,
                )
                scores.append(score)

            except Exception as e:
                logger.warning("Failed to build complexity score: %s", str(e))

        return scores

    def _parse_risk_rating(self, risk_str: str) -> RiskRating:
        """Parse a risk rating string to enum.

        Args:
            risk_str: Risk rating as string

        Returns:
            RiskRating enum value
        """
        risk_map = {
            "low": RiskRating.LOW,
            "medium": RiskRating.MEDIUM,
            "high": RiskRating.HIGH,
            "critical": RiskRating.CRITICAL,
        }
        return risk_map.get(risk_str.lower(), RiskRating.MEDIUM)

    async def calculate_cognitive_load(self, feature: str) -> int:
        """Calculate cognitive load score for a single feature.

        Uses LLM to analyze the feature and return a score from 1-10.

        Args:
            feature: Feature description

        Returns:
            Cognitive load score (1-10)
        """
        prompt = COGNITIVE_LOAD_PROMPT.format(feature=feature)

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at estimating software complexity.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            json_str = self._extract_json(response)
            data = json.loads(json_str)
            score = data.get("score", 5)

            # Ensure score is in bounds
            return max(1, min(10, int(score)))

        except Exception as e:
            logger.error("Cognitive load calculation failed: %s", str(e))
            return 5  # Default to medium

    def build_dependency_graph(
        self, features: list[dict[str, Any]]
    ) -> DependencyGraph:
        """Build a dependency graph from feature list.

        Args:
            features: List of feature dictionaries with dependencies

        Returns:
            DependencyGraph with all nodes and relationships
        """
        if not features:
            return DependencyGraph(nodes=[])

        # Build nodes first
        nodes_map: dict[str, DependencyNode] = {}

        for feature in features:
            name = feature.get("name", "Unknown")
            node_id = self._to_node_id(name)
            dependencies = feature.get("dependencies", [])
            risk_str = feature.get("risk", "low")

            # Convert dependency names to IDs
            dep_ids = [self._to_node_id(d) for d in dependencies]

            nodes_map[node_id] = DependencyNode(
                id=node_id,
                name=name,
                dependencies=dep_ids,
                dependents=[],  # Will be filled in next pass
                risk_rating=self._parse_risk_rating(risk_str),
            )

        # Second pass: identify dependents
        for node_id, node in nodes_map.items():
            for dep_id in node.dependencies:
                if dep_id in nodes_map:
                    if node_id not in nodes_map[dep_id].dependents:
                        nodes_map[dep_id].dependents.append(node_id)

        return DependencyGraph(nodes=list(nodes_map.values()))

    def _to_node_id(self, name: str) -> str:
        """Convert a feature name to a node ID.

        Args:
            name: Feature name

        Returns:
            Normalized node ID
        """
        return name.lower().replace(" ", "_").replace("-", "_")

    def _infer_tasks_from_features(
        self, features: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Infer tasks from features for model recommendations.

        Args:
            features: List of feature dictionaries

        Returns:
            List of inferred task dictionaries
        """
        tasks: list[dict[str, Any]] = []

        for i, feature in enumerate(features):
            name = feature.get("name", "Unknown")
            cognitive_load = feature.get("cognitive_load", 5)

            # Infer task type based on cognitive load
            if cognitive_load >= 7:
                task_type = "planning"
            elif cognitive_load >= 4:
                task_type = "code"
            else:
                task_type = "fast"

            tasks.append(
                {
                    "id": f"TASK-{i + 1:03d}",
                    "description": f"Implement {name}",
                    "type": task_type,
                }
            )

        return tasks

    def recommend_models(
        self, tasks: list[dict[str, Any]]
    ) -> list[ModelRecommendation]:
        """Generate model recommendations for a list of tasks.

        Based on MODEL-001 router mode:
        - Planning tasks: o1/opus (high reasoning)
        - Coding tasks: sonnet/haiku (balanced)
        - Validation tasks: gpt-4o (cross-validation)
        - Fast tasks: haiku (speed)

        Args:
            tasks: List of task dictionaries with type field

        Returns:
            List of ModelRecommendation objects
        """
        recommendations: list[ModelRecommendation] = []

        type_to_tier = {
            "planning": ModelTier.PLANNING,
            "code": ModelTier.CODING,
            "validation": ModelTier.VALIDATION,
            "fast": ModelTier.FAST,
            "docs": ModelTier.FAST,
            "test": ModelTier.CODING,
        }

        tier_reasoning = {
            ModelTier.PLANNING: "High cognitive load architecture/design task",
            ModelTier.CODING: "Standard implementation task",
            ModelTier.VALIDATION: "Cross-validation requires different model",
            ModelTier.FAST: "Simple task, speed optimized",
        }

        for task in tasks:
            task_id = task.get("id", "UNKNOWN")
            description = task.get("description", "")
            task_type = task.get("type", "code")

            tier = type_to_tier.get(task_type, ModelTier.CODING)
            model = self.TIER_MODEL_MAP.get(tier, "sonnet")
            reasoning = tier_reasoning.get(tier, "Default recommendation")

            rec = ModelRecommendation(
                task_id=task_id,
                task_description=description,
                tier=tier,
                recommended_model=model,
                reasoning=reasoning,
            )
            recommendations.append(rec)

        return recommendations

    def detect_bottlenecks(
        self, graph: DependencyGraph
    ) -> list[ArchitecturalWarning]:
        """Detect architectural bottlenecks in the dependency graph.

        A bottleneck is a node that:
        - Has many dependents (BOTTLENECK_THRESHOLD or more)
        - Is on the critical path (critical risk rating)
        - Has no redundancy/fallback

        Args:
            graph: The dependency graph to analyze

        Returns:
            List of ArchitecturalWarning for detected issues
        """
        warnings: list[ArchitecturalWarning] = []

        if not graph.nodes:
            return warnings

        for node in graph.nodes:
            # Check for bottleneck (many dependents)
            if len(node.dependents) >= self.BOTTLENECK_THRESHOLD:
                severity = (
                    RiskRating.CRITICAL
                    if node.risk_rating == RiskRating.CRITICAL
                    else RiskRating.HIGH
                )

                warning = ArchitecturalWarning(
                    warning_type="bottleneck",
                    feature=node.name,
                    description=f"Node '{node.name}' has {len(node.dependents)} dependents. "
                    f"Failure would impact: {', '.join(node.dependents)}",
                    severity=severity,
                    mitigation=self._get_bottleneck_mitigation(node),
                )
                warnings.append(warning)

            # Check for critical nodes without mitigation
            if (
                node.risk_rating == RiskRating.CRITICAL
                and len(node.dependents) > 0
            ):
                # Check if already added as bottleneck
                if not any(
                    w.feature == node.name and w.warning_type == "bottleneck"
                    for w in warnings
                ):
                    warning = ArchitecturalWarning(
                        warning_type="critical_path",
                        feature=node.name,
                        description=f"Critical node '{node.name}' is on the dependency path",
                        severity=RiskRating.CRITICAL,
                        mitigation="Implement comprehensive testing, monitoring, and fallback mechanisms",
                    )
                    warnings.append(warning)

        return warnings

    def _get_bottleneck_mitigation(self, node: DependencyNode) -> str:
        """Get mitigation strategy for a bottleneck.

        Args:
            node: The bottleneck node

        Returns:
            Mitigation strategy string
        """
        mitigations = [
            "Consider adding redundancy or failover mechanisms",
            "Implement comprehensive error handling",
            "Add caching layer to reduce load",
            "Consider horizontal scaling",
        ]

        # Add specific suggestions based on node characteristics
        if "database" in node.name.lower() or "db" in node.name.lower():
            return "Add read replicas, implement connection pooling, and consider sharding"
        if "auth" in node.name.lower():
            return "Implement token caching, add fallback authentication, consider distributed session management"
        if "api" in node.name.lower() or "gateway" in node.name.lower():
            return "Scale horizontally, implement rate limiting, add request queuing"

        return "; ".join(mitigations[:2])


__all__ = [
    "ComplexityAnalyzer",
    "ComplexityAnalysis",
    "ComplexityScore",
    "DependencyGraph",
    "DependencyNode",
    "ArchitecturalWarning",
    "ModelRecommendation",
    "RiskRating",
    "ModelTier",
]
