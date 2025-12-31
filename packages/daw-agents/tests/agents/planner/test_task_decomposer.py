"""Tests for TaskDecomposer - Task Decomposition Agent.

This module tests the TaskDecomposer class which:
1. Parses PRD markdown into structured tasks
2. Uses complexity scores to size tasks appropriately
3. Generates task IDs (e.g., FEATURE-001, BUG-001)
4. Infers dependencies between tasks
5. Assigns context_files based on task content
6. Creates verification criteria for each task
7. Outputs tasks.json compatible format
8. Validates all tasks before emitting

Task: TASK-DECOMP-001
Dependencies: PLANNER-001 (Taskmaster), COMPLEXITY-001 (ComplexityAnalyzer)
Reference: FR-02.4 in PRD
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.agents.planner.complexity_analyzer import (
    ComplexityAnalysis,
    ComplexityScore,
    DependencyGraph,
    DependencyNode,
    ModelRecommendation,
    ModelTier,
    RiskRating,
)
from daw_agents.agents.planner.task_decomposer import (
    DecomposedTask,
    DecompositionResult,
    TaskDecomposer,
    TaskDecomposerConfig,
    TaskPriority,
    TaskType,
    TaskVerification,
    VerificationType,
)
from daw_agents.agents.planner.taskmaster import PRDOutput

# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_prd() -> str:
    """Return a sample PRD for testing."""
    return """
# E-Commerce Platform PRD

## Overview
Build a full-featured e-commerce platform with authentication,
product catalog, shopping cart, and payment processing.

## User Stories

### US-001: User Authentication (P0)
As a user, I want to sign up and log in securely.
- Email/password registration
- OAuth (Google, GitHub) integration
- JWT token-based sessions

### US-002: Product Catalog (P0)
As a user, I want to browse products.
- Search with filters
- Categories and tags
- Pagination

### US-003: Shopping Cart (P1)
As a user, I want to add products to my cart.
- Add/remove items
- Update quantities

### US-004: Payment Processing (P0)
As a user, I want to checkout and pay securely.
- Stripe integration
- Order confirmation

## Tech Specs
- Frontend: React + TypeScript
- Backend: FastAPI + PostgreSQL
- Authentication: Clerk
- Payments: Stripe
"""


@pytest.fixture
def sample_prd_output() -> PRDOutput:
    """Return a sample PRDOutput for testing."""
    return PRDOutput(
        title="E-Commerce Platform",
        overview="Build a full-featured e-commerce platform",
        user_stories=[
            {
                "id": "US-001",
                "description": "As a user, I want to sign up and log in securely",
                "priority": "P0",
                "acceptance_criteria": [
                    "Email/password registration works",
                    "OAuth integration available",
                    "JWT tokens are issued",
                ],
            },
            {
                "id": "US-002",
                "description": "As a user, I want to browse products",
                "priority": "P0",
                "acceptance_criteria": [
                    "Search with filters works",
                    "Pagination works",
                ],
            },
            {
                "id": "US-003",
                "description": "As a user, I want to add products to cart",
                "priority": "P1",
                "acceptance_criteria": [
                    "Add/remove items works",
                ],
            },
        ],
        tech_specs={
            "architecture": "Microservices",
            "technology_stack": ["React", "FastAPI", "PostgreSQL"],
        },
        acceptance_criteria=["All P0 features work"],
    )


@pytest.fixture
def sample_complexity_analysis() -> ComplexityAnalysis:
    """Return a sample ComplexityAnalysis for testing."""
    return ComplexityAnalysis(
        prd_title="E-Commerce Platform",
        features=[
            ComplexityScore(
                feature="Authentication",
                cognitive_load=7,
                risk_rating=RiskRating.MEDIUM,
            ),
            ComplexityScore(
                feature="Product Catalog",
                cognitive_load=5,
                risk_rating=RiskRating.LOW,
            ),
            ComplexityScore(
                feature="Shopping Cart",
                cognitive_load=4,
                risk_rating=RiskRating.LOW,
            ),
            ComplexityScore(
                feature="Payment Processing",
                cognitive_load=9,
                risk_rating=RiskRating.CRITICAL,
            ),
        ],
        dependency_graph=DependencyGraph(
            nodes=[
                DependencyNode(
                    id="auth",
                    name="Authentication",
                    dependencies=[],
                    dependents=["cart", "payments"],
                ),
                DependencyNode(
                    id="catalog",
                    name="Product Catalog",
                    dependencies=[],
                    dependents=["cart"],
                ),
                DependencyNode(
                    id="cart",
                    name="Shopping Cart",
                    dependencies=["auth", "catalog"],
                    dependents=["payments"],
                ),
                DependencyNode(
                    id="payments",
                    name="Payment Processing",
                    dependencies=["auth", "cart"],
                    dependents=[],
                ),
            ]
        ),
        model_recommendations=[
            ModelRecommendation(
                task_id="TASK-001",
                task_description="Implement Authentication",
                tier=ModelTier.PLANNING,
                recommended_model="o1",
                reasoning="High complexity architecture task",
            ),
        ],
        bottleneck_warnings=[],
    )


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Create a mock ModelRouter."""
    router = AsyncMock()
    router.route = AsyncMock(return_value='[]')
    return router


@pytest.fixture
def mock_complexity_analyzer() -> MagicMock:
    """Create a mock ComplexityAnalyzer."""
    analyzer = AsyncMock()
    return analyzer


@pytest.fixture
def decomposer(
    mock_model_router: MagicMock,
    mock_complexity_analyzer: MagicMock,
) -> TaskDecomposer:
    """Create a TaskDecomposer with mocked dependencies."""
    return TaskDecomposer(
        model_router=mock_model_router,
        complexity_analyzer=mock_complexity_analyzer,
    )


# -----------------------------------------------------------------------------
# Test Enums
# -----------------------------------------------------------------------------


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_task_priority_values(self) -> None:
        """Test TaskPriority enum values."""
        assert TaskPriority.P0.value == "P0"
        assert TaskPriority.P1.value == "P1"
        assert TaskPriority.P2.value == "P2"

    def test_task_priority_from_string(self) -> None:
        """Test creating TaskPriority from string."""
        assert TaskPriority("P0") == TaskPriority.P0
        assert TaskPriority("P1") == TaskPriority.P1


class TestTaskType:
    """Tests for TaskType enum."""

    def test_task_type_values(self) -> None:
        """Test TaskType enum values."""
        assert TaskType.SETUP.value == "setup"
        assert TaskType.CODE.value == "code"
        assert TaskType.TEST.value == "test"
        assert TaskType.DOCS.value == "docs"
        assert TaskType.CONFIG.value == "config"


class TestVerificationType:
    """Tests for VerificationType enum."""

    def test_verification_type_values(self) -> None:
        """Test VerificationType enum values."""
        assert VerificationType.TEST_PASS.value == "test_pass"
        assert VerificationType.FILE_EXISTS.value == "file_exists"
        assert VerificationType.MANUAL.value == "manual"


# -----------------------------------------------------------------------------
# Test TaskVerification Model
# -----------------------------------------------------------------------------


class TestTaskVerification:
    """Tests for TaskVerification model."""

    def test_create_task_verification_test_pass(self) -> None:
        """Test creating a TaskVerification with test_pass type."""
        verification = TaskVerification(
            type=VerificationType.TEST_PASS,
            command="pytest tests/test_auth.py",
        )
        assert verification.type == VerificationType.TEST_PASS
        assert verification.command == "pytest tests/test_auth.py"

    def test_create_task_verification_file_exists(self) -> None:
        """Test creating a TaskVerification with file_exists type."""
        verification = TaskVerification(
            type=VerificationType.FILE_EXISTS,
            path="src/auth/handler.py",
        )
        assert verification.type == VerificationType.FILE_EXISTS
        assert verification.path == "src/auth/handler.py"

    def test_task_verification_to_dict(self) -> None:
        """Test serializing TaskVerification to dict."""
        verification = TaskVerification(
            type=VerificationType.TEST_PASS,
            command="pytest tests/",
        )
        data = verification.model_dump()
        assert data["type"] == "test_pass"
        assert "command" in data


# -----------------------------------------------------------------------------
# Test DecomposedTask Model
# -----------------------------------------------------------------------------


class TestDecomposedTask:
    """Tests for DecomposedTask model."""

    def test_create_decomposed_task_required_fields(self) -> None:
        """Test creating DecomposedTask with required fields."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement user authentication",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )
        assert task.id == "FEATURE-001"
        assert task.description == "Implement user authentication"
        assert task.priority == TaskPriority.P0
        assert task.type == TaskType.CODE

    def test_decomposed_task_with_dependencies(self) -> None:
        """Test DecomposedTask with dependencies."""
        task = DecomposedTask(
            id="FEATURE-002",
            description="Implement shopping cart",
            priority=TaskPriority.P1,
            type=TaskType.CODE,
            dependencies=["FEATURE-001"],
        )
        assert task.dependencies == ["FEATURE-001"]

    def test_decomposed_task_with_context_files(self) -> None:
        """Test DecomposedTask with context_files."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement auth",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
            context_files=[
                "src/auth/handler.py",
                "src/auth/models.py",
            ],
        )
        assert len(task.context_files) == 2
        assert "src/auth/handler.py" in task.context_files

    def test_decomposed_task_with_verification(self) -> None:
        """Test DecomposedTask with verification criteria."""
        verification = TaskVerification(
            type=VerificationType.TEST_PASS,
            command="pytest tests/test_auth.py",
        )
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement auth",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
            verification=verification,
        )
        assert task.verification is not None
        assert task.verification.type == VerificationType.TEST_PASS

    def test_decomposed_task_with_estimated_hours(self) -> None:
        """Test DecomposedTask with estimated hours."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement auth",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
            estimated_hours=4.0,
        )
        assert task.estimated_hours == 4.0

    def test_decomposed_task_with_model_hint(self) -> None:
        """Test DecomposedTask with model hint."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement auth",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
            model_hint="coding",
        )
        assert task.model_hint == "coding"

    def test_decomposed_task_default_values(self) -> None:
        """Test DecomposedTask default values."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Test task",
            priority=TaskPriority.P1,
            type=TaskType.CODE,
        )
        assert task.dependencies == []
        assert task.context_files == []
        assert task.verification is None
        assert task.estimated_hours is None
        assert task.model_hint is None
        assert task.instruction is None

    def test_decomposed_task_to_dict_matches_tasks_json_schema(self) -> None:
        """Test that serialized task matches tasks.json schema."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement auth",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
            dependencies=["SETUP-001"],
            context_files=["src/auth/handler.py"],
            verification=TaskVerification(
                type=VerificationType.TEST_PASS,
                command="pytest tests/test_auth.py",
            ),
            estimated_hours=3.0,
            model_hint="coding",
            instruction="Implement OAuth 2.0 authentication flow",
        )
        data = task.model_dump()

        # Verify all required fields for tasks.json schema
        assert "id" in data
        assert "description" in data
        assert "priority" in data
        assert "type" in data
        assert "dependencies" in data
        assert "context_files" in data
        assert "verification" in data
        assert "estimated_hours" in data
        assert "model_hint" in data
        assert "instruction" in data


# -----------------------------------------------------------------------------
# Test DecompositionResult Model
# -----------------------------------------------------------------------------


class TestDecompositionResult:
    """Tests for DecompositionResult model."""

    def test_create_decomposition_result(self) -> None:
        """Test creating DecompositionResult."""
        tasks = [
            DecomposedTask(
                id="FEATURE-001",
                description="Auth",
                priority=TaskPriority.P0,
                type=TaskType.CODE,
            ),
        ]
        result = DecompositionResult(
            prd_title="E-Commerce",
            tasks=tasks,
            total_estimated_hours=3.0,
        )
        assert result.prd_title == "E-Commerce"
        assert len(result.tasks) == 1

    def test_decomposition_result_to_json(self) -> None:
        """Test serializing DecompositionResult to JSON."""
        tasks = [
            DecomposedTask(
                id="FEATURE-001",
                description="Auth",
                priority=TaskPriority.P0,
                type=TaskType.CODE,
            ),
        ]
        result = DecompositionResult(
            prd_title="E-Commerce",
            tasks=tasks,
            total_estimated_hours=3.0,
        )
        json_output = result.to_json()
        assert "FEATURE-001" in json_output
        assert "E-Commerce" in json_output

    def test_decomposition_result_to_tasks_json_format(self) -> None:
        """Test converting result to tasks.json compatible format."""
        tasks = [
            DecomposedTask(
                id="FEATURE-001",
                description="Auth",
                priority=TaskPriority.P0,
                type=TaskType.CODE,
            ),
            DecomposedTask(
                id="FEATURE-002",
                description="Cart",
                priority=TaskPriority.P1,
                type=TaskType.CODE,
                dependencies=["FEATURE-001"],
            ),
        ]
        result = DecompositionResult(
            prd_title="E-Commerce",
            tasks=tasks,
            total_estimated_hours=6.0,
        )

        tasks_json = result.to_tasks_json()

        assert isinstance(tasks_json, list)
        assert len(tasks_json) == 2
        # Each task should have proper schema
        for task_dict in tasks_json:
            assert "id" in task_dict
            assert "description" in task_dict
            assert "priority" in task_dict
            assert "type" in task_dict


# -----------------------------------------------------------------------------
# Test TaskDecomposerConfig Model
# -----------------------------------------------------------------------------


class TestTaskDecomposerConfig:
    """Tests for TaskDecomposerConfig model."""

    def test_create_config_defaults(self) -> None:
        """Test creating config with defaults."""
        config = TaskDecomposerConfig()
        assert config.max_tasks_per_feature >= 1
        assert config.min_task_hours > 0
        assert config.max_task_hours > config.min_task_hours

    def test_create_config_custom(self) -> None:
        """Test creating config with custom values."""
        config = TaskDecomposerConfig(
            max_tasks_per_feature=10,
            min_task_hours=0.5,
            max_task_hours=8.0,
            id_prefix="TASK",
        )
        assert config.max_tasks_per_feature == 10
        assert config.id_prefix == "TASK"


# -----------------------------------------------------------------------------
# Test TaskDecomposer Initialization
# -----------------------------------------------------------------------------


class TestTaskDecomposerInit:
    """Tests for TaskDecomposer initialization."""

    def test_init_with_model_router(
        self, mock_model_router: MagicMock
    ) -> None:
        """Test initialization with model router."""
        decomposer = TaskDecomposer(model_router=mock_model_router)
        assert decomposer._model_router is not None

    def test_init_with_complexity_analyzer(
        self, mock_model_router: MagicMock,
        mock_complexity_analyzer: MagicMock,
    ) -> None:
        """Test initialization with complexity analyzer."""
        decomposer = TaskDecomposer(
            model_router=mock_model_router,
            complexity_analyzer=mock_complexity_analyzer,
        )
        assert decomposer._complexity_analyzer is not None

    def test_init_with_config(
        self, mock_model_router: MagicMock
    ) -> None:
        """Test initialization with custom config."""
        config = TaskDecomposerConfig(id_prefix="CUSTOM")
        decomposer = TaskDecomposer(
            model_router=mock_model_router,
            config=config,
        )
        assert decomposer._config.id_prefix == "CUSTOM"

    def test_init_creates_defaults(self) -> None:
        """Test initialization creates default dependencies."""
        with patch("daw_agents.agents.planner.task_decomposer.ModelRouter") as mock:
            mock.return_value = MagicMock()
            decomposer = TaskDecomposer()
            assert decomposer._model_router is not None


# -----------------------------------------------------------------------------
# Test TaskDecomposer.decompose_prd()
# -----------------------------------------------------------------------------


class TestTaskDecomposerDecomposePrd:
    """Tests for decompose_prd method."""

    @pytest.mark.asyncio
    async def test_decompose_prd_returns_result(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that decompose_prd returns a DecompositionResult."""
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {
                "id": "FEATURE-001",
                "description": "Setup project structure",
                "priority": "P0",
                "type": "setup",
                "dependencies": []
            }
        ]
        ''')
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )

        result = await decomposer.decompose_prd(sample_prd)

        assert isinstance(result, DecompositionResult)
        assert len(result.tasks) > 0

    @pytest.mark.asyncio
    async def test_decompose_prd_uses_complexity_scores(
        self, decomposer: TaskDecomposer,
        sample_prd: str,
        sample_complexity_analysis: ComplexityAnalysis,
    ) -> None:
        """Test that decompose_prd uses complexity scores for sizing."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=sample_complexity_analysis
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {
                "id": "FEATURE-001",
                "description": "Implement authentication",
                "priority": "P0",
                "type": "code"
            }
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)

        # Verify complexity analyzer was called
        decomposer._complexity_analyzer.analyze_prd.assert_called_once()

    @pytest.mark.asyncio
    async def test_decompose_prd_generates_task_ids(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that decompose_prd generates proper task IDs."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {"id": "TASK-001", "description": "Task 1", "priority": "P0", "type": "setup"},
            {"id": "TASK-002", "description": "Task 2", "priority": "P0", "type": "code"}
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)

        # All tasks should have proper IDs
        for task in result.tasks:
            assert task.id is not None
            assert len(task.id) > 0
            # ID should match pattern like FEATURE-001, TASK-001, etc.
            assert "-" in task.id

    @pytest.mark.asyncio
    async def test_decompose_prd_infers_dependencies(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that decompose_prd infers task dependencies."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(
                    nodes=[
                        DependencyNode(
                            id="auth",
                            name="Auth",
                            dependencies=[],
                            dependents=["cart"],
                        ),
                        DependencyNode(
                            id="cart",
                            name="Cart",
                            dependencies=["auth"],
                            dependents=[],
                        ),
                    ]
                ),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {"id": "AUTH-001", "description": "Auth", "priority": "P0", "type": "code", "dependencies": []},
            {"id": "CART-001", "description": "Cart", "priority": "P1", "type": "code", "dependencies": ["AUTH-001"]}
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)

        # Find cart task and check dependencies
        cart_tasks = [t for t in result.tasks if "Cart" in t.description or "CART" in t.id]
        if cart_tasks:
            cart_task = cart_tasks[0]
            assert len(cart_task.dependencies) > 0

    @pytest.mark.asyncio
    async def test_decompose_prd_assigns_context_files(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that decompose_prd assigns context_files to tasks."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {
                "id": "FEATURE-001",
                "description": "Implement authentication handler",
                "priority": "P0",
                "type": "code",
                "context_files": ["src/auth/handler.py", "src/auth/models.py"]
            }
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)

        # Check that at least some tasks have context_files
        tasks_with_files = [t for t in result.tasks if t.context_files]
        assert len(tasks_with_files) > 0

    @pytest.mark.asyncio
    async def test_decompose_prd_creates_verification_criteria(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that decompose_prd creates verification criteria."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {
                "id": "FEATURE-001",
                "description": "Implement authentication",
                "priority": "P0",
                "type": "code",
                "verification": {
                    "type": "test_pass",
                    "command": "pytest tests/test_auth.py"
                }
            }
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)

        # Check that tasks have verification criteria
        tasks_with_verification = [t for t in result.tasks if t.verification]
        assert len(tasks_with_verification) > 0


# -----------------------------------------------------------------------------
# Test TaskDecomposer.decompose_prd_output()
# -----------------------------------------------------------------------------


class TestTaskDecomposerDecomposePrdOutput:
    """Tests for decompose_prd_output method."""

    @pytest.mark.asyncio
    async def test_decompose_prd_output_accepts_prd_output(
        self, decomposer: TaskDecomposer, sample_prd_output: PRDOutput
    ) -> None:
        """Test that decompose_prd_output accepts PRDOutput."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title=sample_prd_output.title,
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [{"id": "TASK-001", "description": "Test", "priority": "P0", "type": "setup"}]
        ''')

        result = await decomposer.decompose_prd_output(sample_prd_output)

        assert isinstance(result, DecompositionResult)
        assert result.prd_title == sample_prd_output.title


# -----------------------------------------------------------------------------
# Test TaskDecomposer Task ID Generation
# -----------------------------------------------------------------------------


class TestTaskDecomposerIdGeneration:
    """Tests for task ID generation."""

    def test_generate_task_id_with_prefix(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test generating task ID with prefix."""
        task_id = decomposer.generate_task_id("FEATURE", 1)
        assert task_id == "FEATURE-001"

    def test_generate_task_id_sequence(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test generating sequential task IDs."""
        id1 = decomposer.generate_task_id("TASK", 1)
        id2 = decomposer.generate_task_id("TASK", 2)
        id3 = decomposer.generate_task_id("TASK", 10)

        assert id1 == "TASK-001"
        assert id2 == "TASK-002"
        assert id3 == "TASK-010"

    def test_generate_task_id_different_prefixes(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test generating IDs with different prefixes."""
        feature_id = decomposer.generate_task_id("FEATURE", 1)
        bug_id = decomposer.generate_task_id("BUG", 1)
        setup_id = decomposer.generate_task_id("SETUP", 1)

        assert feature_id.startswith("FEATURE-")
        assert bug_id.startswith("BUG-")
        assert setup_id.startswith("SETUP-")


# -----------------------------------------------------------------------------
# Test TaskDecomposer Dependency Inference
# -----------------------------------------------------------------------------


class TestTaskDecomposerDependencyInference:
    """Tests for dependency inference."""

    def test_infer_dependencies_from_graph(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test inferring dependencies from complexity graph."""
        graph = DependencyGraph(
            nodes=[
                DependencyNode(
                    id="auth",
                    name="Authentication",
                    dependencies=[],
                    dependents=["cart"],
                ),
                DependencyNode(
                    id="cart",
                    name="Shopping Cart",
                    dependencies=["auth"],
                    dependents=[],
                ),
            ]
        )
        tasks = [
            DecomposedTask(
                id="AUTH-001",
                description="Implement Authentication",
                priority=TaskPriority.P0,
                type=TaskType.CODE,
            ),
            DecomposedTask(
                id="CART-001",
                description="Implement Shopping Cart",
                priority=TaskPriority.P1,
                type=TaskType.CODE,
            ),
        ]

        enriched_tasks = decomposer.infer_dependencies(tasks, graph)

        # Cart should depend on Auth
        cart_task = next(t for t in enriched_tasks if "CART" in t.id)
        assert "AUTH-001" in cart_task.dependencies

    def test_infer_dependencies_handles_no_graph(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test handling empty dependency graph."""
        graph = DependencyGraph(nodes=[])
        tasks = [
            DecomposedTask(
                id="TASK-001",
                description="Test",
                priority=TaskPriority.P0,
                type=TaskType.CODE,
            ),
        ]

        enriched_tasks = decomposer.infer_dependencies(tasks, graph)

        assert len(enriched_tasks) == 1
        assert enriched_tasks[0].dependencies == []


# -----------------------------------------------------------------------------
# Test TaskDecomposer Context File Assignment
# -----------------------------------------------------------------------------


class TestTaskDecomposerContextFiles:
    """Tests for context file assignment."""

    def test_infer_context_files_from_description(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test inferring context files from task description."""
        task = DecomposedTask(
            id="AUTH-001",
            description="Implement authentication handler with OAuth support",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )

        context_files = decomposer.infer_context_files(task)

        # Should infer auth-related file paths
        assert len(context_files) > 0

    def test_infer_context_files_for_test_task(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test inferring context files for test tasks."""
        task = DecomposedTask(
            id="TEST-001",
            description="Write unit tests for authentication",
            priority=TaskPriority.P1,
            type=TaskType.TEST,
        )

        context_files = decomposer.infer_context_files(task)

        # Should include test directory
        assert any("test" in f.lower() for f in context_files)


# -----------------------------------------------------------------------------
# Test TaskDecomposer Verification Generation
# -----------------------------------------------------------------------------


class TestTaskDecomposerVerification:
    """Tests for verification criteria generation."""

    def test_generate_verification_for_code_task(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test generating verification for code tasks."""
        task = DecomposedTask(
            id="AUTH-001",
            description="Implement authentication",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )

        verification = decomposer.generate_verification(task)

        assert verification is not None
        assert verification.type == VerificationType.TEST_PASS
        assert verification.command is not None

    def test_generate_verification_for_setup_task(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test generating verification for setup tasks."""
        task = DecomposedTask(
            id="SETUP-001",
            description="Create project directory structure",
            priority=TaskPriority.P0,
            type=TaskType.SETUP,
        )

        verification = decomposer.generate_verification(task)

        assert verification is not None
        assert verification.type in [
            VerificationType.FILE_EXISTS,
            VerificationType.TEST_PASS,
        ]

    def test_generate_verification_for_docs_task(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test generating verification for docs tasks."""
        task = DecomposedTask(
            id="DOCS-001",
            description="Write API documentation",
            priority=TaskPriority.P2,
            type=TaskType.DOCS,
        )

        verification = decomposer.generate_verification(task)

        assert verification is not None


# -----------------------------------------------------------------------------
# Test TaskDecomposer Hour Estimation
# -----------------------------------------------------------------------------


class TestTaskDecomposerHourEstimation:
    """Tests for hour estimation."""

    def test_estimate_hours_from_complexity(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test estimating hours from complexity score."""
        # High complexity = more hours
        high_complexity = ComplexityScore(
            feature="Payment",
            cognitive_load=9,
            risk_rating=RiskRating.CRITICAL,
        )
        low_complexity = ComplexityScore(
            feature="Static Page",
            cognitive_load=2,
            risk_rating=RiskRating.LOW,
        )

        high_hours = decomposer.estimate_hours(high_complexity)
        low_hours = decomposer.estimate_hours(low_complexity)

        assert high_hours > low_hours
        assert high_hours <= decomposer._config.max_task_hours
        assert low_hours >= decomposer._config.min_task_hours

    def test_estimate_hours_respects_config_bounds(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test that hour estimates respect config bounds."""
        extreme_complexity = ComplexityScore(
            feature="Complex",
            cognitive_load=10,
            risk_rating=RiskRating.CRITICAL,
        )

        hours = decomposer.estimate_hours(extreme_complexity)

        assert hours <= decomposer._config.max_task_hours
        assert hours >= decomposer._config.min_task_hours


# -----------------------------------------------------------------------------
# Test TaskDecomposer JSON Schema Validation
# -----------------------------------------------------------------------------


class TestTaskDecomposerValidation:
    """Tests for task validation."""

    def test_validate_task_passes_valid_task(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test that valid tasks pass validation."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement authentication",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )

        is_valid = decomposer.validate_task(task)

        assert is_valid is True

    def test_validate_task_fails_empty_id(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test that tasks with empty ID fail validation."""
        task = DecomposedTask(
            id="",
            description="Test",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )

        is_valid = decomposer.validate_task(task)

        assert is_valid is False

    def test_validate_task_fails_empty_description(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test that tasks with empty description fail validation."""
        task = DecomposedTask(
            id="TASK-001",
            description="",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )

        is_valid = decomposer.validate_task(task)

        assert is_valid is False

    def test_validate_all_tasks(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test validating a list of tasks."""
        tasks = [
            DecomposedTask(
                id="TASK-001",
                description="Valid task",
                priority=TaskPriority.P0,
                type=TaskType.CODE,
            ),
            DecomposedTask(
                id="TASK-002",
                description="Another valid task",
                priority=TaskPriority.P1,
                type=TaskType.TEST,
            ),
        ]

        all_valid = decomposer.validate_all(tasks)

        assert all_valid is True


# -----------------------------------------------------------------------------
# Test TaskDecomposer Model Hint Assignment
# -----------------------------------------------------------------------------


class TestTaskDecomposerModelHint:
    """Tests for model hint assignment."""

    def test_assign_model_hint_for_setup(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test model hint for setup tasks."""
        task = DecomposedTask(
            id="SETUP-001",
            description="Initialize project",
            priority=TaskPriority.P0,
            type=TaskType.SETUP,
        )

        hint = decomposer.assign_model_hint(task)

        assert hint == "fast"

    def test_assign_model_hint_for_code(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test model hint for code tasks."""
        task = DecomposedTask(
            id="FEATURE-001",
            description="Implement feature",
            priority=TaskPriority.P0,
            type=TaskType.CODE,
        )

        hint = decomposer.assign_model_hint(task)

        assert hint == "coding"

    def test_assign_model_hint_for_docs(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test model hint for docs tasks."""
        task = DecomposedTask(
            id="DOCS-001",
            description="Write documentation",
            priority=TaskPriority.P2,
            type=TaskType.DOCS,
        )

        hint = decomposer.assign_model_hint(task)

        assert hint == "fast"


# -----------------------------------------------------------------------------
# Test TaskDecomposer Output Format
# -----------------------------------------------------------------------------


class TestTaskDecomposerOutput:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_output_matches_tasks_json_schema(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that output matches tasks.json schema."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {
                "id": "TASK-001",
                "description": "Setup project",
                "priority": "P0",
                "type": "setup",
                "dependencies": [],
                "verification": {"type": "file_exists", "path": "src/"}
            }
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)
        tasks_json = result.to_tasks_json()

        # Verify each task matches schema
        for task_dict in tasks_json:
            assert isinstance(task_dict["id"], str)
            assert isinstance(task_dict["description"], str)
            assert task_dict["priority"] in ["P0", "P1", "P2"]
            assert task_dict["type"] in ["setup", "code", "test", "docs", "config"]

    @pytest.mark.asyncio
    async def test_output_can_be_serialized_to_json(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test that output can be serialized to valid JSON."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [{"id": "TASK-001", "description": "Test", "priority": "P0", "type": "setup"}]
        ''')

        result = await decomposer.decompose_prd(sample_prd)
        json_output = result.to_json()

        # Should be valid JSON
        parsed = json.loads(json_output)
        assert "tasks" in parsed or isinstance(parsed, list)


# -----------------------------------------------------------------------------
# Test TaskDecomposer Error Handling
# -----------------------------------------------------------------------------


class TestTaskDecomposerErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handles_invalid_prd(
        self, decomposer: TaskDecomposer
    ) -> None:
        """Test handling invalid/empty PRD."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Empty",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='[]')

        result = await decomposer.decompose_prd("")

        assert isinstance(result, DecompositionResult)
        # May have no tasks for empty PRD, but should not raise

    @pytest.mark.asyncio
    async def test_handles_llm_error(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test handling LLM errors gracefully."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(
            side_effect=Exception("LLM error")
        )

        with pytest.raises(Exception):
            await decomposer.decompose_prd(sample_prd)

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test handling invalid JSON from LLM."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="Test",
                features=[],
                dependency_graph=DependencyGraph(nodes=[]),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(
            return_value="This is not valid JSON"
        )

        # Should handle gracefully, possibly returning empty result
        result = await decomposer.decompose_prd(sample_prd)
        assert isinstance(result, DecompositionResult)


# -----------------------------------------------------------------------------
# Test TaskDecomposer Integration
# -----------------------------------------------------------------------------


class TestTaskDecomposerIntegration:
    """Integration tests for TaskDecomposer."""

    @pytest.mark.asyncio
    async def test_full_decomposition_workflow(
        self, decomposer: TaskDecomposer, sample_prd: str
    ) -> None:
        """Test complete decomposition workflow."""
        decomposer._complexity_analyzer.analyze_prd = AsyncMock(
            return_value=ComplexityAnalysis(
                prd_title="E-Commerce Platform",
                features=[
                    ComplexityScore(
                        feature="Authentication",
                        cognitive_load=7,
                        risk_rating=RiskRating.MEDIUM,
                    ),
                    ComplexityScore(
                        feature="Product Catalog",
                        cognitive_load=5,
                        risk_rating=RiskRating.LOW,
                    ),
                ],
                dependency_graph=DependencyGraph(
                    nodes=[
                        DependencyNode(
                            id="auth",
                            name="Authentication",
                            dependencies=[],
                            dependents=["catalog"],
                        ),
                        DependencyNode(
                            id="catalog",
                            name="Product Catalog",
                            dependencies=["auth"],
                            dependents=[],
                        ),
                    ]
                ),
                model_recommendations=[],
                bottleneck_warnings=[],
            )
        )
        decomposer._model_router.route = AsyncMock(return_value='''
        [
            {
                "id": "SETUP-001",
                "description": "Initialize project structure",
                "priority": "P0",
                "type": "setup"
            },
            {
                "id": "AUTH-001",
                "description": "Implement user authentication",
                "priority": "P0",
                "type": "code",
                "dependencies": ["SETUP-001"]
            },
            {
                "id": "CATALOG-001",
                "description": "Implement product catalog",
                "priority": "P0",
                "type": "code",
                "dependencies": ["SETUP-001", "AUTH-001"]
            },
            {
                "id": "TEST-001",
                "description": "Write tests for authentication",
                "priority": "P1",
                "type": "test",
                "dependencies": ["AUTH-001"]
            }
        ]
        ''')

        result = await decomposer.decompose_prd(sample_prd)

        # Verify result structure
        assert result.prd_title == "E-Commerce Platform"
        assert len(result.tasks) == 4

        # Verify task order respects dependencies
        task_ids = [t.id for t in result.tasks]
        assert task_ids.index("SETUP-001") < task_ids.index("AUTH-001")
        assert task_ids.index("AUTH-001") < task_ids.index("CATALOG-001")
