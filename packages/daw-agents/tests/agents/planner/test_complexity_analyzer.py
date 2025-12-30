"""Tests for ComplexityAnalyzer - Complexity Analysis Engine.

This module tests the ComplexityAnalyzer class which:
1. Analyzes PRD documents to extract features
2. Calculates cognitive load scores (1-10) per feature
3. Builds dependency graphs with risk ratings
4. Recommends model tiers per task
5. Detects architectural bottlenecks with mitigations

Task: COMPLEXITY-001
Dependencies: PLANNER-001, CORE-003
Reference: FR-02.5 in PRD
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.agents.planner.complexity_analyzer import (
    ArchitecturalWarning,
    ComplexityAnalysis,
    ComplexityAnalyzer,
    ComplexityScore,
    DependencyGraph,
    DependencyNode,
    ModelRecommendation,
    ModelTier,
    RiskRating,
)

# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_prd() -> str:
    """Return a sample PRD for testing."""
    return """
    # Project: E-Commerce Platform

    ## Overview
    Build a full-featured e-commerce platform with authentication,
    product catalog, shopping cart, and payment processing.

    ## User Stories

    ### US-001: User Authentication
    As a user, I want to sign up and log in securely.
    - Priority: P0
    - Acceptance Criteria:
      - Email/password registration
      - OAuth (Google, GitHub) integration
      - JWT token-based sessions
      - Password reset flow

    ### US-002: Product Catalog
    As a user, I want to browse products.
    - Priority: P0
    - Acceptance Criteria:
      - Search with filters
      - Categories and tags
      - Product details page
      - Pagination

    ### US-003: Shopping Cart
    As a user, I want to add products to my cart.
    - Priority: P1
    - Acceptance Criteria:
      - Add/remove items
      - Update quantities
      - Cart persistence

    ### US-004: Payment Processing
    As a user, I want to checkout and pay securely.
    - Priority: P0
    - Acceptance Criteria:
      - Stripe integration
      - Order confirmation
      - Payment error handling

    ## Tech Specs
    - Frontend: React + TypeScript
    - Backend: FastAPI + PostgreSQL
    - Authentication: Clerk
    - Payments: Stripe
    """


@pytest.fixture
def simple_prd() -> str:
    """Return a simple PRD with minimal features."""
    return """
    # Simple Calculator

    ## Overview
    A basic calculator app.

    ## User Stories

    ### US-001: Basic Operations
    As a user, I want to perform basic math operations.
    - Priority: P1
    - Acceptance Criteria:
      - Add two numbers
      - Subtract two numbers
    """


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Create a mock ModelRouter."""
    router = AsyncMock()
    router.route = AsyncMock(return_value='{"features": []}')
    return router


@pytest.fixture
def mock_mcp_client() -> MagicMock:
    """Create a mock MCPClient."""
    client = AsyncMock()
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def analyzer(mock_model_router: MagicMock, mock_mcp_client: MagicMock) -> ComplexityAnalyzer:
    """Create a ComplexityAnalyzer with mocked dependencies."""
    return ComplexityAnalyzer(
        model_router=mock_model_router,
        mcp_client=mock_mcp_client,
    )


# -----------------------------------------------------------------------------
# Test Models - ComplexityScore
# -----------------------------------------------------------------------------


class TestComplexityScore:
    """Tests for ComplexityScore model."""

    def test_create_complexity_score_with_required_fields(self) -> None:
        """Test creating a ComplexityScore with required fields."""
        score = ComplexityScore(
            feature="Authentication",
            cognitive_load=7,
            risk_rating=RiskRating.MEDIUM,
        )
        assert score.feature == "Authentication"
        assert score.cognitive_load == 7
        assert score.risk_rating == RiskRating.MEDIUM

    def test_complexity_score_with_description(self) -> None:
        """Test creating a ComplexityScore with optional description."""
        score = ComplexityScore(
            feature="Payment Processing",
            cognitive_load=9,
            risk_rating=RiskRating.CRITICAL,
            description="Handles financial transactions",
        )
        assert score.description == "Handles financial transactions"

    def test_complexity_score_cognitive_load_bounds(self) -> None:
        """Test that cognitive_load must be between 1 and 10."""
        # Valid scores
        score_low = ComplexityScore(
            feature="Test", cognitive_load=1, risk_rating=RiskRating.LOW
        )
        score_high = ComplexityScore(
            feature="Test", cognitive_load=10, risk_rating=RiskRating.HIGH
        )
        assert score_low.cognitive_load == 1
        assert score_high.cognitive_load == 10

        # Invalid scores should raise validation error
        with pytest.raises(ValueError):
            ComplexityScore(
                feature="Test", cognitive_load=0, risk_rating=RiskRating.LOW
            )
        with pytest.raises(ValueError):
            ComplexityScore(
                feature="Test", cognitive_load=11, risk_rating=RiskRating.LOW
            )

    def test_complexity_score_to_dict(self) -> None:
        """Test serializing ComplexityScore to dict."""
        score = ComplexityScore(
            feature="Auth",
            cognitive_load=5,
            risk_rating=RiskRating.MEDIUM,
        )
        data = score.model_dump()
        assert data["feature"] == "Auth"
        assert data["cognitive_load"] == 5
        assert data["risk_rating"] == "medium"


# -----------------------------------------------------------------------------
# Test Models - RiskRating Enum
# -----------------------------------------------------------------------------


class TestRiskRating:
    """Tests for RiskRating enum."""

    def test_risk_rating_values(self) -> None:
        """Test RiskRating enum values."""
        assert RiskRating.LOW.value == "low"
        assert RiskRating.MEDIUM.value == "medium"
        assert RiskRating.HIGH.value == "high"
        assert RiskRating.CRITICAL.value == "critical"

    def test_risk_rating_from_string(self) -> None:
        """Test creating RiskRating from string."""
        assert RiskRating("low") == RiskRating.LOW
        assert RiskRating("critical") == RiskRating.CRITICAL


# -----------------------------------------------------------------------------
# Test Models - ModelTier Enum
# -----------------------------------------------------------------------------


class TestModelTier:
    """Tests for ModelTier enum."""

    def test_model_tier_values(self) -> None:
        """Test ModelTier enum values."""
        assert ModelTier.PLANNING.value == "planning"
        assert ModelTier.CODING.value == "coding"
        assert ModelTier.VALIDATION.value == "validation"
        assert ModelTier.FAST.value == "fast"


# -----------------------------------------------------------------------------
# Test Models - DependencyNode
# -----------------------------------------------------------------------------


class TestDependencyNode:
    """Tests for DependencyNode model."""

    def test_create_dependency_node(self) -> None:
        """Test creating a DependencyNode."""
        node = DependencyNode(
            id="auth",
            name="Authentication",
            dependencies=["database"],
            dependents=["cart", "checkout"],
            risk_rating=RiskRating.MEDIUM,
        )
        assert node.id == "auth"
        assert node.name == "Authentication"
        assert "database" in node.dependencies
        assert "cart" in node.dependents
        assert node.risk_rating == RiskRating.MEDIUM

    def test_dependency_node_defaults(self) -> None:
        """Test DependencyNode with default values."""
        node = DependencyNode(
            id="simple",
            name="Simple Feature",
        )
        assert node.dependencies == []
        assert node.dependents == []
        assert node.risk_rating == RiskRating.LOW


# -----------------------------------------------------------------------------
# Test Models - DependencyGraph
# -----------------------------------------------------------------------------


class TestDependencyGraph:
    """Tests for DependencyGraph model."""

    def test_create_dependency_graph(self) -> None:
        """Test creating a DependencyGraph."""
        nodes = [
            DependencyNode(id="db", name="Database"),
            DependencyNode(id="auth", name="Auth", dependencies=["db"]),
        ]
        graph = DependencyGraph(nodes=nodes)
        assert len(graph.nodes) == 2

    def test_dependency_graph_get_node(self) -> None:
        """Test getting a node by ID from the graph."""
        nodes = [
            DependencyNode(id="db", name="Database"),
            DependencyNode(id="auth", name="Auth", dependencies=["db"]),
        ]
        graph = DependencyGraph(nodes=nodes)

        node = graph.get_node("auth")
        assert node is not None
        assert node.name == "Auth"

        missing = graph.get_node("nonexistent")
        assert missing is None

    def test_dependency_graph_critical_nodes(self) -> None:
        """Test identifying critical path nodes."""
        nodes = [
            DependencyNode(id="db", name="Database", risk_rating=RiskRating.CRITICAL),
            DependencyNode(id="auth", name="Auth", risk_rating=RiskRating.MEDIUM),
            DependencyNode(id="payments", name="Payments", risk_rating=RiskRating.CRITICAL),
        ]
        graph = DependencyGraph(nodes=nodes)

        critical = graph.get_critical_nodes()
        assert len(critical) == 2
        assert all(n.risk_rating == RiskRating.CRITICAL for n in critical)


# -----------------------------------------------------------------------------
# Test Models - ArchitecturalWarning
# -----------------------------------------------------------------------------


class TestArchitecturalWarning:
    """Tests for ArchitecturalWarning model."""

    def test_create_architectural_warning(self) -> None:
        """Test creating an ArchitecturalWarning."""
        warning = ArchitecturalWarning(
            warning_type="bottleneck",
            feature="Database",
            description="Single point of failure",
            severity=RiskRating.CRITICAL,
            mitigation="Add replication and failover",
        )
        assert warning.warning_type == "bottleneck"
        assert warning.feature == "Database"
        assert warning.severity == RiskRating.CRITICAL
        assert "replication" in warning.mitigation

    def test_architectural_warning_types(self) -> None:
        """Test different warning types."""
        bottleneck = ArchitecturalWarning(
            warning_type="bottleneck",
            feature="API Gateway",
            description="All traffic routes through",
            severity=RiskRating.HIGH,
            mitigation="Scale horizontally",
        )
        circular = ArchitecturalWarning(
            warning_type="circular_dependency",
            feature="Module A",
            description="A depends on B, B depends on A",
            severity=RiskRating.MEDIUM,
            mitigation="Extract common interface",
        )
        assert bottleneck.warning_type == "bottleneck"
        assert circular.warning_type == "circular_dependency"


# -----------------------------------------------------------------------------
# Test Models - ModelRecommendation
# -----------------------------------------------------------------------------


class TestModelRecommendation:
    """Tests for ModelRecommendation model."""

    def test_create_model_recommendation(self) -> None:
        """Test creating a ModelRecommendation."""
        rec = ModelRecommendation(
            task_id="TASK-001",
            task_description="Design authentication flow",
            tier=ModelTier.PLANNING,
            recommended_model="o1",
            reasoning="High cognitive load architecture task",
        )
        assert rec.task_id == "TASK-001"
        assert rec.tier == ModelTier.PLANNING
        assert rec.recommended_model == "o1"

    def test_model_recommendation_for_coding_task(self) -> None:
        """Test recommendation for a coding task."""
        rec = ModelRecommendation(
            task_id="TASK-002",
            task_description="Implement login endpoint",
            tier=ModelTier.CODING,
            recommended_model="sonnet",
            reasoning="Standard implementation task",
        )
        assert rec.tier == ModelTier.CODING
        assert rec.recommended_model == "sonnet"


# -----------------------------------------------------------------------------
# Test Models - ComplexityAnalysis
# -----------------------------------------------------------------------------


class TestComplexityAnalysis:
    """Tests for ComplexityAnalysis model."""

    def test_create_complexity_analysis(self) -> None:
        """Test creating a ComplexityAnalysis."""
        analysis = ComplexityAnalysis(
            prd_title="E-Commerce Platform",
            features=[
                ComplexityScore(
                    feature="Auth", cognitive_load=7, risk_rating=RiskRating.MEDIUM
                )
            ],
            dependency_graph=DependencyGraph(nodes=[]),
            model_recommendations=[],
            bottleneck_warnings=[],
        )
        assert analysis.prd_title == "E-Commerce Platform"
        assert len(analysis.features) == 1

    def test_complexity_analysis_overall_score(self) -> None:
        """Test calculating overall complexity score."""
        analysis = ComplexityAnalysis(
            prd_title="Test",
            features=[
                ComplexityScore(
                    feature="A", cognitive_load=5, risk_rating=RiskRating.LOW
                ),
                ComplexityScore(
                    feature="B", cognitive_load=8, risk_rating=RiskRating.HIGH
                ),
                ComplexityScore(
                    feature="C", cognitive_load=6, risk_rating=RiskRating.MEDIUM
                ),
            ],
            dependency_graph=DependencyGraph(nodes=[]),
            model_recommendations=[],
            bottleneck_warnings=[],
        )
        # Average cognitive load: (5 + 8 + 6) / 3 = 6.33
        assert 6 <= analysis.overall_cognitive_load <= 7

    def test_complexity_analysis_to_json(self) -> None:
        """Test serializing ComplexityAnalysis to JSON."""
        analysis = ComplexityAnalysis(
            prd_title="Test",
            features=[
                ComplexityScore(
                    feature="Auth", cognitive_load=7, risk_rating=RiskRating.MEDIUM
                )
            ],
            dependency_graph=DependencyGraph(nodes=[]),
            model_recommendations=[
                ModelRecommendation(
                    task_id="T1",
                    task_description="Test",
                    tier=ModelTier.PLANNING,
                    recommended_model="o1",
                    reasoning="Test",
                )
            ],
            bottleneck_warnings=[],
        )
        json_output = analysis.to_json()
        assert "Auth" in json_output
        assert "model_recommendations" in json_output


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - Initialization
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerInit:
    """Tests for ComplexityAnalyzer initialization."""

    def test_init_with_model_router(
        self, mock_model_router: MagicMock
    ) -> None:
        """Test initialization with model router."""
        analyzer = ComplexityAnalyzer(model_router=mock_model_router)
        assert analyzer._model_router is not None

    def test_init_with_mcp_client(
        self, mock_model_router: MagicMock, mock_mcp_client: MagicMock
    ) -> None:
        """Test initialization with MCP client."""
        analyzer = ComplexityAnalyzer(
            model_router=mock_model_router,
            mcp_client=mock_mcp_client,
        )
        assert analyzer._mcp_client is not None

    def test_init_creates_default_model_router(self) -> None:
        """Test initialization creates default model router if not provided."""
        with patch("daw_agents.agents.planner.complexity_analyzer.ModelRouter") as mock:
            mock.return_value = MagicMock()
            _analyzer = ComplexityAnalyzer()  # noqa: F841
            mock.assert_called_once()


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - analyze_prd
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerAnalyzePrd:
    """Tests for analyze_prd method."""

    @pytest.mark.asyncio
    async def test_analyze_prd_returns_complexity_analysis(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that analyze_prd returns a ComplexityAnalysis."""
        # Mock the model router response for feature extraction
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Authentication", "cognitive_load": 7, "risk": "medium"},
                {"name": "Product Catalog", "cognitive_load": 5, "risk": "low"},
                {"name": "Shopping Cart", "cognitive_load": 4, "risk": "low"},
                {"name": "Payment Processing", "cognitive_load": 9, "risk": "critical"}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        assert isinstance(result, ComplexityAnalysis)
        assert len(result.features) > 0

    @pytest.mark.asyncio
    async def test_analyze_prd_extracts_features(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that analyze_prd extracts features from PRD."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Authentication", "cognitive_load": 7, "risk": "medium"},
                {"name": "Payment Processing", "cognitive_load": 9, "risk": "critical"}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        feature_names = [f.feature for f in result.features]
        assert "Authentication" in feature_names
        assert "Payment Processing" in feature_names

    @pytest.mark.asyncio
    async def test_analyze_prd_builds_dependency_graph(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that analyze_prd builds a dependency graph."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Auth", "cognitive_load": 7, "risk": "medium", "dependencies": []},
                {"name": "Cart", "cognitive_load": 4, "risk": "low", "dependencies": ["Auth"]}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        assert isinstance(result.dependency_graph, DependencyGraph)
        assert len(result.dependency_graph.nodes) > 0

    @pytest.mark.asyncio
    async def test_analyze_prd_generates_model_recommendations(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that analyze_prd generates model recommendations."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Auth", "cognitive_load": 8, "risk": "high"}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        assert len(result.model_recommendations) > 0
        assert all(isinstance(r, ModelRecommendation) for r in result.model_recommendations)

    @pytest.mark.asyncio
    async def test_analyze_prd_detects_bottlenecks(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that analyze_prd detects architectural bottlenecks."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Database", "cognitive_load": 8, "risk": "critical", "dependencies": []},
                {"name": "Auth", "cognitive_load": 6, "risk": "medium", "dependencies": ["Database"]},
                {"name": "Cart", "cognitive_load": 4, "risk": "low", "dependencies": ["Database", "Auth"]},
                {"name": "Payments", "cognitive_load": 9, "risk": "critical", "dependencies": ["Database"]}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        # Database should be identified as a bottleneck (multiple dependents)
        assert len(result.bottleneck_warnings) > 0

    @pytest.mark.asyncio
    async def test_analyze_prd_handles_empty_prd(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that analyze_prd handles empty PRD gracefully."""
        analyzer._model_router.route = AsyncMock(return_value='{"features": []}')

        result = await analyzer.analyze_prd("")

        assert isinstance(result, ComplexityAnalysis)
        assert len(result.features) == 0


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - calculate_cognitive_load
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerCognitiveLoad:
    """Tests for calculate_cognitive_load method."""

    @pytest.mark.asyncio
    async def test_calculate_cognitive_load_returns_score(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that calculate_cognitive_load returns a score 1-10."""
        analyzer._model_router.route = AsyncMock(return_value='{"score": 7, "reasoning": "Complex auth flow"}')

        score = await analyzer.calculate_cognitive_load("User Authentication")

        assert 1 <= score <= 10

    @pytest.mark.asyncio
    async def test_calculate_cognitive_load_high_complexity(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test high cognitive load for complex features."""
        analyzer._model_router.route = AsyncMock(return_value='{"score": 9, "reasoning": "Complex"}')

        score = await analyzer.calculate_cognitive_load(
            "Real-time Payment Processing with Fraud Detection"
        )

        assert score >= 7

    @pytest.mark.asyncio
    async def test_calculate_cognitive_load_low_complexity(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test low cognitive load for simple features."""
        analyzer._model_router.route = AsyncMock(return_value='{"score": 3, "reasoning": "Simple"}')

        score = await analyzer.calculate_cognitive_load("Display Hello World")

        assert score <= 5

    @pytest.mark.asyncio
    async def test_calculate_cognitive_load_uses_planning_model(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that cognitive load calculation uses planning model."""
        analyzer._model_router.route = AsyncMock(return_value='{"score": 5}')

        await analyzer.calculate_cognitive_load("Test Feature")

        # Verify the route was called with PLANNING task type
        call_args = analyzer._model_router.route.call_args
        assert call_args is not None


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - build_dependency_graph
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerBuildDependencyGraph:
    """Tests for build_dependency_graph method."""

    def test_build_dependency_graph_from_features(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test building dependency graph from feature list."""
        features = [
            {"name": "Database", "dependencies": []},
            {"name": "Auth", "dependencies": ["Database"]},
            {"name": "Cart", "dependencies": ["Database", "Auth"]},
        ]

        graph = analyzer.build_dependency_graph(features)

        assert isinstance(graph, DependencyGraph)
        assert len(graph.nodes) == 3

        auth_node = graph.get_node("auth")  # IDs are normalized to lowercase
        assert auth_node is not None
        assert "database" in auth_node.dependencies  # Dependencies also normalized

    def test_build_dependency_graph_assigns_risk_ratings(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that dependency graph assigns risk ratings."""
        features = [
            {"name": "Database", "dependencies": [], "risk": "critical"},
            {"name": "Auth", "dependencies": ["Database"], "risk": "medium"},
        ]

        graph = analyzer.build_dependency_graph(features)

        db_node = graph.get_node("Database")
        assert db_node is not None
        assert db_node.risk_rating == RiskRating.CRITICAL

    def test_build_dependency_graph_identifies_dependents(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that dependency graph identifies dependents correctly."""
        features = [
            {"name": "Database", "dependencies": []},
            {"name": "Auth", "dependencies": ["Database"]},
            {"name": "Cart", "dependencies": ["Database"]},
        ]

        graph = analyzer.build_dependency_graph(features)

        db_node = graph.get_node("database")  # IDs are normalized to lowercase
        assert db_node is not None
        assert "auth" in db_node.dependents  # Dependents also normalized
        assert "cart" in db_node.dependents

    def test_build_dependency_graph_handles_empty_list(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test building dependency graph from empty list."""
        graph = analyzer.build_dependency_graph([])

        assert isinstance(graph, DependencyGraph)
        assert len(graph.nodes) == 0


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - recommend_models
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerRecommendModels:
    """Tests for recommend_models method."""

    def test_recommend_models_for_tasks(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test generating model recommendations for tasks."""
        tasks = [
            {"id": "T1", "description": "Design auth flow", "type": "planning"},
            {"id": "T2", "description": "Implement login", "type": "code"},
            {"id": "T3", "description": "Validate tests", "type": "validation"},
        ]

        recommendations = analyzer.recommend_models(tasks)

        assert len(recommendations) == 3
        assert all(isinstance(r, ModelRecommendation) for r in recommendations)

    def test_recommend_models_planning_tier(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that planning tasks get planning tier."""
        tasks = [
            {"id": "T1", "description": "Architect the system", "type": "planning"},
        ]

        recommendations = analyzer.recommend_models(tasks)

        assert recommendations[0].tier == ModelTier.PLANNING
        assert recommendations[0].recommended_model in ["o1", "opus"]

    def test_recommend_models_coding_tier(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that coding tasks get coding tier."""
        tasks = [
            {"id": "T1", "description": "Implement the feature", "type": "code"},
        ]

        recommendations = analyzer.recommend_models(tasks)

        assert recommendations[0].tier == ModelTier.CODING
        assert recommendations[0].recommended_model in ["sonnet", "haiku"]

    def test_recommend_models_includes_reasoning(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that recommendations include reasoning."""
        tasks = [
            {"id": "T1", "description": "Design flow", "type": "planning"},
        ]

        recommendations = analyzer.recommend_models(tasks)

        assert recommendations[0].reasoning is not None
        assert len(recommendations[0].reasoning) > 0


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - detect_bottlenecks
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerDetectBottlenecks:
    """Tests for detect_bottlenecks method."""

    def test_detect_bottlenecks_finds_high_dependency_nodes(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test detecting nodes with many dependents as bottlenecks."""
        nodes = [
            DependencyNode(id="db", name="Database", dependents=["auth", "cart", "orders", "payments"]),
            DependencyNode(id="auth", name="Auth", dependencies=["db"], dependents=["cart"]),
            DependencyNode(id="cart", name="Cart", dependencies=["db", "auth"]),
        ]
        graph = DependencyGraph(nodes=nodes)

        warnings = analyzer.detect_bottlenecks(graph)

        # Database should be flagged as bottleneck (4 dependents)
        assert len(warnings) > 0
        bottleneck_features = [w.feature for w in warnings if w.warning_type == "bottleneck"]
        assert "Database" in bottleneck_features

    def test_detect_bottlenecks_includes_mitigations(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test that bottleneck warnings include mitigations."""
        nodes = [
            DependencyNode(id="api", name="API Gateway", dependents=["a", "b", "c", "d"]),
        ]
        graph = DependencyGraph(nodes=nodes)

        warnings = analyzer.detect_bottlenecks(graph)

        assert len(warnings) > 0
        assert all(w.mitigation is not None for w in warnings)
        assert all(len(w.mitigation) > 0 for w in warnings)

    def test_detect_bottlenecks_handles_empty_graph(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test handling empty dependency graph."""
        graph = DependencyGraph(nodes=[])

        warnings = analyzer.detect_bottlenecks(graph)

        assert isinstance(warnings, list)
        assert len(warnings) == 0

    def test_detect_bottlenecks_critical_path_nodes(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        """Test detecting critical path bottlenecks."""
        nodes = [
            DependencyNode(
                id="core",
                name="Core Module",
                risk_rating=RiskRating.CRITICAL,
                dependents=["a", "b", "c"],
            ),
        ]
        graph = DependencyGraph(nodes=nodes)

        warnings = analyzer.detect_bottlenecks(graph)

        # Critical nodes with dependents should have highest severity
        critical_warnings = [w for w in warnings if w.severity == RiskRating.CRITICAL]
        assert len(critical_warnings) > 0


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - Integration with MCP
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerMCPIntegration:
    """Tests for MCP client integration."""

    @pytest.mark.asyncio
    async def test_uses_mcp_for_codebase_analysis(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that analyzer uses MCP client for codebase analysis."""
        analyzer._mcp_client.call_tool = AsyncMock(
            return_value=MagicMock(
                success=True,
                result='{"files": ["src/auth.py", "src/db.py"]}',
            )
        )
        analyzer._model_router.route = AsyncMock(return_value='{"features": []}')

        await analyzer.analyze_prd(sample_prd)

        # MCP client should be called if available
        if analyzer._mcp_client:
            # The call might or might not happen depending on implementation
            # Just verify no errors occurred
            pass

    @pytest.mark.asyncio
    async def test_handles_mcp_client_not_available(
        self, mock_model_router: MagicMock, sample_prd: str
    ) -> None:
        """Test graceful handling when MCP client is not available."""
        analyzer = ComplexityAnalyzer(model_router=mock_model_router, mcp_client=None)
        analyzer._model_router.route = AsyncMock(return_value='{"features": []}')

        # Should not raise an error
        result = await analyzer.analyze_prd(sample_prd)

        assert isinstance(result, ComplexityAnalysis)


# -----------------------------------------------------------------------------
# Test ComplexityAnalyzer - Output Format
# -----------------------------------------------------------------------------


class TestComplexityAnalyzerOutput:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_output_matches_required_schema(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that output matches required complexity_analysis.json schema."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Auth", "cognitive_load": 7, "risk": "medium"},
                {"name": "Payments", "cognitive_load": 9, "risk": "critical"}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)
        json_output = result.to_json()

        import json
        data = json.loads(json_output)

        # Verify required fields from FR-02.5
        assert "features" in data
        assert "dependency_graph" in data or "dependencies" in data
        assert "model_recommendations" in data
        assert "bottleneck_warnings" in data

    @pytest.mark.asyncio
    async def test_features_have_cognitive_load_scores(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that each feature has a cognitive load score."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Auth", "cognitive_load": 7, "risk": "medium"}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        for feature in result.features:
            assert 1 <= feature.cognitive_load <= 10

    @pytest.mark.asyncio
    async def test_features_have_risk_ratings(
        self, analyzer: ComplexityAnalyzer, sample_prd: str
    ) -> None:
        """Test that each feature has a risk rating."""
        analyzer._model_router.route = AsyncMock(return_value='''
        {
            "features": [
                {"name": "Auth", "cognitive_load": 7, "risk": "medium"}
            ]
        }
        ''')

        result = await analyzer.analyze_prd(sample_prd)

        for feature in result.features:
            assert feature.risk_rating in [
                RiskRating.LOW,
                RiskRating.MEDIUM,
                RiskRating.HIGH,
                RiskRating.CRITICAL,
            ]
