"""
Reflection Hook for post-task learning.

This module provides the ReflectionHook class that triggers after task completion
to extract learnings and store them in Neo4j for future reference.

Implements FR-07.2: Proactive Reflection Pattern

The Reflection Hook transforms reactive Monitor-Diagnose-Heal into proactive
reflection by analyzing both successful and failed tasks to extract insights.

Features:
- ReflectionDepth enum for configurable reflection depth (QUICK, STANDARD, DEEP)
- ReflectionConfig for hook configuration
- ReflectionInsight model for extracted learnings
- ReflectionHook class as LangGraph callback
- Async execution to avoid blocking main workflow

Neo4j Schema Extension:
(:Experience)-[:REFLECTED_AS]->(:Insight {what_worked, lessons_learned, patterns})
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from daw_agents.evolution.schemas import Experience, Insight

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ReflectionDepth(str, Enum):
    """Depth levels for reflection analysis.

    - QUICK: ~100ms, basic success/failure analysis
    - STANDARD: ~3s, pattern extraction and lessons
    - DEEP: ~15s, comprehensive learning extraction with drift analysis
    """

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ReflectionConfig(BaseModel):
    """Configuration for ReflectionHook.

    Attributes:
        experience_logger: Logger for storing experiences.
        model_router: Router for LLM calls.
        neo4j_connector: Connector for Neo4j operations.
        depth: Depth of reflection analysis.
    """

    experience_logger: Any = Field(..., description="ExperienceLogger instance")
    model_router: Any = Field(..., description="ModelRouter instance")
    neo4j_connector: Any = Field(..., description="Neo4jConnector instance")
    depth: ReflectionDepth = Field(
        default=ReflectionDepth.STANDARD,
        description="Depth of reflection analysis",
    )

    model_config = {"arbitrary_types_allowed": True}


class ReflectionInsight(BaseModel):
    """Model for extracted reflection insights.

    Captures what worked, what failed, lessons learned, detected patterns,
    and suggestions for improvement.

    Attributes:
        id: Unique identifier for the insight.
        experience_id: ID of the experience this insight is for.
        what_worked: Description of what worked well.
        what_failed: Description of what failed (if applicable).
        lessons_learned: List of lessons learned from the experience.
        patterns_detected: List of detected code/workflow patterns.
        suggestions: List of suggestions for improvement.
        created_at: Timestamp when the insight was created.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experience_id: str = Field(..., description="ID of the related experience")
    what_worked: str = Field(..., description="What worked well")
    what_failed: str | None = Field(
        default=None, description="What failed (if applicable)"
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="List of lessons learned"
    )
    patterns_detected: list[str] = Field(
        default_factory=list, description="Detected patterns"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Suggestions for improvement"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the insight was created",
    )

    def to_insight(self) -> Insight:
        """Convert to legacy Insight model for backward compatibility.

        Returns:
            Legacy Insight model instance.
        """
        lesson_learned = "; ".join(self.lessons_learned) if self.lessons_learned else ""
        improvement = "; ".join(self.suggestions) if self.suggestions else None

        return Insight(
            id=self.id,
            what_worked=self.what_worked,
            lesson_learned=lesson_learned,
            improvement_suggestion=improvement,
            created_at=self.created_at,
        )

    def to_neo4j_properties(self) -> dict[str, Any]:
        """Convert to properties dict for Neo4j node creation.

        Returns:
            Dictionary of properties for Neo4j node.
        """
        return {
            "id": self.id,
            "experience_id": self.experience_id,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "lessons_learned": json.dumps(self.lessons_learned),
            "patterns_detected": json.dumps(self.patterns_detected),
            "suggestions": json.dumps(self.suggestions),
            "created_at": self.created_at.isoformat(),
        }


class ReflectionHook:
    """Hook for post-task learning reflection.

    Triggers after task completion to analyze what worked, what failed,
    and extract learnings for future improvement.

    The hook can be registered as a LangGraph callback to automatically
    trigger reflection after each task completes.

    Example:
        config = ReflectionConfig(
            experience_logger=logger,
            model_router=router,
            neo4j_connector=connector,
            depth=ReflectionDepth.STANDARD,
        )
        hook = ReflectionHook(config=config)

        # Reflect on an experience
        insight = await hook.reflect(experience)

        # Reflect and store the result
        insight_id = await hook.reflect_and_store(experience)

        # Use as LangGraph callback
        await hook.on_task_complete(experience=experience)
    """

    def __init__(self, config: ReflectionConfig) -> None:
        """Initialize ReflectionHook with configuration.

        Args:
            config: ReflectionConfig with required dependencies.
        """
        self.config = config

    @property
    def experience_logger(self) -> Any:
        """Get the experience logger from config."""
        return self.config.experience_logger

    @property
    def model_router(self) -> Any:
        """Get the model router from config."""
        return self.config.model_router

    @property
    def neo4j_connector(self) -> Any:
        """Get the Neo4j connector from config."""
        return self.config.neo4j_connector

    async def reflect(self, experience: Experience) -> ReflectionInsight:
        """Analyze an experience and extract learnings.

        Uses the model router to call an LLM for analysis based on the
        configured reflection depth.

        Args:
            experience: The experience to reflect on.

        Returns:
            ReflectionInsight with extracted learnings.
        """
        from daw_agents.models.router import TaskType as ModelTaskType

        prompt = self._get_prompt(depth=self.config.depth, experience=experience)

        try:
            response = await self.model_router.route(
                task_type=ModelTaskType.FAST,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse_response(
                response=response, experience_id=experience.id
            )
        except Exception as e:
            logger.warning(
                "Failed to get LLM reflection for experience %s: %s",
                experience.id,
                str(e),
            )
            # Return a minimal insight on failure
            return ReflectionInsight(
                experience_id=experience.id,
                what_worked=(
                    f"Task {experience.task_id} completed"
                    if experience.success
                    else f"Task {experience.task_id} attempted"
                ),
                what_failed=(
                    experience.error_message if not experience.success else None
                ),
                lessons_learned=["Unable to extract detailed lessons due to error"],
            )

    async def store_insight(self, insight: ReflectionInsight) -> str:
        """Store an insight in Neo4j with relationship to experience.

        Creates an Insight node and REFLECTED_AS relationship from the
        experience node.

        Args:
            insight: The ReflectionInsight to store.

        Returns:
            The element ID of the created Insight node.
        """
        # Create insight node
        insight_id = await self.neo4j_connector.create_node(
            labels=["Insight"],
            properties=insight.to_neo4j_properties(),
        )

        # Create REFLECTED_AS relationship from experience to insight
        await self.neo4j_connector.create_relationship(
            from_node_id=insight.experience_id,
            to_node_id=insight_id,
            rel_type="REFLECTED_AS",
        )

        logger.debug(
            "Created insight %s for experience %s",
            insight_id,
            insight.experience_id,
        )

        return str(insight_id)

    async def reflect_and_store(self, experience: Experience) -> str:
        """Reflect on an experience and store the insight.

        Convenience method that combines reflect() and store_insight().

        Args:
            experience: The experience to reflect on.

        Returns:
            The element ID of the created Insight node.
        """
        insight = await self.reflect(experience)
        return await self.store_insight(insight)

    async def get_related_insights(
        self, experience_id: str
    ) -> list[ReflectionInsight]:
        """Get insights related to an experience.

        Args:
            experience_id: The experience node ID.

        Returns:
            List of related ReflectionInsight objects.
        """
        cypher = """
            MATCH (e:Experience)-[:REFLECTED_AS]->(i:Insight)
            WHERE elementId(e) = $id OR e.id = $id
            RETURN i
        """
        results = await self.neo4j_connector.query(cypher, {"id": experience_id})

        insights: list[ReflectionInsight] = []
        for record in results:
            insight_data = record["i"]
            insights.append(self._dict_to_insight(insight_data))

        return insights

    async def on_task_complete(
        self,
        experience: Experience | None = None,
        experience_id: str | None = None,
        task_id: str | None = None,
        success: bool | None = None,
    ) -> str | None:
        """LangGraph callback for task completion.

        Can be called with either an Experience object or individual
        parameters. If using parameters, fetches the experience from
        the experience logger.

        Args:
            experience: Optional Experience object directly.
            experience_id: Optional experience ID to fetch.
            task_id: Optional task ID (for logging).
            success: Optional success status (for logging).

        Returns:
            The insight ID if successful, None otherwise.
        """
        if experience is None:
            if experience_id is None:
                logger.warning(
                    "on_task_complete called without experience or experience_id"
                )
                return None

            # Fetch the experience from the logger
            experience = await self.experience_logger.get_experience_by_id(
                experience_id
            )
            if experience is None:
                logger.warning(
                    "Could not find experience %s for reflection",
                    experience_id,
                )
                return None

        return await self.reflect_and_store(experience)

    def _get_prompt(
        self, depth: ReflectionDepth, experience: Experience
    ) -> str:
        """Generate reflection prompt based on depth and experience.

        Args:
            depth: The reflection depth level.
            experience: The experience to reflect on.

        Returns:
            Prompt string for the LLM.
        """
        context = f"""
Task ID: {experience.task_id}
Task Type: {experience.task_type.value}
Success: {experience.success}
Model Used: {experience.model_used}
Tokens Used: {experience.tokens_used}
Cost (USD): {experience.cost_usd}
Duration (ms): {experience.duration_ms}
Retries: {experience.retries}
"""
        if not experience.success:
            context += f"""
Error Type: {experience.error_type}
Error Message: {experience.error_message}
"""

        if depth == ReflectionDepth.QUICK:
            return f"""Briefly analyze this task execution and provide a JSON response:

{context}

Respond ONLY with valid JSON in this exact format:
{{
    "what_worked": "Brief description of what worked",
    "what_failed": null or "Brief description of failure",
    "lessons_learned": ["One key lesson"],
    "patterns_detected": [],
    "suggestions": []
}}"""

        elif depth == ReflectionDepth.STANDARD:
            return f"""Analyze this task execution and extract learnings. Respond with JSON:

{context}

Consider:
1. What patterns or approaches worked well?
2. What could be improved for similar tasks?
3. Are there any lessons that apply more broadly?

Respond ONLY with valid JSON in this exact format:
{{
    "what_worked": "Description of what worked well in this task",
    "what_failed": null or "Description of what failed",
    "lessons_learned": ["Lesson 1", "Lesson 2", ...],
    "patterns_detected": ["pattern-name-1", "pattern-name-2", ...],
    "suggestions": ["Suggestion 1", "Suggestion 2", ...]
}}"""

        else:  # DEEP
            return f"""Perform a comprehensive analysis of this task execution:

{context}

Analyze:
1. What worked well and why?
2. What failed or could have been better?
3. What patterns or approaches should be remembered?
4. Are there performance or efficiency insights?
5. What specific improvements would help similar tasks?
6. Are there architectural or design patterns to extract?
7. What would make this task more reliable in the future?

Respond ONLY with valid JSON in this exact format:
{{
    "what_worked": "Detailed description of what worked well",
    "what_failed": null or "Detailed description of failures",
    "lessons_learned": ["Lesson 1", "Lesson 2", "Lesson 3", ...],
    "patterns_detected": ["pattern-1", "pattern-2", ...],
    "suggestions": ["Improvement 1", "Improvement 2", ...]
}}"""

    def _parse_response(
        self, response: str, experience_id: str
    ) -> ReflectionInsight:
        """Parse LLM response into ReflectionInsight.

        Args:
            response: Raw LLM response string.
            experience_id: ID of the experience.

        Returns:
            Parsed ReflectionInsight.
        """
        try:
            # Try to extract JSON from response
            # Handle case where response has markdown code blocks
            json_str = response.strip()
            if json_str.startswith("```"):
                # Extract JSON from markdown code block
                lines = json_str.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                json_str = "\n".join(json_lines)

            data = json.loads(json_str)

            return ReflectionInsight(
                experience_id=experience_id,
                what_worked=data.get("what_worked", "No details available"),
                what_failed=data.get("what_failed"),
                lessons_learned=data.get("lessons_learned", []),
                patterns_detected=data.get("patterns_detected", []),
                suggestions=data.get("suggestions", []),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "Failed to parse reflection response: %s. Response was: %s",
                str(e),
                response[:200],
            )
            # Return a minimal insight
            return ReflectionInsight(
                experience_id=experience_id,
                what_worked="Task completed",
                lessons_learned=["Unable to parse detailed reflection"],
            )

    def _dict_to_insight(
        self, data: dict[str, Any]
    ) -> ReflectionInsight:
        """Convert Neo4j record to ReflectionInsight.

        Args:
            data: Dictionary from Neo4j query result.

        Returns:
            ReflectionInsight object.
        """
        # Parse JSON lists from stored strings
        lessons_str = data.get("lessons_learned")
        lessons = (
            json.loads(str(lessons_str))
            if lessons_str
            else []
        )
        patterns_str = data.get("patterns_detected")
        patterns = (
            json.loads(str(patterns_str))
            if patterns_str
            else []
        )
        suggestions_str = data.get("suggestions")
        suggestions = (
            json.loads(str(suggestions_str)) if suggestions_str else []
        )

        return ReflectionInsight(
            id=str(data.get("id", "")),
            experience_id=str(data.get("experience_id", "")),
            what_worked=str(data.get("what_worked", "")),
            what_failed=str(data["what_failed"]) if data.get("what_failed") else None,
            lessons_learned=lessons,
            patterns_detected=patterns,
            suggestions=suggestions,
            created_at=(
                datetime.fromisoformat(str(data["created_at"]))
                if data.get("created_at")
                else datetime.now(UTC)
            ),
        )


__all__ = [
    "ReflectionDepth",
    "ReflectionConfig",
    "ReflectionInsight",
    "ReflectionHook",
]
