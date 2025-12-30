"""
Tests for Reflection Hook module.

This module tests the post-task learning reflection system for the DAW system,
implementing FR-07.2 (Proactive Reflection).

The Reflection Hook triggers after task completion to extract learnings,
store insights in Neo4j, and enable proactive self-improvement.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from daw_agents.evolution.reflection import (
    ReflectionConfig,
    ReflectionDepth,
    ReflectionHook,
    ReflectionInsight,
)
from daw_agents.evolution.schemas import (
    Experience,
    Insight,
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
    connector.create_node = AsyncMock(return_value="insight:12345")
    connector.create_relationship = AsyncMock(return_value="rel:12345")
    connector.query = AsyncMock(return_value=[])
    return connector


@pytest.fixture
def mock_experience_logger(mock_neo4j_connector: MagicMock) -> MagicMock:
    """Create a mock ExperienceLogger."""
    logger = MagicMock()
    logger.neo4j_connector = mock_neo4j_connector
    logger.add_insight = AsyncMock(return_value="insight:12345")
    logger.get_experience_by_id = AsyncMock(
        return_value=Experience(
            id="exp:123",
            task_id="CORE-001",
            task_type=TaskType.CODING,
            success=True,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
        )
    )
    return logger


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Create a mock ModelRouter."""
    router = MagicMock()
    router.route = AsyncMock(
        return_value="""
        {
            "what_worked": "Used async context managers for proper resource cleanup",
            "what_failed": null,
            "lessons_learned": ["Always use context managers for resources"],
            "patterns_detected": ["async-context-manager"],
            "suggestions": ["Consider adding timeout to cleanup operations"]
        }
        """
    )
    return router


@pytest.fixture
def reflection_config(
    mock_experience_logger: MagicMock,
    mock_model_router: MagicMock,
    mock_neo4j_connector: MagicMock,
) -> ReflectionConfig:
    """Create a ReflectionConfig for testing."""
    return ReflectionConfig(
        experience_logger=mock_experience_logger,
        model_router=mock_model_router,
        neo4j_connector=mock_neo4j_connector,
        depth=ReflectionDepth.STANDARD,
    )


@pytest.fixture
def reflection_hook(reflection_config: ReflectionConfig) -> ReflectionHook:
    """Create a ReflectionHook instance for testing."""
    return ReflectionHook(config=reflection_config)


@pytest.fixture
def sample_experience() -> Experience:
    """Create a sample experience for testing."""
    return Experience(
        id="exp:123",
        task_id="CORE-001",
        task_type=TaskType.CODING,
        success=True,
        prompt_version="executor_v1.2",
        model_used="claude-sonnet-4-20250514",
        tokens_used=5000,
        cost_usd=0.045,
        duration_ms=12500,
        retries=0,
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# ReflectionDepth Tests
# =============================================================================


class TestReflectionDepth:
    """Tests for ReflectionDepth enum."""

    def test_reflection_depth_quick(self) -> None:
        """Test QUICK depth value."""
        assert ReflectionDepth.QUICK.value == "quick"

    def test_reflection_depth_standard(self) -> None:
        """Test STANDARD depth value."""
        assert ReflectionDepth.STANDARD.value == "standard"

    def test_reflection_depth_deep(self) -> None:
        """Test DEEP depth value."""
        assert ReflectionDepth.DEEP.value == "deep"

    def test_all_depths_defined(self) -> None:
        """Test that all expected depths are defined."""
        depths = [d.value for d in ReflectionDepth]
        assert "quick" in depths
        assert "standard" in depths
        assert "deep" in depths
        assert len(depths) == 3


# =============================================================================
# ReflectionConfig Tests
# =============================================================================


class TestReflectionConfig:
    """Tests for ReflectionConfig Pydantic model."""

    def test_config_creation(
        self,
        mock_experience_logger: MagicMock,
        mock_model_router: MagicMock,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test creating a ReflectionConfig with all fields."""
        config = ReflectionConfig(
            experience_logger=mock_experience_logger,
            model_router=mock_model_router,
            neo4j_connector=mock_neo4j_connector,
            depth=ReflectionDepth.STANDARD,
        )
        assert config.depth == ReflectionDepth.STANDARD
        assert config.experience_logger is mock_experience_logger
        assert config.model_router is mock_model_router
        assert config.neo4j_connector is mock_neo4j_connector

    def test_config_default_depth(
        self,
        mock_experience_logger: MagicMock,
        mock_model_router: MagicMock,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that default depth is STANDARD."""
        config = ReflectionConfig(
            experience_logger=mock_experience_logger,
            model_router=mock_model_router,
            neo4j_connector=mock_neo4j_connector,
        )
        assert config.depth == ReflectionDepth.STANDARD

    def test_config_with_quick_depth(
        self,
        mock_experience_logger: MagicMock,
        mock_model_router: MagicMock,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test config with QUICK depth."""
        config = ReflectionConfig(
            experience_logger=mock_experience_logger,
            model_router=mock_model_router,
            neo4j_connector=mock_neo4j_connector,
            depth=ReflectionDepth.QUICK,
        )
        assert config.depth == ReflectionDepth.QUICK

    def test_config_with_deep_depth(
        self,
        mock_experience_logger: MagicMock,
        mock_model_router: MagicMock,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test config with DEEP depth."""
        config = ReflectionConfig(
            experience_logger=mock_experience_logger,
            model_router=mock_model_router,
            neo4j_connector=mock_neo4j_connector,
            depth=ReflectionDepth.DEEP,
        )
        assert config.depth == ReflectionDepth.DEEP


# =============================================================================
# ReflectionInsight Tests
# =============================================================================


class TestReflectionInsight:
    """Tests for ReflectionInsight Pydantic model."""

    def test_insight_creation(self) -> None:
        """Test creating a ReflectionInsight with all fields."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Used async context managers",
            what_failed=None,
            lessons_learned=["Always use context managers"],
            patterns_detected=["async-context-manager"],
            suggestions=["Add timeout to cleanup"],
        )
        assert insight.experience_id == "exp:123"
        assert insight.what_worked == "Used async context managers"
        assert insight.what_failed is None
        assert len(insight.lessons_learned) == 1
        assert len(insight.patterns_detected) == 1
        assert len(insight.suggestions) == 1

    def test_insight_creation_minimal(self) -> None:
        """Test creating a ReflectionInsight with minimal fields."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="It worked",
            lessons_learned=["A lesson"],
        )
        assert insight.experience_id == "exp:123"
        assert insight.what_failed is None
        assert insight.patterns_detected == []
        assert insight.suggestions == []

    def test_insight_with_failure(self) -> None:
        """Test creating a ReflectionInsight for a failed task."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Initial approach",
            what_failed="Timeout in cleanup",
            lessons_learned=["Set explicit timeouts"],
            patterns_detected=["timeout-pattern"],
            suggestions=["Use asyncio.wait_for"],
        )
        assert insight.what_failed == "Timeout in cleanup"

    def test_insight_to_legacy_insight(self) -> None:
        """Test converting ReflectionInsight to legacy Insight model."""
        reflection_insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Good patterns used",
            what_failed=None,
            lessons_learned=["Lesson 1", "Lesson 2"],
            patterns_detected=["pattern1"],
            suggestions=["Suggestion 1"],
        )
        legacy = reflection_insight.to_insight()
        assert isinstance(legacy, Insight)
        assert legacy.what_worked == "Good patterns used"
        assert "Lesson 1" in legacy.lesson_learned

    def test_insight_id_auto_generated(self) -> None:
        """Test that insight ID is auto-generated."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="It worked",
            lessons_learned=["A lesson"],
        )
        assert insight.id is not None
        assert len(insight.id) > 0

    def test_insight_created_at_auto_set(self) -> None:
        """Test that created_at timestamp is auto-set."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="It worked",
            lessons_learned=["A lesson"],
        )
        assert insight.created_at is not None


# =============================================================================
# ReflectionHook Initialization Tests
# =============================================================================


class TestReflectionHookInit:
    """Tests for ReflectionHook initialization."""

    def test_init_with_config(self, reflection_config: ReflectionConfig) -> None:
        """Test initializing ReflectionHook with a config."""
        hook = ReflectionHook(config=reflection_config)
        assert hook.config is reflection_config

    def test_init_requires_config(self) -> None:
        """Test that ReflectionHook requires a config."""
        with pytest.raises(TypeError):
            ReflectionHook()  # type: ignore[call-arg]

    def test_hook_has_config_attributes(
        self, reflection_hook: ReflectionHook
    ) -> None:
        """Test that hook exposes config attributes."""
        assert reflection_hook.experience_logger is not None
        assert reflection_hook.model_router is not None
        assert reflection_hook.neo4j_connector is not None


# =============================================================================
# ReflectionHook.reflect() Tests
# =============================================================================


class TestReflectionHookReflect:
    """Tests for ReflectionHook.reflect() method."""

    @pytest.mark.asyncio
    async def test_reflect_returns_insight(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
    ) -> None:
        """Test that reflect() returns a ReflectionInsight."""
        insight = await reflection_hook.reflect(sample_experience)
        assert isinstance(insight, ReflectionInsight)
        assert insight.experience_id == sample_experience.id

    @pytest.mark.asyncio
    async def test_reflect_calls_model_router(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_model_router: MagicMock,
    ) -> None:
        """Test that reflect() calls the model router."""
        await reflection_hook.reflect(sample_experience)
        mock_model_router.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_reflect_uses_fast_task_type(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_model_router: MagicMock,
    ) -> None:
        """Test that reflect() uses FAST task type for efficiency."""
        from daw_agents.models.router import TaskType as ModelTaskType

        await reflection_hook.reflect(sample_experience)
        call_args = mock_model_router.route.call_args
        assert call_args.kwargs.get("task_type") == ModelTaskType.FAST

    @pytest.mark.asyncio
    async def test_reflect_with_quick_depth(
        self,
        reflection_config: ReflectionConfig,
        sample_experience: Experience,
    ) -> None:
        """Test reflect with QUICK depth uses simpler prompt."""
        reflection_config.depth = ReflectionDepth.QUICK
        hook = ReflectionHook(config=reflection_config)
        insight = await hook.reflect(sample_experience)
        assert isinstance(insight, ReflectionInsight)

    @pytest.mark.asyncio
    async def test_reflect_with_deep_depth(
        self,
        reflection_config: ReflectionConfig,
        sample_experience: Experience,
    ) -> None:
        """Test reflect with DEEP depth uses comprehensive prompt."""
        reflection_config.depth = ReflectionDepth.DEEP
        hook = ReflectionHook(config=reflection_config)
        insight = await hook.reflect(sample_experience)
        assert isinstance(insight, ReflectionInsight)

    @pytest.mark.asyncio
    async def test_reflect_parses_model_response(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
    ) -> None:
        """Test that reflect() parses the model response correctly."""
        insight = await reflection_hook.reflect(sample_experience)
        assert insight.what_worked is not None
        assert len(insight.lessons_learned) > 0

    @pytest.mark.asyncio
    async def test_reflect_handles_parse_error(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_model_router: MagicMock,
    ) -> None:
        """Test that reflect() handles invalid model response gracefully."""
        mock_model_router.route.return_value = "invalid json response"
        insight = await reflection_hook.reflect(sample_experience)
        # Should return a basic insight with fallback values
        assert insight.experience_id == sample_experience.id
        assert insight.what_worked is not None

    @pytest.mark.asyncio
    async def test_reflect_on_failed_experience(
        self,
        reflection_hook: ReflectionHook,
    ) -> None:
        """Test reflecting on a failed experience."""
        failed_experience = Experience(
            id="exp:456",
            task_id="CORE-002",
            task_type=TaskType.VALIDATION,
            success=False,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=2000,
            cost_usd=0.02,
            duration_ms=10000,
            error_message="Test failed: AssertionError",
            error_type="AssertionError",
        )
        insight = await reflection_hook.reflect(failed_experience)
        assert insight.experience_id == failed_experience.id


# =============================================================================
# ReflectionHook.store_insight() Tests
# =============================================================================


class TestReflectionHookStoreInsight:
    """Tests for ReflectionHook.store_insight() method."""

    @pytest.mark.asyncio
    async def test_store_insight_creates_node(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that store_insight creates an Insight node in Neo4j."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Good approach",
            lessons_learned=["Lesson 1"],
        )
        insight_id = await reflection_hook.store_insight(insight)
        assert insight_id is not None
        mock_neo4j_connector.create_node.assert_called()

    @pytest.mark.asyncio
    async def test_store_insight_creates_relationship(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that store_insight creates REFLECTED_AS relationship."""
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Good approach",
            lessons_learned=["Lesson 1"],
        )
        await reflection_hook.store_insight(insight)
        mock_neo4j_connector.create_relationship.assert_called()
        call_args = mock_neo4j_connector.create_relationship.call_args
        assert call_args.kwargs.get("rel_type") == "REFLECTED_AS"

    @pytest.mark.asyncio
    async def test_store_insight_returns_insight_id(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that store_insight returns the created insight ID."""
        mock_neo4j_connector.create_node.return_value = "insight:new123"
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Good approach",
            lessons_learned=["Lesson 1"],
        )
        insight_id = await reflection_hook.store_insight(insight)
        assert insight_id == "insight:new123"


# =============================================================================
# ReflectionHook.get_related_insights() Tests
# =============================================================================


class TestReflectionHookGetRelatedInsights:
    """Tests for ReflectionHook.get_related_insights() method."""

    @pytest.mark.asyncio
    async def test_get_related_insights_returns_list(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that get_related_insights returns a list."""
        mock_neo4j_connector.query.return_value = []
        insights = await reflection_hook.get_related_insights("exp:123")
        assert isinstance(insights, list)

    @pytest.mark.asyncio
    async def test_get_related_insights_queries_neo4j(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that get_related_insights queries Neo4j."""
        mock_neo4j_connector.query.return_value = []
        await reflection_hook.get_related_insights("exp:123")
        mock_neo4j_connector.query.assert_called_once()
        cypher = mock_neo4j_connector.query.call_args[0][0]
        assert "REFLECTED_AS" in cypher

    @pytest.mark.asyncio
    async def test_get_related_insights_returns_insight_objects(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that get_related_insights returns ReflectionInsight objects."""
        mock_neo4j_connector.query.return_value = [
            {
                "i": {
                    "id": "insight:123",
                    "experience_id": "exp:123",
                    "what_worked": "Good approach",
                    "what_failed": None,
                    "lessons_learned": '["Lesson 1"]',
                    "patterns_detected": "[]",
                    "suggestions": "[]",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            }
        ]
        insights = await reflection_hook.get_related_insights("exp:123")
        assert len(insights) == 1
        assert isinstance(insights[0], ReflectionInsight)


# =============================================================================
# ReflectionHook Async Execution Tests
# =============================================================================


class TestReflectionHookAsync:
    """Tests for ReflectionHook async behavior."""

    @pytest.mark.asyncio
    async def test_reflect_is_async(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
    ) -> None:
        """Test that reflect() is properly async."""
        result = reflection_hook.reflect(sample_experience)
        # Should return a coroutine
        assert asyncio.iscoroutine(result)
        await result

    @pytest.mark.asyncio
    async def test_reflect_and_store_async(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
    ) -> None:
        """Test that reflect_and_store runs async."""
        insight_id = await reflection_hook.reflect_and_store(sample_experience)
        assert insight_id is not None

    @pytest.mark.asyncio
    async def test_reflect_and_store_stores_result(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that reflect_and_store stores the reflection result."""
        await reflection_hook.reflect_and_store(sample_experience)
        mock_neo4j_connector.create_node.assert_called()

    @pytest.mark.asyncio
    async def test_non_blocking_execution(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
    ) -> None:
        """Test that reflection can run without blocking main workflow."""
        # Create a task for reflection
        task = asyncio.create_task(
            reflection_hook.reflect_and_store(sample_experience)
        )

        # Main workflow can continue
        other_result = await asyncio.sleep(0, result="main_workflow_done")
        assert other_result == "main_workflow_done"

        # Wait for reflection to complete
        insight_id = await task
        assert insight_id is not None


# =============================================================================
# ReflectionHook LangGraph Integration Tests
# =============================================================================


class TestReflectionHookLangGraphIntegration:
    """Tests for ReflectionHook as LangGraph callback."""

    def test_hook_has_on_task_complete(
        self, reflection_hook: ReflectionHook
    ) -> None:
        """Test that hook has on_task_complete callback method."""
        assert hasattr(reflection_hook, "on_task_complete")
        assert callable(reflection_hook.on_task_complete)

    @pytest.mark.asyncio
    async def test_on_task_complete_triggers_reflection(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_model_router: MagicMock,
    ) -> None:
        """Test that on_task_complete triggers reflection."""
        await reflection_hook.on_task_complete(
            experience_id=sample_experience.id,
            task_id=sample_experience.task_id,
            success=sample_experience.success,
        )
        # Should trigger model router for reflection
        mock_model_router.route.assert_called()

    @pytest.mark.asyncio
    async def test_on_task_complete_with_experience_object(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
    ) -> None:
        """Test on_task_complete with Experience object directly."""
        result = await reflection_hook.on_task_complete(
            experience=sample_experience
        )
        assert result is not None


# =============================================================================
# ReflectionHook DriftDetector Integration Tests
# =============================================================================


class TestReflectionHookDriftIntegration:
    """Tests for ReflectionHook integration with DriftDetector."""

    @pytest.mark.asyncio
    async def test_reflect_includes_drift_analysis(
        self,
        reflection_config: ReflectionConfig,
        sample_experience: Experience,
    ) -> None:
        """Test that deep reflection includes drift analysis."""
        reflection_config.depth = ReflectionDepth.DEEP
        hook = ReflectionHook(config=reflection_config)
        insight = await hook.reflect(sample_experience)
        # Deep reflection should analyze performance patterns
        assert insight is not None

    @pytest.mark.asyncio
    async def test_reflect_with_drift_metrics(
        self,
        reflection_hook: ReflectionHook,
    ) -> None:
        """Test reflecting with task that has drift metrics."""
        experience_with_metrics = Experience(
            id="exp:789",
            task_id="CORE-003",
            task_type=TaskType.CODING,
            success=True,
            prompt_version="v1.0",
            model_used="gpt-4o",
            tokens_used=10000,  # High token usage
            cost_usd=0.10,
            duration_ms=30000,  # Long duration
            retries=2,  # Some retries
        )
        insight = await reflection_hook.reflect(experience_with_metrics)
        assert insight.experience_id == experience_with_metrics.id


# =============================================================================
# Prompt Generation Tests
# =============================================================================


class TestPromptGeneration:
    """Tests for reflection prompt generation."""

    def test_get_prompt_for_quick_depth(
        self, reflection_hook: ReflectionHook
    ) -> None:
        """Test prompt generation for QUICK depth."""
        prompt = reflection_hook._get_prompt(
            depth=ReflectionDepth.QUICK,
            experience=Experience(
                task_id="TEST-001",
                task_type=TaskType.CODING,
                success=True,
                prompt_version="v1.0",
                model_used="gpt-4o",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            ),
        )
        assert prompt is not None
        assert len(prompt) > 0

    def test_get_prompt_for_standard_depth(
        self, reflection_hook: ReflectionHook
    ) -> None:
        """Test prompt generation for STANDARD depth."""
        prompt = reflection_hook._get_prompt(
            depth=ReflectionDepth.STANDARD,
            experience=Experience(
                task_id="TEST-001",
                task_type=TaskType.CODING,
                success=True,
                prompt_version="v1.0",
                model_used="gpt-4o",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            ),
        )
        assert prompt is not None
        # Standard should be more detailed than quick
        quick_prompt = reflection_hook._get_prompt(
            depth=ReflectionDepth.QUICK,
            experience=Experience(
                task_id="TEST-001",
                task_type=TaskType.CODING,
                success=True,
                prompt_version="v1.0",
                model_used="gpt-4o",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            ),
        )
        assert len(prompt) >= len(quick_prompt)

    def test_get_prompt_for_deep_depth(
        self, reflection_hook: ReflectionHook
    ) -> None:
        """Test prompt generation for DEEP depth."""
        prompt = reflection_hook._get_prompt(
            depth=ReflectionDepth.DEEP,
            experience=Experience(
                task_id="TEST-001",
                task_type=TaskType.CODING,
                success=True,
                prompt_version="v1.0",
                model_used="gpt-4o",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            ),
        )
        assert prompt is not None
        # Deep should include more analysis areas

    def test_prompt_includes_experience_context(
        self, reflection_hook: ReflectionHook
    ) -> None:
        """Test that prompt includes experience context."""
        experience = Experience(
            task_id="TASK-XYZ",
            task_type=TaskType.VALIDATION,
            success=False,
            prompt_version="validator_v2.0",
            model_used="claude-sonnet-4-20250514",
            tokens_used=2500,
            cost_usd=0.025,
            duration_ms=8000,
            error_message="Validation failed",
        )
        prompt = reflection_hook._get_prompt(
            depth=ReflectionDepth.STANDARD,
            experience=experience,
        )
        # Prompt should reference task context
        assert "TASK-XYZ" in prompt or "validation" in prompt.lower()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in ReflectionHook."""

    @pytest.mark.asyncio
    async def test_reflect_handles_model_error(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_model_router: MagicMock,
    ) -> None:
        """Test that reflect handles model errors gracefully."""
        mock_model_router.route.side_effect = Exception("Model unavailable")
        # Should not raise, but return a minimal insight
        insight = await reflection_hook.reflect(sample_experience)
        assert insight is not None
        assert insight.experience_id == sample_experience.id

    @pytest.mark.asyncio
    async def test_store_insight_handles_neo4j_error(
        self,
        reflection_hook: ReflectionHook,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test that store_insight propagates Neo4j errors."""
        from neo4j.exceptions import Neo4jError

        mock_neo4j_connector.create_node.side_effect = Neo4jError(
            "Connection failed"
        )
        insight = ReflectionInsight(
            experience_id="exp:123",
            what_worked="Test",
            lessons_learned=["Lesson"],
        )
        with pytest.raises(Neo4jError):
            await reflection_hook.store_insight(insight)

    @pytest.mark.asyncio
    async def test_reflect_and_store_handles_partial_failure(
        self,
        reflection_hook: ReflectionHook,
        sample_experience: Experience,
        mock_neo4j_connector: MagicMock,
    ) -> None:
        """Test handling when reflection succeeds but storage fails."""
        from neo4j.exceptions import Neo4jError

        mock_neo4j_connector.create_node.side_effect = Neo4jError(
            "Storage failed"
        )
        # reflect_and_store should propagate the storage error
        with pytest.raises(Neo4jError):
            await reflection_hook.reflect_and_store(sample_experience)
