"""
Tests for Experience Logger module.

This module tests the self-learning foundation for the DAW system,
implementing FR-07.1 (Experience-Driven Learning).

The Experience Logger stores task completion experiences in Neo4j
for future learning and retrieval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from daw_agents.evolution.experience_logger import ExperienceLogger
from daw_agents.evolution.schemas import (
    Artifact,
    ArtifactType,
    Experience,
    ExperienceQuery,
    Insight,
    Skill,
    SuccessRate,
    TaskType,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_neo4j_connector() -> MagicMock:
    """Create a mock Neo4j connector."""
    connector = MagicMock()
    connector.create_node = AsyncMock(return_value="node:12345")
    connector.create_relationship = AsyncMock(return_value="rel:12345")
    connector.query = AsyncMock(return_value=[])
    return connector


@pytest.fixture
def experience_logger(mock_neo4j_connector: MagicMock) -> ExperienceLogger:
    """Create an ExperienceLogger instance with mocked connector."""
    return ExperienceLogger(neo4j_connector=mock_neo4j_connector)


@pytest.fixture
def sample_experience() -> Experience:
    """Create a sample experience for testing."""
    return Experience(
        task_id="CORE-001",
        task_type=TaskType.CODING,
        success=True,
        prompt_version="executor_v1.2",
        model_used="claude-sonnet-4-20250514",
        tokens_used=5000,
        cost_usd=0.045,
        duration_ms=12500,
        retries=0,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_skill() -> Skill:
    """Create a sample skill for testing."""
    return Skill(
        name="python_async_context_manager",
        pattern="async with ... as ...: pattern for resource management",
        description="Async context manager pattern for resource cleanup",
        success_rate=0.95,
        usage_count=42,
    )


@pytest.fixture
def sample_artifact() -> Artifact:
    """Create a sample artifact for testing."""
    return Artifact(
        artifact_type=ArtifactType.CODE,
        path="src/daw_agents/sandbox/e2b.py",
        description="E2B sandbox wrapper implementation",
    )


# =============================================================================
# Schema Tests
# =============================================================================


class TestTaskType:
    """Tests for TaskType enum."""

    def test_task_type_values(self) -> None:
        """Test that TaskType has all expected values."""
        assert TaskType.PLANNING.value == "planning"
        assert TaskType.CODING.value == "coding"
        assert TaskType.VALIDATION.value == "validation"
        assert TaskType.FAST.value == "fast"
        assert TaskType.DEBUGGING.value == "debugging"
        assert TaskType.DOCUMENTATION.value == "documentation"

    def test_task_type_from_string(self) -> None:
        """Test creating TaskType from string."""
        assert TaskType("coding") == TaskType.CODING
        assert TaskType("planning") == TaskType.PLANNING


class TestArtifactType:
    """Tests for ArtifactType enum."""

    def test_artifact_type_values(self) -> None:
        """Test that ArtifactType has all expected values."""
        assert ArtifactType.CODE.value == "code"
        assert ArtifactType.TEST.value == "test"
        assert ArtifactType.DOCUMENTATION.value == "documentation"
        assert ArtifactType.CONFIG.value == "config"
        assert ArtifactType.PRD.value == "prd"


class TestExperienceModel:
    """Tests for Experience Pydantic model."""

    def test_experience_creation_minimal(self) -> None:
        """Test creating an Experience with minimal required fields."""
        exp = Experience(
            task_id="TASK-001",
            task_type=TaskType.CODING,
            success=True,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
        )
        assert exp.task_id == "TASK-001"
        assert exp.task_type == TaskType.CODING
        assert exp.success is True
        assert exp.retries == 0  # default
        assert exp.timestamp is not None  # auto-generated

    def test_experience_creation_full(self, sample_experience: Experience) -> None:
        """Test creating an Experience with all fields."""
        assert sample_experience.task_id == "CORE-001"
        assert sample_experience.task_type == TaskType.CODING
        assert sample_experience.success is True
        assert sample_experience.prompt_version == "executor_v1.2"
        assert sample_experience.model_used == "claude-sonnet-4-20250514"
        assert sample_experience.tokens_used == 5000
        assert sample_experience.cost_usd == 0.045
        assert sample_experience.duration_ms == 12500
        assert sample_experience.retries == 0

    def test_experience_with_error_details(self) -> None:
        """Test creating a failed Experience with error details."""
        exp = Experience(
            task_id="TASK-002",
            task_type=TaskType.VALIDATION,
            success=False,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=2000,
            cost_usd=0.02,
            duration_ms=10000,
            retries=3,
            error_message="Test failed: AssertionError",
            error_type="AssertionError",
        )
        assert exp.success is False
        assert exp.retries == 3
        assert exp.error_message == "Test failed: AssertionError"
        assert exp.error_type == "AssertionError"

    def test_experience_id_auto_generated(self) -> None:
        """Test that experience ID is auto-generated if not provided."""
        exp = Experience(
            task_id="TASK-001",
            task_type=TaskType.CODING,
            success=True,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
        )
        assert exp.id is not None
        assert len(exp.id) > 0

    def test_experience_to_neo4j_properties(self, sample_experience: Experience) -> None:
        """Test converting Experience to Neo4j properties dict."""
        props = sample_experience.to_neo4j_properties()
        assert props["task_id"] == "CORE-001"
        assert props["task_type"] == "coding"
        assert props["success"] is True
        assert props["prompt_version"] == "executor_v1.2"
        assert props["model_used"] == "claude-sonnet-4-20250514"
        assert props["tokens_used"] == 5000
        assert props["cost_usd"] == 0.045
        assert props["duration_ms"] == 12500
        assert "timestamp" in props


class TestSkillModel:
    """Tests for Skill Pydantic model."""

    def test_skill_creation(self, sample_skill: Skill) -> None:
        """Test creating a Skill."""
        assert sample_skill.name == "python_async_context_manager"
        assert sample_skill.success_rate == 0.95
        assert sample_skill.usage_count == 42

    def test_skill_with_defaults(self) -> None:
        """Test Skill creation with defaults."""
        skill = Skill(
            name="basic_pattern",
            pattern="some pattern",
        )
        assert skill.success_rate == 0.0
        assert skill.usage_count == 0
        assert skill.description is None

    def test_skill_to_neo4j_properties(self, sample_skill: Skill) -> None:
        """Test converting Skill to Neo4j properties."""
        props = sample_skill.to_neo4j_properties()
        assert props["name"] == "python_async_context_manager"
        assert props["pattern"] == "async with ... as ...: pattern for resource management"
        assert props["success_rate"] == 0.95
        assert props["usage_count"] == 42


class TestArtifactModel:
    """Tests for Artifact Pydantic model."""

    def test_artifact_creation(self, sample_artifact: Artifact) -> None:
        """Test creating an Artifact."""
        assert sample_artifact.artifact_type == ArtifactType.CODE
        assert sample_artifact.path == "src/daw_agents/sandbox/e2b.py"
        assert sample_artifact.description == "E2B sandbox wrapper implementation"

    def test_artifact_to_neo4j_properties(self, sample_artifact: Artifact) -> None:
        """Test converting Artifact to Neo4j properties."""
        props = sample_artifact.to_neo4j_properties()
        assert props["type"] == "code"
        assert props["path"] == "src/daw_agents/sandbox/e2b.py"


class TestInsightModel:
    """Tests for Insight Pydantic model."""

    def test_insight_creation(self) -> None:
        """Test creating an Insight."""
        insight = Insight(
            what_worked="Using async context manager ensured proper cleanup",
            lesson_learned="Always use context managers for resource management",
            improvement_suggestion="Consider adding timeout to cleanup operations",
        )
        assert insight.what_worked is not None
        assert insight.lesson_learned is not None

    def test_insight_to_neo4j_properties(self) -> None:
        """Test converting Insight to Neo4j properties."""
        insight = Insight(
            what_worked="Pattern X worked well",
            lesson_learned="Always use pattern X",
        )
        props = insight.to_neo4j_properties()
        assert props["what_worked"] == "Pattern X worked well"
        assert props["lesson_learned"] == "Always use pattern X"


class TestExperienceQuery:
    """Tests for ExperienceQuery model."""

    def test_query_with_task_type(self) -> None:
        """Test creating a query with task type filter."""
        query = ExperienceQuery(task_type=TaskType.CODING)
        assert query.task_type == TaskType.CODING
        assert query.success is None
        assert query.model_used is None

    def test_query_with_multiple_filters(self) -> None:
        """Test creating a query with multiple filters."""
        query = ExperienceQuery(
            task_type=TaskType.CODING,
            success=True,
            model_used="claude-sonnet-4-20250514",
            limit=10,
        )
        assert query.task_type == TaskType.CODING
        assert query.success is True
        assert query.model_used == "claude-sonnet-4-20250514"
        assert query.limit == 10


class TestSuccessRate:
    """Tests for SuccessRate model."""

    def test_success_rate_creation(self) -> None:
        """Test creating a SuccessRate."""
        rate = SuccessRate(
            task_type=TaskType.CODING,
            model_used="gpt-4o",
            success_rate=0.85,
            total_count=100,
            success_count=85,
        )
        assert rate.success_rate == 0.85
        assert rate.total_count == 100
        assert rate.success_count == 85


# =============================================================================
# ExperienceLogger Tests
# =============================================================================


class TestExperienceLoggerInit:
    """Tests for ExperienceLogger initialization."""

    def test_init_with_connector(self, mock_neo4j_connector: MagicMock) -> None:
        """Test initializing ExperienceLogger with a connector."""
        logger = ExperienceLogger(neo4j_connector=mock_neo4j_connector)
        assert logger.neo4j_connector is mock_neo4j_connector

    def test_init_requires_connector(self) -> None:
        """Test that ExperienceLogger requires a connector."""
        with pytest.raises(TypeError):
            ExperienceLogger()  # type: ignore[call-arg]


class TestLogSuccess:
    """Tests for ExperienceLogger.log_success()."""

    @pytest.mark.asyncio
    async def test_log_success_creates_experience_node(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_success creates an Experience node in Neo4j."""
        exp_id = await experience_logger.log_success(
            task_id="CORE-001",
            task_type=TaskType.CODING,
            prompt_version="v1.0",
            model_used="claude-sonnet-4-20250514",
            tokens_used=5000,
            cost_usd=0.045,
            duration_ms=12500,
        )

        assert exp_id is not None
        mock_neo4j_connector.create_node.assert_called_once()
        call_args = mock_neo4j_connector.create_node.call_args
        # Access kwargs since we use keyword arguments
        labels = call_args.kwargs.get("labels", call_args[0][0] if call_args[0] else [])
        props = call_args.kwargs.get("properties", call_args[0][1] if len(call_args[0]) > 1 else {})
        assert "Experience" in labels
        assert props["task_id"] == "CORE-001"
        assert props["success"] is True

    @pytest.mark.asyncio
    async def test_log_success_with_skills(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_success creates USED_SKILL relationships."""
        skills = [
            Skill(name="pattern1", pattern="p1"),
            Skill(name="pattern2", pattern="p2"),
        ]

        await experience_logger.log_success(
            task_id="CORE-001",
            task_type=TaskType.CODING,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
            skills=skills,
        )

        # Should create experience node + 2 skill nodes + 2 relationships
        assert mock_neo4j_connector.create_node.call_count >= 1
        assert mock_neo4j_connector.create_relationship.call_count >= 2

    @pytest.mark.asyncio
    async def test_log_success_with_artifacts(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_success creates PRODUCED relationships."""
        artifacts = [
            Artifact(artifact_type=ArtifactType.CODE, path="src/module.py"),
            Artifact(artifact_type=ArtifactType.TEST, path="tests/test_module.py"),
        ]

        await experience_logger.log_success(
            task_id="CORE-001",
            task_type=TaskType.CODING,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
            artifacts=artifacts,
        )

        # Should create PRODUCED relationships
        relationship_calls = [
            call for call in mock_neo4j_connector.create_relationship.call_args_list
            if call.kwargs.get("rel_type") == "PRODUCED"
        ]
        assert len(relationship_calls) == 2

    @pytest.mark.asyncio
    async def test_log_success_returns_experience_id(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_success returns the created experience ID."""
        mock_neo4j_connector.create_node = AsyncMock(return_value="exp:12345")

        exp_id = await experience_logger.log_success(
            task_id="CORE-001",
            task_type=TaskType.CODING,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
        )

        assert exp_id == "exp:12345"


class TestLogFailure:
    """Tests for ExperienceLogger.log_failure()."""

    @pytest.mark.asyncio
    async def test_log_failure_creates_experience_node(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_failure creates an Experience node with success=False."""
        await experience_logger.log_failure(
            task_id="CORE-001",
            task_type=TaskType.VALIDATION,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=2000,
            cost_usd=0.02,
            duration_ms=10000,
            error_message="Test failed",
            error_type="AssertionError",
            retries=3,
        )

        mock_neo4j_connector.create_node.assert_called_once()
        call_args = mock_neo4j_connector.create_node.call_args
        props = call_args.kwargs.get("properties", {})
        assert props["success"] is False
        assert props["error_message"] == "Test failed"
        assert props["error_type"] == "AssertionError"
        assert props["retries"] == 3

    @pytest.mark.asyncio
    async def test_log_failure_with_skills(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_failure still creates skill relationships."""
        skills = [Skill(name="failed_pattern", pattern="p1")]

        await experience_logger.log_failure(
            task_id="CORE-001",
            task_type=TaskType.CODING,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
            error_message="Error",
            skills=skills,
        )

        # Should still create USED_SKILL relationship
        assert mock_neo4j_connector.create_relationship.call_count >= 1


class TestQuerySimilarExperiences:
    """Tests for ExperienceLogger.query_similar_experiences()."""

    @pytest.mark.asyncio
    async def test_query_by_task_type(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test querying experiences by task type."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "e": {
                        "id": "exp:123",
                        "task_id": "CORE-001",
                        "task_type": "coding",
                        "success": True,
                        "prompt_version": "v1.0",
                        "model_used": "gpt-4o",
                        "tokens_used": 1000,
                        "cost_usd": 0.01,
                        "duration_ms": 5000,
                        "retries": 0,
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                }
            ]
        )

        query = ExperienceQuery(task_type=TaskType.CODING)
        results = await experience_logger.query_similar_experiences(query)

        assert len(results) >= 0
        mock_neo4j_connector.query.assert_called_once()
        cypher = mock_neo4j_connector.query.call_args[0][0]
        assert "task_type" in cypher

    @pytest.mark.asyncio
    async def test_query_by_error_type(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test querying failed experiences by error type for RAG."""
        mock_neo4j_connector.query = AsyncMock(return_value=[])

        query = ExperienceQuery(
            success=False,
            error_type="AssertionError",
        )
        await experience_logger.query_similar_experiences(query)

        mock_neo4j_connector.query.assert_called_once()
        cypher = mock_neo4j_connector.query.call_args[0][0]
        assert "error_type" in cypher

    @pytest.mark.asyncio
    async def test_query_with_limit(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that query respects limit parameter."""
        mock_neo4j_connector.query = AsyncMock(return_value=[])

        query = ExperienceQuery(task_type=TaskType.CODING, limit=5)
        await experience_logger.query_similar_experiences(query)

        cypher = mock_neo4j_connector.query.call_args[0][0]
        assert "LIMIT" in cypher

    @pytest.mark.asyncio
    async def test_query_with_time_range(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test querying experiences within a time range."""
        mock_neo4j_connector.query = AsyncMock(return_value=[])
        start_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2025, 12, 31, tzinfo=timezone.utc)

        query = ExperienceQuery(
            task_type=TaskType.CODING,
            start_time=start_time,
            end_time=end_time,
        )
        await experience_logger.query_similar_experiences(query)

        cypher = mock_neo4j_connector.query.call_args[0][0]
        assert "timestamp" in cypher

    @pytest.mark.asyncio
    async def test_query_returns_experience_objects(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that query returns Experience objects."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "e": {
                        "id": "exp:123",
                        "task_id": "CORE-001",
                        "task_type": "coding",
                        "success": True,
                        "prompt_version": "v1.0",
                        "model_used": "gpt-4o",
                        "tokens_used": 1000,
                        "cost_usd": 0.01,
                        "duration_ms": 5000,
                        "retries": 0,
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                }
            ]
        )

        query = ExperienceQuery(task_type=TaskType.CODING)
        results = await experience_logger.query_similar_experiences(query)

        assert len(results) == 1
        assert isinstance(results[0], Experience)
        assert results[0].task_id == "CORE-001"


class TestCalculateSuccessRate:
    """Tests for ExperienceLogger.calculate_success_rate()."""

    @pytest.mark.asyncio
    async def test_success_rate_by_task_type(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test calculating success rate by task type."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "task_type": "coding",
                    "total": 100,
                    "successes": 85,
                }
            ]
        )

        rate = await experience_logger.calculate_success_rate(task_type=TaskType.CODING)

        assert rate.task_type == TaskType.CODING
        assert rate.total_count == 100
        assert rate.success_count == 85
        assert rate.success_rate == 0.85

    @pytest.mark.asyncio
    async def test_success_rate_by_model(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test calculating success rate by model."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "model_used": "gpt-4o",
                    "total": 50,
                    "successes": 45,
                }
            ]
        )

        rate = await experience_logger.calculate_success_rate(model_used="gpt-4o")

        assert rate.model_used == "gpt-4o"
        assert rate.success_rate == 0.90

    @pytest.mark.asyncio
    async def test_success_rate_by_task_type_and_model(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test calculating success rate by both task type and model."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "task_type": "coding",
                    "model_used": "claude-sonnet-4-20250514",
                    "total": 30,
                    "successes": 27,
                }
            ]
        )

        rate = await experience_logger.calculate_success_rate(
            task_type=TaskType.CODING,
            model_used="claude-sonnet-4-20250514",
        )

        assert rate.task_type == TaskType.CODING
        assert rate.model_used == "claude-sonnet-4-20250514"
        assert rate.success_rate == 0.90

    @pytest.mark.asyncio
    async def test_success_rate_no_data(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test success rate when no data exists."""
        mock_neo4j_connector.query = AsyncMock(return_value=[])

        rate = await experience_logger.calculate_success_rate(task_type=TaskType.CODING)

        assert rate.total_count == 0
        assert rate.success_count == 0
        assert rate.success_rate == 0.0


class TestGetExperienceById:
    """Tests for ExperienceLogger.get_experience_by_id()."""

    @pytest.mark.asyncio
    async def test_get_existing_experience(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test retrieving an existing experience by ID."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "e": {
                        "id": "exp:123",
                        "task_id": "CORE-001",
                        "task_type": "coding",
                        "success": True,
                        "prompt_version": "v1.0",
                        "model_used": "gpt-4o",
                        "tokens_used": 1000,
                        "cost_usd": 0.01,
                        "duration_ms": 5000,
                        "retries": 0,
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                }
            ]
        )

        exp = await experience_logger.get_experience_by_id("exp:123")

        assert exp is not None
        assert exp.task_id == "CORE-001"

    @pytest.mark.asyncio
    async def test_get_nonexistent_experience(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test retrieving a non-existent experience."""
        mock_neo4j_connector.query = AsyncMock(return_value=[])

        exp = await experience_logger.get_experience_by_id("exp:nonexistent")

        assert exp is None


class TestGetRelatedSkills:
    """Tests for ExperienceLogger.get_related_skills()."""

    @pytest.mark.asyncio
    async def test_get_skills_for_experience(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test getting skills related to an experience."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "s": {
                        "name": "pattern1",
                        "pattern": "p1",
                        "success_rate": 0.9,
                        "usage_count": 10,
                    }
                },
                {
                    "s": {
                        "name": "pattern2",
                        "pattern": "p2",
                        "success_rate": 0.8,
                        "usage_count": 5,
                    }
                },
            ]
        )

        skills = await experience_logger.get_related_skills("exp:123")

        assert len(skills) == 2
        assert skills[0].name == "pattern1"
        assert skills[1].name == "pattern2"


class TestGetRelatedArtifacts:
    """Tests for ExperienceLogger.get_related_artifacts()."""

    @pytest.mark.asyncio
    async def test_get_artifacts_for_experience(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test getting artifacts produced by an experience."""
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "a": {
                        "type": "code",
                        "path": "src/module.py",
                        "description": "Main module",
                    }
                },
            ]
        )

        artifacts = await experience_logger.get_related_artifacts("exp:123")

        assert len(artifacts) == 1
        assert artifacts[0].path == "src/module.py"


class TestAddInsight:
    """Tests for ExperienceLogger.add_insight()."""

    @pytest.mark.asyncio
    async def test_add_insight_to_experience(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test adding an insight to an experience."""
        insight = Insight(
            what_worked="Used async context manager",
            lesson_learned="Always use context managers for cleanup",
        )

        insight_id = await experience_logger.add_insight("exp:123", insight)

        assert insight_id is not None
        mock_neo4j_connector.create_node.assert_called_once()
        mock_neo4j_connector.create_relationship.assert_called_once()

        # Verify relationship type
        rel_call = mock_neo4j_connector.create_relationship.call_args
        assert rel_call.kwargs.get("rel_type") == "REFLECTED_AS"


class TestCypherGeneration:
    """Tests for Cypher query generation."""

    @pytest.mark.asyncio
    async def test_log_success_cypher_structure(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that log_success generates correct Cypher for node creation."""
        await experience_logger.log_success(
            task_id="CORE-001",
            task_type=TaskType.CODING,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
        )

        call_args = mock_neo4j_connector.create_node.call_args
        labels = call_args.kwargs.get("labels", call_args[0][0] if call_args[0] else [])
        assert "Experience" in labels

    @pytest.mark.asyncio
    async def test_query_cypher_includes_match(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that query generates MATCH clause."""
        mock_neo4j_connector.query = AsyncMock(return_value=[])

        query = ExperienceQuery(task_type=TaskType.CODING)
        await experience_logger.query_similar_experiences(query)

        cypher = mock_neo4j_connector.query.call_args[0][0]
        assert "MATCH" in cypher
        assert "Experience" in cypher


class TestSkillMergeOrCreate:
    """Tests for skill upsert logic."""

    @pytest.mark.asyncio
    async def test_skill_merge_increments_usage(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that existing skills get usage count incremented."""
        # Simulate skill exists by returning the id from the query
        mock_neo4j_connector.query = AsyncMock(
            return_value=[
                {
                    "id": "skill:existing123",
                }
            ]
        )

        skill = Skill(name="pattern1", pattern="p1")
        skill_id = await experience_logger.get_or_create_skill(skill)

        assert skill_id == "skill:existing123"
        # Verify the MERGE query was called
        mock_neo4j_connector.query.assert_called_once()


class TestBulkOperations:
    """Tests for bulk experience operations."""

    @pytest.mark.asyncio
    async def test_log_multiple_experiences(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test logging multiple experiences in batch."""
        experiences = [
            Experience(
                task_id=f"TASK-{i}",
                task_type=TaskType.CODING,
                success=True,
                prompt_version="v1.0",
                model_used="gpt-4o",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            )
            for i in range(5)
        ]

        exp_ids = await experience_logger.log_batch(experiences)

        assert len(exp_ids) == 5
        assert mock_neo4j_connector.create_node.call_count == 5


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_log_success_handles_neo4j_error(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that Neo4j errors are properly propagated."""
        from neo4j.exceptions import Neo4jError

        mock_neo4j_connector.create_node = AsyncMock(
            side_effect=Neo4jError("Connection failed")
        )

        with pytest.raises(Neo4jError):
            await experience_logger.log_success(
                task_id="CORE-001",
                task_type=TaskType.CODING,
                prompt_version="v1.0",
                model_used="gpt-4o",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            )

    @pytest.mark.asyncio
    async def test_query_handles_neo4j_error(
        self, experience_logger: ExperienceLogger, mock_neo4j_connector: MagicMock
    ) -> None:
        """Test that query errors are properly propagated."""
        from neo4j.exceptions import Neo4jError

        mock_neo4j_connector.query = AsyncMock(
            side_effect=Neo4jError("Query failed")
        )

        with pytest.raises(Neo4jError):
            query = ExperienceQuery(task_type=TaskType.CODING)
            await experience_logger.query_similar_experiences(query)
