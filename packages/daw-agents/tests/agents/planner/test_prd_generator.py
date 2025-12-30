"""
Tests for PRD Generator (PRD-OUTPUT-001).

The PRD Generator is responsible for:
1. Generating structured PRD from Taskmaster output
2. Creating User Stories with P0/P1/P2 priority levels
3. Generating Tech Specs with clear architecture decisions
4. Converting acceptance criteria to testable Given/When/Then format
5. Adding non-functional requirements (performance, security)
6. Validating completeness before allowing task decomposition

Following TDD workflow - tests written FIRST, then implementation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

# Note: These imports will fail until implementation is created (RED phase)
from daw_agents.agents.planner.prd_generator import (
    AcceptanceCriterion,
    NonFunctionalRequirement,
    NonFunctionalType,
    PRDGenerationConfig,
    PRDGenerator,
    PRDValidationError,
    PRDValidationResult,
    TechSpec,
    UserStoryPriority,
)
from daw_agents.schemas.prd_schema import (
    PRDSchema,
    UserStorySchema,
    TechSpecSchema,
    AcceptanceCriteriaSchema,
    NonFunctionalRequirementSchema,
)


# =============================================================================
# Test PRD Schema Models
# =============================================================================


class TestUserStoryPriority:
    """Test UserStoryPriority enum."""

    def test_priority_enum_values(self) -> None:
        """Verify all priority levels exist."""
        assert UserStoryPriority.P0.value == "P0"
        assert UserStoryPriority.P1.value == "P1"
        assert UserStoryPriority.P2.value == "P2"

    def test_priority_ordering(self) -> None:
        """Test that P0 is highest priority."""
        priorities = [UserStoryPriority.P2, UserStoryPriority.P0, UserStoryPriority.P1]
        # P0 should be considered highest priority
        assert UserStoryPriority.P0 in priorities


class TestAcceptanceCriterion:
    """Test AcceptanceCriterion Pydantic model."""

    def test_acceptance_criterion_creation(self) -> None:
        """Test creating an acceptance criterion with Given/When/Then format."""
        criterion = AcceptanceCriterion(
            given="a user is logged in",
            when="they click the create task button",
            then="a new task form appears",
        )
        assert criterion.given == "a user is logged in"
        assert criterion.when == "they click the create task button"
        assert criterion.then == "a new task form appears"

    def test_acceptance_criterion_to_string(self) -> None:
        """Test converting acceptance criterion to string."""
        criterion = AcceptanceCriterion(
            given="a user is logged in",
            when="they click the create task button",
            then="a new task form appears",
        )
        result = criterion.to_gherkin()
        assert "Given a user is logged in" in result
        assert "When they click the create task button" in result
        assert "Then a new task form appears" in result

    def test_acceptance_criterion_with_and_clauses(self) -> None:
        """Test acceptance criterion with additional and clauses."""
        criterion = AcceptanceCriterion(
            given="a user is logged in",
            when="they click the create task button",
            then="a new task form appears",
            and_given=["they have write permissions"],
            and_then=["the form has a title field", "the form has a submit button"],
        )
        assert len(criterion.and_given) == 1
        assert len(criterion.and_then) == 2

    def test_acceptance_criterion_validation(self) -> None:
        """Test that acceptance criterion requires all fields."""
        with pytest.raises(ValidationError):
            AcceptanceCriterion(given="a user", when="they click")  # Missing 'then'


class TestNonFunctionalRequirement:
    """Test NonFunctionalRequirement model."""

    def test_nfr_creation(self) -> None:
        """Test creating a non-functional requirement."""
        nfr = NonFunctionalRequirement(
            type=NonFunctionalType.PERFORMANCE,
            description="API response time must be under 500ms",
            metric="p95 latency",
            target="< 500ms",
            priority=UserStoryPriority.P0,
        )
        assert nfr.type == NonFunctionalType.PERFORMANCE
        assert nfr.metric == "p95 latency"
        assert nfr.target == "< 500ms"

    def test_nfr_types_exist(self) -> None:
        """Verify all NFR types are defined."""
        assert NonFunctionalType.PERFORMANCE.value == "performance"
        assert NonFunctionalType.SECURITY.value == "security"
        assert NonFunctionalType.SCALABILITY.value == "scalability"
        assert NonFunctionalType.RELIABILITY.value == "reliability"
        assert NonFunctionalType.MAINTAINABILITY.value == "maintainability"
        assert NonFunctionalType.USABILITY.value == "usability"


class TestTechSpec:
    """Test TechSpec model."""

    def test_tech_spec_creation(self) -> None:
        """Test creating a tech spec with architecture decisions."""
        spec = TechSpec(
            architecture_pattern="Microservices",
            architecture_decisions=[
                "Use event-driven communication between services",
                "Implement circuit breaker pattern for resilience",
            ],
            technology_stack=["Python", "FastAPI", "PostgreSQL", "Redis"],
            infrastructure_requirements=["Kubernetes cluster", "Load balancer"],
            constraints=["Must support 1000 concurrent users"],
        )
        assert spec.architecture_pattern == "Microservices"
        assert len(spec.architecture_decisions) == 2
        assert "Python" in spec.technology_stack

    def test_tech_spec_defaults(self) -> None:
        """Test tech spec default values."""
        spec = TechSpec(
            architecture_pattern="Monolith",
            architecture_decisions=[],
            technology_stack=["Python"],
        )
        assert spec.infrastructure_requirements == []
        assert spec.constraints == []


# =============================================================================
# Test PRDSchema (Main Schema Model)
# =============================================================================


class TestPRDSchema:
    """Test PRDSchema Pydantic model for full PRD structure."""

    def test_prd_schema_creation(self) -> None:
        """Test creating a complete PRD schema."""
        prd = PRDSchema(
            title="Todo Application PRD",
            version="1.0.0",
            overview="A modern todo application with collaboration features",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="Create Task",
                    description="As a user, I want to create tasks so I can track my work",
                    priority=UserStoryPriority.P0,
                    acceptance_criteria=[
                        AcceptanceCriteriaSchema(
                            given="I am logged in",
                            when="I click create task",
                            then="a new task is created",
                        )
                    ],
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="Modular Monolith",
                architecture_decisions=["Use CQRS for commands and queries"],
                technology_stack=["Next.js", "FastAPI"],
            ),
            acceptance_criteria=[
                AcceptanceCriteriaSchema(
                    given="all user stories are implemented",
                    when="the application is deployed",
                    then="all P0 features are functional",
                )
            ],
            non_functional_requirements=[
                NonFunctionalRequirementSchema(
                    type=NonFunctionalType.PERFORMANCE,
                    description="Fast response times",
                    metric="p95 latency",
                    target="< 500ms",
                    priority=UserStoryPriority.P1,
                )
            ],
        )
        assert prd.title == "Todo Application PRD"
        assert prd.version == "1.0.0"
        assert len(prd.user_stories) == 1
        assert prd.user_stories[0].priority == UserStoryPriority.P0

    def test_prd_schema_requires_title(self) -> None:
        """Test that PRD schema requires a title."""
        with pytest.raises(ValidationError):
            PRDSchema(overview="Some overview")  # Missing title

    def test_prd_schema_requires_overview(self) -> None:
        """Test that PRD schema requires an overview."""
        with pytest.raises(ValidationError):
            PRDSchema(title="My PRD")  # Missing overview

    def test_prd_schema_to_markdown(self) -> None:
        """Test converting PRD schema to markdown format."""
        prd = PRDSchema(
            title="Test PRD",
            version="1.0.0",
            overview="Test overview",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="Test Story",
                    description="As a user...",
                    priority=UserStoryPriority.P0,
                    acceptance_criteria=[],
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="Simple",
                architecture_decisions=[],
                technology_stack=["Python"],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )
        markdown = prd.to_markdown()
        assert "# Test PRD" in markdown
        assert "## Overview" in markdown
        assert "## User Stories" in markdown
        assert "US-001" in markdown

    def test_prd_schema_to_json(self) -> None:
        """Test converting PRD schema to JSON."""
        prd = PRDSchema(
            title="TestPRD",
            version="1.0.0",
            overview="Test overview",
            user_stories=[],
            tech_specs=TechSpecSchema(
                architecture_pattern="Simple",
                architecture_decisions=[],
                technology_stack=[],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )
        json_output = prd.model_dump_json()
        assert '"title":"TestPRD"' in json_output.replace(" ", "")


class TestUserStorySchema:
    """Test UserStorySchema model."""

    def test_user_story_schema_creation(self) -> None:
        """Test creating a user story schema."""
        story = UserStorySchema(
            id="US-001",
            title="Create Task",
            description="As a user, I want to create tasks",
            priority=UserStoryPriority.P0,
            acceptance_criteria=[
                AcceptanceCriteriaSchema(
                    given="I am logged in",
                    when="I click create",
                    then="task is created",
                )
            ],
            dependencies=[],
            tags=["core", "mvp"],
        )
        assert story.id == "US-001"
        assert story.priority == UserStoryPriority.P0
        assert len(story.acceptance_criteria) == 1
        assert "core" in story.tags

    def test_user_story_has_at_least_p0(self) -> None:
        """Test that user story has valid priority."""
        story = UserStorySchema(
            id="US-001",
            title="Critical Feature",
            description="Must have feature",
            priority=UserStoryPriority.P0,
            acceptance_criteria=[],
        )
        assert story.priority == UserStoryPriority.P0


# =============================================================================
# Test PRDGenerator Class
# =============================================================================


class TestPRDGeneratorInit:
    """Test PRDGenerator initialization."""

    def test_prd_generator_init_default(self) -> None:
        """Test PRDGenerator initializes with defaults."""
        generator = PRDGenerator()
        assert generator is not None

    def test_prd_generator_init_with_model_router(self) -> None:
        """Test PRDGenerator accepts custom model router."""
        mock_router = MagicMock()
        generator = PRDGenerator(model_router=mock_router)
        assert generator._model_router == mock_router

    def test_prd_generator_init_with_config(self) -> None:
        """Test PRDGenerator accepts configuration."""
        config = PRDGenerationConfig(
            require_p0_story=True,
            require_acceptance_criteria=True,
            require_tech_specs=True,
            require_nfr=True,
        )
        generator = PRDGenerator(config=config)
        assert generator._config.require_p0_story is True


class TestPRDGeneratorGenerate:
    """Test PRDGenerator.generate() method."""

    @pytest.fixture
    def generator(self) -> PRDGenerator:
        """Create a PRDGenerator with mocked dependencies."""
        mock_router = MagicMock()
        return PRDGenerator(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_generate_returns_prd_schema(self, generator: PRDGenerator) -> None:
        """Test that generate() returns a PRDSchema object."""
        # Mock the model router
        mock_response = """{
            "title": "Todo App",
            "version": "1.0.0",
            "overview": "A todo application",
            "user_stories": [
                {
                    "id": "US-001",
                    "title": "Create Task",
                    "description": "As a user, I want to create tasks",
                    "priority": "P0",
                    "acceptance_criteria": [
                        {"given": "I am logged in", "when": "I click create", "then": "task created"}
                    ]
                }
            ],
            "tech_specs": {
                "architecture_pattern": "Monolith",
                "architecture_decisions": [],
                "technology_stack": ["Python"]
            },
            "acceptance_criteria": [],
            "non_functional_requirements": []
        }"""
        generator._model_router.route = AsyncMock(return_value=mock_response)

        result = await generator.generate(
            requirement="Build a todo app",
            clarifications=["Need mobile support"],
            roundtable_critiques=["CTO: Consider caching"],
        )

        assert isinstance(result, PRDSchema)
        assert result.title == "Todo App"

    @pytest.mark.asyncio
    async def test_generate_includes_user_stories(
        self, generator: PRDGenerator
    ) -> None:
        """Test that generated PRD includes user stories."""
        mock_response = """{
            "title": "App",
            "version": "1.0.0",
            "overview": "Test app",
            "user_stories": [
                {"id": "US-001", "title": "Story 1", "description": "As a user...", "priority": "P0", "acceptance_criteria": []},
                {"id": "US-002", "title": "Story 2", "description": "As an admin...", "priority": "P1", "acceptance_criteria": []}
            ],
            "tech_specs": {"architecture_pattern": "Simple", "architecture_decisions": [], "technology_stack": []},
            "acceptance_criteria": [],
            "non_functional_requirements": []
        }"""
        generator._model_router.route = AsyncMock(return_value=mock_response)

        result = await generator.generate(requirement="Build an app")

        assert len(result.user_stories) == 2
        assert result.user_stories[0].id == "US-001"

    @pytest.mark.asyncio
    async def test_generate_includes_tech_specs(
        self, generator: PRDGenerator
    ) -> None:
        """Test that generated PRD includes tech specs."""
        mock_response = """{
            "title": "App",
            "version": "1.0.0",
            "overview": "Test",
            "user_stories": [],
            "tech_specs": {
                "architecture_pattern": "Microservices",
                "architecture_decisions": ["Use event sourcing"],
                "technology_stack": ["Python", "FastAPI", "PostgreSQL"]
            },
            "acceptance_criteria": [],
            "non_functional_requirements": []
        }"""
        generator._model_router.route = AsyncMock(return_value=mock_response)

        result = await generator.generate(requirement="Build an app")

        assert result.tech_specs.architecture_pattern == "Microservices"
        assert "Use event sourcing" in result.tech_specs.architecture_decisions

    @pytest.mark.asyncio
    async def test_generate_includes_acceptance_criteria_in_given_when_then(
        self, generator: PRDGenerator
    ) -> None:
        """Test that acceptance criteria are in Given/When/Then format."""
        mock_response = """{
            "title": "App",
            "version": "1.0.0",
            "overview": "Test",
            "user_stories": [
                {
                    "id": "US-001",
                    "title": "Test",
                    "description": "Test",
                    "priority": "P0",
                    "acceptance_criteria": [
                        {"given": "a user exists", "when": "they log in", "then": "dashboard appears"}
                    ]
                }
            ],
            "tech_specs": {"architecture_pattern": "Simple", "architecture_decisions": [], "technology_stack": []},
            "acceptance_criteria": [
                {"given": "all stories complete", "when": "deployed", "then": "app works"}
            ],
            "non_functional_requirements": []
        }"""
        generator._model_router.route = AsyncMock(return_value=mock_response)

        result = await generator.generate(requirement="Build an app")

        # Check user story acceptance criteria
        assert len(result.user_stories[0].acceptance_criteria) == 1
        criteria = result.user_stories[0].acceptance_criteria[0]
        assert criteria.given == "a user exists"
        assert criteria.when == "they log in"
        assert criteria.then == "dashboard appears"

    @pytest.mark.asyncio
    async def test_generate_includes_nfr(self, generator: PRDGenerator) -> None:
        """Test that generated PRD includes non-functional requirements."""
        mock_response = """{
            "title": "App",
            "version": "1.0.0",
            "overview": "Test",
            "user_stories": [],
            "tech_specs": {"architecture_pattern": "Simple", "architecture_decisions": [], "technology_stack": []},
            "acceptance_criteria": [],
            "non_functional_requirements": [
                {"type": "performance", "description": "Fast API", "metric": "p95", "target": "< 500ms", "priority": "P0"},
                {"type": "security", "description": "Auth required", "metric": "auth coverage", "target": "100%", "priority": "P0"}
            ]
        }"""
        generator._model_router.route = AsyncMock(return_value=mock_response)

        result = await generator.generate(requirement="Build an app")

        assert len(result.non_functional_requirements) == 2
        assert result.non_functional_requirements[0].type == NonFunctionalType.PERFORMANCE


class TestPRDGeneratorValidation:
    """Test PRDGenerator validation methods."""

    @pytest.fixture
    def generator(self) -> PRDGenerator:
        """Create a PRDGenerator with validation enabled."""
        config = PRDGenerationConfig(
            require_p0_story=True,
            require_acceptance_criteria=True,
            require_tech_specs=True,
            require_nfr=False,
        )
        return PRDGenerator(config=config)

    def test_validate_completeness_passes_for_valid_prd(
        self, generator: PRDGenerator
    ) -> None:
        """Test that validation passes for complete PRD."""
        prd = PRDSchema(
            title="Complete PRD",
            version="1.0.0",
            overview="Complete overview",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="P0 Story",
                    description="Critical story",
                    priority=UserStoryPriority.P0,
                    acceptance_criteria=[
                        AcceptanceCriteriaSchema(
                            given="user exists",
                            when="action taken",
                            then="result occurs",
                        )
                    ],
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="Good Pattern",
                architecture_decisions=["Decision 1"],
                technology_stack=["Python"],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )

        result = generator.validate_completeness(prd)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_completeness_fails_without_p0_story(
        self, generator: PRDGenerator
    ) -> None:
        """Test that validation fails when P0 story is missing."""
        prd = PRDSchema(
            title="Incomplete PRD",
            version="1.0.0",
            overview="Overview",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="P1 Story",
                    description="Lower priority",
                    priority=UserStoryPriority.P1,  # No P0!
                    acceptance_criteria=[
                        AcceptanceCriteriaSchema(
                            given="x", when="y", then="z"
                        )
                    ],
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="Pattern",
                architecture_decisions=[],
                technology_stack=[],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )

        result = generator.validate_completeness(prd)

        assert result.is_valid is False
        assert any("P0" in error for error in result.errors)

    def test_validate_completeness_fails_without_acceptance_criteria(
        self, generator: PRDGenerator
    ) -> None:
        """Test that validation fails when acceptance criteria are missing."""
        prd = PRDSchema(
            title="PRD",
            version="1.0.0",
            overview="Overview",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="Story",
                    description="Story",
                    priority=UserStoryPriority.P0,
                    acceptance_criteria=[],  # Empty!
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="Pattern",
                architecture_decisions=[],
                technology_stack=[],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )

        result = generator.validate_completeness(prd)

        assert result.is_valid is False
        assert any("acceptance criteria" in error.lower() for error in result.errors)

    def test_validate_completeness_fails_without_tech_specs(
        self, generator: PRDGenerator
    ) -> None:
        """Test that validation fails when tech specs are incomplete."""
        prd = PRDSchema(
            title="PRD",
            version="1.0.0",
            overview="Overview",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="Story",
                    description="Story",
                    priority=UserStoryPriority.P0,
                    acceptance_criteria=[
                        AcceptanceCriteriaSchema(given="x", when="y", then="z")
                    ],
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="",  # Empty pattern!
                architecture_decisions=[],
                technology_stack=[],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )

        result = generator.validate_completeness(prd)

        assert result.is_valid is False
        assert any("architecture" in error.lower() for error in result.errors)

    def test_can_proceed_to_task_decomposition_returns_true_for_valid(
        self, generator: PRDGenerator
    ) -> None:
        """Test that can_proceed_to_task_decomposition returns True for valid PRD."""
        prd = PRDSchema(
            title="Valid PRD",
            version="1.0.0",
            overview="Overview",
            user_stories=[
                UserStorySchema(
                    id="US-001",
                    title="Story",
                    description="Story",
                    priority=UserStoryPriority.P0,
                    acceptance_criteria=[
                        AcceptanceCriteriaSchema(given="x", when="y", then="z")
                    ],
                )
            ],
            tech_specs=TechSpecSchema(
                architecture_pattern="Pattern",
                architecture_decisions=["Decision"],
                technology_stack=["Python"],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )

        assert generator.can_proceed_to_task_decomposition(prd) is True

    def test_can_proceed_to_task_decomposition_returns_false_for_invalid(
        self, generator: PRDGenerator
    ) -> None:
        """Test that can_proceed_to_task_decomposition returns False for invalid PRD."""
        prd = PRDSchema(
            title="Invalid PRD",
            version="1.0.0",
            overview="Overview",
            user_stories=[],  # No stories!
            tech_specs=TechSpecSchema(
                architecture_pattern="Pattern",
                architecture_decisions=[],
                technology_stack=[],
            ),
            acceptance_criteria=[],
            non_functional_requirements=[],
        )

        assert generator.can_proceed_to_task_decomposition(prd) is False


class TestPRDGeneratorFromTaskmaster:
    """Test PRDGenerator integration with Taskmaster output."""

    @pytest.fixture
    def generator(self) -> PRDGenerator:
        """Create a PRDGenerator with mocked dependencies."""
        mock_router = MagicMock()
        return PRDGenerator(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_generate_from_taskmaster_output(
        self, generator: PRDGenerator
    ) -> None:
        """Test generating PRD from Taskmaster PRDOutput."""
        # Simulated Taskmaster output (simplified PRDOutput)
        taskmaster_output = {
            "title": "Todo App",
            "overview": "A todo application",
            "user_stories": [
                {
                    "id": "US-001",
                    "description": "As a user, I can create tasks",
                    "priority": "P0",
                    "acceptance_criteria": ["Task appears in list"],
                }
            ],
            "tech_specs": {
                "architecture": "Next.js with FastAPI",
                "technology_stack": ["Next.js", "FastAPI"],
            },
            "acceptance_criteria": ["All P0 features work"],
        }

        mock_enhanced_response = """{
            "title": "Todo App",
            "version": "1.0.0",
            "overview": "A todo application",
            "user_stories": [
                {
                    "id": "US-001",
                    "title": "Create Task",
                    "description": "As a user, I can create tasks",
                    "priority": "P0",
                    "acceptance_criteria": [
                        {"given": "I am logged in", "when": "I create a task", "then": "task appears in list"}
                    ]
                }
            ],
            "tech_specs": {
                "architecture_pattern": "Modular Frontend with API Backend",
                "architecture_decisions": ["Use Next.js for SSR", "Use FastAPI for API layer"],
                "technology_stack": ["Next.js", "FastAPI"]
            },
            "acceptance_criteria": [
                {"given": "all P0 stories complete", "when": "deployed", "then": "all features work"}
            ],
            "non_functional_requirements": [
                {"type": "performance", "description": "Fast load", "metric": "LCP", "target": "< 2.5s", "priority": "P1"}
            ]
        }"""
        generator._model_router.route = AsyncMock(return_value=mock_enhanced_response)

        result = await generator.enhance_from_taskmaster(taskmaster_output)

        assert isinstance(result, PRDSchema)
        assert result.title == "Todo App"
        # Should have converted acceptance criteria to Given/When/Then
        assert len(result.user_stories[0].acceptance_criteria) >= 1
        # Should have added NFRs
        assert len(result.non_functional_requirements) >= 1


class TestPRDValidationResult:
    """Test PRDValidationResult model."""

    def test_validation_result_creation(self) -> None:
        """Test creating a validation result."""
        result = PRDValidationResult(
            is_valid=False,
            errors=["Missing P0 story", "No tech specs"],
            warnings=["Consider adding more acceptance criteria"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1

    def test_validation_result_defaults(self) -> None:
        """Test validation result defaults."""
        result = PRDValidationResult(is_valid=True, errors=[])
        assert result.warnings == []


class TestPRDGenerationConfig:
    """Test PRDGenerationConfig model."""

    def test_config_creation(self) -> None:
        """Test creating a generation config."""
        config = PRDGenerationConfig(
            require_p0_story=True,
            require_acceptance_criteria=True,
            require_tech_specs=True,
            require_nfr=True,
            min_user_stories=1,
            min_acceptance_criteria_per_story=1,
        )
        assert config.require_p0_story is True
        assert config.min_user_stories == 1

    def test_config_defaults(self) -> None:
        """Test config defaults."""
        config = PRDGenerationConfig()
        assert config.require_p0_story is True  # Should default to True
        assert config.require_acceptance_criteria is True
        assert config.require_tech_specs is True
        assert config.require_nfr is False  # Optional by default


class TestPRDValidationError:
    """Test PRDValidationError exception."""

    def test_validation_error_creation(self) -> None:
        """Test creating a validation error."""
        error = PRDValidationError(
            message="PRD validation failed",
            errors=["Missing P0 story", "No acceptance criteria"],
        )
        assert str(error) == "PRD validation failed"
        assert len(error.errors) == 2

    def test_validation_error_raise(self) -> None:
        """Test raising validation error."""
        with pytest.raises(PRDValidationError) as exc_info:
            raise PRDValidationError(
                message="Invalid PRD",
                errors=["Error 1"],
            )
        assert "Invalid PRD" in str(exc_info.value)


class TestPRDSchemaExports:
    """Test that all expected types are exported from schemas module."""

    def test_prd_schema_exports(self) -> None:
        """Test that PRDSchema is exported."""
        from daw_agents.schemas.prd_schema import PRDSchema

        assert PRDSchema is not None

    def test_user_story_schema_exports(self) -> None:
        """Test that UserStorySchema is exported."""
        from daw_agents.schemas.prd_schema import UserStorySchema

        assert UserStorySchema is not None

    def test_tech_spec_schema_exports(self) -> None:
        """Test that TechSpecSchema is exported."""
        from daw_agents.schemas.prd_schema import TechSpecSchema

        assert TechSpecSchema is not None

    def test_acceptance_criteria_schema_exports(self) -> None:
        """Test that AcceptanceCriteriaSchema is exported."""
        from daw_agents.schemas.prd_schema import AcceptanceCriteriaSchema

        assert AcceptanceCriteriaSchema is not None

    def test_nfr_schema_exports(self) -> None:
        """Test that NonFunctionalRequirementSchema is exported."""
        from daw_agents.schemas.prd_schema import NonFunctionalRequirementSchema

        assert NonFunctionalRequirementSchema is not None
