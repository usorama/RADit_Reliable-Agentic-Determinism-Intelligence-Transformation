"""
Experience Logger for self-learning foundation.

This module provides the ExperienceLogger class that stores task completion
experiences in Neo4j for future learning and RAG retrieval.

Implements FR-07.1: Experience-Driven Learning Pattern

Neo4j Schema:
(:Experience {task_type, success, prompt_version, model_used, tokens_used, cost_usd})
  -[:USED_SKILL]->(:Skill {name, pattern, success_rate})
  -[:PRODUCED]->(:Artifact {type, path})
  -[:REFLECTED_AS]->(:Insight {what_worked, lesson_learned})
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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
    from daw_agents.memory.neo4j import Neo4jConnector

logger = logging.getLogger(__name__)


class ExperienceLogger:
    """
    Logger for storing and querying task completion experiences.

    This class provides the foundation for self-learning capabilities
    by persisting experiences in Neo4j and enabling RAG-style retrieval.

    Example:
        connector = Neo4jConnector.get_instance(config)
        logger = ExperienceLogger(neo4j_connector=connector)

        # Log a successful experience
        exp_id = await logger.log_success(
            task_id="CORE-003",
            task_type=TaskType.CODING,
            prompt_version="executor_v1.2",
            model_used="claude-sonnet-4-20250514",
            tokens_used=5000,
            cost_usd=0.045,
            duration_ms=12500
        )

        # Query similar experiences
        query = ExperienceQuery(task_type=TaskType.CODING, success=True)
        experiences = await logger.query_similar_experiences(query)

        # Get success rate
        rate = await logger.calculate_success_rate(task_type=TaskType.CODING)
    """

    def __init__(self, neo4j_connector: Neo4jConnector) -> None:
        """
        Initialize ExperienceLogger with a Neo4j connector.

        Args:
            neo4j_connector: The Neo4j connector instance for database operations.
        """
        self.neo4j_connector = neo4j_connector

    async def log_success(
        self,
        task_id: str,
        task_type: TaskType,
        prompt_version: str,
        model_used: str,
        tokens_used: int,
        cost_usd: float,
        duration_ms: int,
        retries: int = 0,
        skills: list[Skill] | None = None,
        artifacts: list[Artifact] | None = None,
    ) -> str:
        """
        Log a successful task completion experience.

        Args:
            task_id: ID of the completed task.
            task_type: Type of task (planning, coding, validation, etc.).
            prompt_version: Version of the prompt used.
            model_used: LLM model that executed the task.
            tokens_used: Total tokens consumed.
            cost_usd: Cost in USD.
            duration_ms: Duration in milliseconds.
            retries: Number of retry attempts (default 0).
            skills: Optional list of skills used.
            artifacts: Optional list of artifacts produced.

        Returns:
            The element ID of the created Experience node.
        """
        experience = Experience(
            task_id=task_id,
            task_type=task_type,
            success=True,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            retries=retries,
            timestamp=datetime.now(UTC),
        )

        # Create Experience node
        exp_node_id = await self.neo4j_connector.create_node(
            labels=["Experience"],
            properties=experience.to_neo4j_properties(),
        )

        logger.debug("Created Experience node: %s for task %s", exp_node_id, task_id)

        # Create skill relationships
        if skills:
            await self._create_skill_relationships(exp_node_id, skills)

        # Create artifact relationships
        if artifacts:
            await self._create_artifact_relationships(exp_node_id, artifacts)

        return exp_node_id

    async def log_failure(
        self,
        task_id: str,
        task_type: TaskType,
        prompt_version: str,
        model_used: str,
        tokens_used: int,
        cost_usd: float,
        duration_ms: int,
        error_message: str,
        error_type: str | None = None,
        retries: int = 0,
        skills: list[Skill] | None = None,
        artifacts: list[Artifact] | None = None,
    ) -> str:
        """
        Log a failed task attempt.

        Args:
            task_id: ID of the failed task.
            task_type: Type of task.
            prompt_version: Version of the prompt used.
            model_used: LLM model that executed the task.
            tokens_used: Total tokens consumed.
            cost_usd: Cost in USD.
            duration_ms: Duration in milliseconds.
            error_message: Error message describing the failure.
            error_type: Type/class of the error.
            retries: Number of retry attempts.
            skills: Optional list of skills used.
            artifacts: Optional list of artifacts produced.

        Returns:
            The element ID of the created Experience node.
        """
        experience = Experience(
            task_id=task_id,
            task_type=task_type,
            success=False,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            retries=retries,
            error_message=error_message,
            error_type=error_type,
            timestamp=datetime.now(UTC),
        )

        # Create Experience node
        exp_node_id = await self.neo4j_connector.create_node(
            labels=["Experience"],
            properties=experience.to_neo4j_properties(),
        )

        logger.debug("Created failed Experience node: %s for task %s", exp_node_id, task_id)

        # Create skill relationships even for failures
        if skills:
            await self._create_skill_relationships(exp_node_id, skills)

        # Create artifact relationships
        if artifacts:
            await self._create_artifact_relationships(exp_node_id, artifacts)

        return exp_node_id

    async def _create_skill_relationships(
        self, exp_node_id: str, skills: list[Skill]
    ) -> None:
        """Create USED_SKILL relationships between Experience and Skill nodes."""
        for skill in skills:
            # Get or create the skill node
            skill_id = await self.get_or_create_skill(skill)

            # Create the relationship
            await self.neo4j_connector.create_relationship(
                from_node_id=exp_node_id,
                to_node_id=skill_id,
                rel_type="USED_SKILL",
            )
            logger.debug("Created USED_SKILL relationship: %s -> %s", exp_node_id, skill_id)

    async def _create_artifact_relationships(
        self, exp_node_id: str, artifacts: list[Artifact]
    ) -> None:
        """Create PRODUCED relationships between Experience and Artifact nodes."""
        for artifact in artifacts:
            # Create artifact node
            artifact_id = await self.neo4j_connector.create_node(
                labels=["Artifact"],
                properties=artifact.to_neo4j_properties(),
            )

            # Create the relationship
            await self.neo4j_connector.create_relationship(
                from_node_id=exp_node_id,
                to_node_id=artifact_id,
                rel_type="PRODUCED",
            )
            logger.debug("Created PRODUCED relationship: %s -> %s", exp_node_id, artifact_id)

    async def get_or_create_skill(self, skill: Skill) -> str:
        """
        Get an existing skill or create a new one.

        If the skill exists, increment its usage count.

        Args:
            skill: The skill to find or create.

        Returns:
            The element ID of the skill node.
        """
        # Try to find existing skill
        cypher = """
            MATCH (s:Skill {name: $name})
            SET s.usage_count = s.usage_count + 1
            RETURN elementId(s) as id
        """
        results = await self.neo4j_connector.query(cypher, {"name": skill.name})

        if results:
            return str(results[0]["id"])

        # Create new skill
        return await self.neo4j_connector.create_node(
            labels=["Skill"],
            properties=skill.to_neo4j_properties(),
        )

    async def query_similar_experiences(
        self, query: ExperienceQuery
    ) -> list[Experience]:
        """
        Query for similar experiences based on criteria.

        This enables RAG-style retrieval of past experiences for
        learning and error resolution.

        Args:
            query: Query parameters to filter experiences.

        Returns:
            List of matching Experience objects.
        """
        # Build dynamic WHERE clause
        conditions: list[str] = []
        params: dict[str, str | bool | int | float] = {}

        if query.task_type is not None:
            conditions.append("e.task_type = $task_type")
            params["task_type"] = query.task_type.value

        if query.success is not None:
            conditions.append("e.success = $success")
            params["success"] = query.success

        if query.model_used is not None:
            conditions.append("e.model_used = $model_used")
            params["model_used"] = query.model_used

        if query.error_type is not None:
            conditions.append("e.error_type = $error_type")
            params["error_type"] = query.error_type

        if query.start_time is not None:
            conditions.append("e.timestamp >= $start_time")
            params["start_time"] = query.start_time.isoformat()

        if query.end_time is not None:
            conditions.append("e.timestamp <= $end_time")
            params["end_time"] = query.end_time.isoformat()

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params["limit"] = query.limit

        cypher = f"""
            MATCH (e:Experience)
            WHERE {where_clause}
            RETURN e
            ORDER BY e.timestamp DESC
            LIMIT $limit
        """

        results = await self.neo4j_connector.query(cypher, params)

        # Convert to Experience objects
        experiences: list[Experience] = []
        for record in results:
            exp_data = record["e"]
            experiences.append(self._dict_to_experience(exp_data))

        return experiences

    async def calculate_success_rate(
        self,
        task_type: TaskType | None = None,
        model_used: str | None = None,
    ) -> SuccessRate:
        """
        Calculate success rate for a task type and/or model.

        Args:
            task_type: Optional task type to filter by.
            model_used: Optional model to filter by.

        Returns:
            SuccessRate object with statistics.
        """
        conditions: list[str] = []
        params: dict[str, str] = {}

        if task_type is not None:
            conditions.append("e.task_type = $task_type")
            params["task_type"] = task_type.value

        if model_used is not None:
            conditions.append("e.model_used = $model_used")
            params["model_used"] = model_used

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cypher = f"""
            MATCH (e:Experience)
            WHERE {where_clause}
            RETURN
                count(e) as total,
                sum(CASE WHEN e.success THEN 1 ELSE 0 END) as successes
        """

        results = await self.neo4j_connector.query(cypher, params)

        if not results:
            return SuccessRate(
                task_type=task_type,
                model_used=model_used,
                success_rate=0.0,
                total_count=0,
                success_count=0,
            )

        total = results[0]["total"]
        successes = results[0]["successes"]
        rate = successes / total if total > 0 else 0.0

        return SuccessRate(
            task_type=task_type,
            model_used=model_used,
            success_rate=rate,
            total_count=total,
            success_count=successes,
        )

    async def get_experience_by_id(self, experience_id: str) -> Experience | None:
        """
        Retrieve an experience by its Neo4j element ID.

        Args:
            experience_id: The element ID of the experience node.

        Returns:
            Experience object if found, None otherwise.
        """
        cypher = """
            MATCH (e:Experience)
            WHERE elementId(e) = $id OR e.id = $id
            RETURN e
        """
        results = await self.neo4j_connector.query(cypher, {"id": experience_id})

        if not results:
            return None

        return self._dict_to_experience(results[0]["e"])

    async def get_related_skills(self, experience_id: str) -> list[Skill]:
        """
        Get skills related to an experience via USED_SKILL relationship.

        Args:
            experience_id: The experience node ID.

        Returns:
            List of related Skill objects.
        """
        cypher = """
            MATCH (e:Experience)-[:USED_SKILL]->(s:Skill)
            WHERE elementId(e) = $id OR e.id = $id
            RETURN s
        """
        results = await self.neo4j_connector.query(cypher, {"id": experience_id})

        skills: list[Skill] = []
        for record in results:
            skill_data = record["s"]
            skills.append(
                Skill(
                    name=skill_data["name"],
                    pattern=skill_data["pattern"],
                    description=skill_data.get("description"),
                    success_rate=skill_data.get("success_rate", 0.0),
                    usage_count=skill_data.get("usage_count", 0),
                )
            )

        return skills

    async def get_related_artifacts(self, experience_id: str) -> list[Artifact]:
        """
        Get artifacts produced by an experience via PRODUCED relationship.

        Args:
            experience_id: The experience node ID.

        Returns:
            List of related Artifact objects.
        """
        cypher = """
            MATCH (e:Experience)-[:PRODUCED]->(a:Artifact)
            WHERE elementId(e) = $id OR e.id = $id
            RETURN a
        """
        results = await self.neo4j_connector.query(cypher, {"id": experience_id})

        artifacts: list[Artifact] = []
        for record in results:
            artifact_data = record["a"]
            artifacts.append(
                Artifact(
                    artifact_type=ArtifactType(artifact_data["type"]),
                    path=artifact_data["path"],
                    description=artifact_data.get("description"),
                )
            )

        return artifacts

    async def add_insight(self, experience_id: str, insight: Insight) -> str:
        """
        Add an insight to an experience via REFLECTED_AS relationship.

        Args:
            experience_id: The experience node ID.
            insight: The insight to add.

        Returns:
            The element ID of the created Insight node.
        """
        # Create insight node
        insight_id = await self.neo4j_connector.create_node(
            labels=["Insight"],
            properties=insight.to_neo4j_properties(),
        )

        # Create relationship
        await self.neo4j_connector.create_relationship(
            from_node_id=experience_id,
            to_node_id=insight_id,
            rel_type="REFLECTED_AS",
        )

        logger.debug("Created REFLECTED_AS relationship: %s -> %s", experience_id, insight_id)

        return insight_id

    async def log_batch(self, experiences: list[Experience]) -> list[str]:
        """
        Log multiple experiences in batch.

        Args:
            experiences: List of Experience objects to log.

        Returns:
            List of created experience node IDs.
        """
        exp_ids: list[str] = []
        for exp in experiences:
            exp_id = await self.neo4j_connector.create_node(
                labels=["Experience"],
                properties=exp.to_neo4j_properties(),
            )
            exp_ids.append(exp_id)

        logger.debug("Created %d Experience nodes in batch", len(exp_ids))
        return exp_ids

    def _dict_to_experience(self, data: dict[str, str | int | float | bool]) -> Experience:
        """Convert a Neo4j record dict to an Experience object."""
        return Experience(
            id=str(data.get("id", "")),
            task_id=str(data["task_id"]),
            task_type=TaskType(data["task_type"]),
            success=bool(data["success"]),
            prompt_version=str(data["prompt_version"]),
            model_used=str(data["model_used"]),
            tokens_used=int(data["tokens_used"]),
            cost_usd=float(data["cost_usd"]),
            duration_ms=int(data["duration_ms"]),
            retries=int(data.get("retries", 0)),
            timestamp=datetime.fromisoformat(str(data["timestamp"])),
            error_message=str(data["error_message"]) if data.get("error_message") else None,
            error_type=str(data["error_type"]) if data.get("error_type") else None,
        )


__all__ = ["ExperienceLogger"]
