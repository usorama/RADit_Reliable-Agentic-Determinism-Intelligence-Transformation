"""Neo4j-backed Workflow Repository.

Replaces the in-memory WorkflowManager with persistent Neo4j storage.
Maintains the same interface for backward compatibility.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from daw_server.db.neo4j import Neo4jConnection

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """Neo4j-backed workflow storage.

    Provides persistent storage for workflows that survives server restarts.
    Uses the same interface as the original WorkflowManager for backward compatibility.

    Workflow Node Properties:
        - id: UUID string
        - user_id: Owner user ID
        - status: Workflow status enum value
        - phase: Current phase
        - message: Initial user message
        - context: JSON-encoded context dict
        - progress: Float progress percentage
        - tasks_total: Total task count
        - tasks_completed: Completed task count
        - current_task: Current task description
        - created_at: ISO timestamp
        - updated_at: ISO timestamp
        - error_message: Error message if any
        - planner_state: JSON-encoded planner state
        - tasks: JSON-encoded tasks data
        - kanban_tasks: JSON-encoded kanban data
        - interview_state: JSON-encoded interview state
        - audit_log: JSON-encoded audit entries
    """

    def __init__(self, connection: Neo4jConnection) -> None:
        """Initialize the repository with a Neo4j connection.

        Args:
            connection: Neo4jConnection instance
        """
        self._connection = connection

    async def create_workflow(
        self,
        user_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new workflow.

        Args:
            user_id: ID of the user creating the workflow
            message: Initial message from user
            context: Optional context dictionary

        Returns:
            Created workflow data
        """
        workflow_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        now_iso = now.isoformat()

        # Default status - importing here to avoid circular imports
        from daw_server.api.schemas import WorkflowStatusEnum

        workflow = {
            "id": workflow_id,
            "user_id": user_id,
            "status": WorkflowStatusEnum.PLANNING.value,
            "phase": "interview",
            "message": message,
            "context": context,
            "progress": 0.0,
            "tasks_total": 0,
            "tasks_completed": 0,
            "current_task": "Analyzing requirements",
            "created_at": now,
            "updated_at": now,
            "error_message": None,
        }

        # Serialize complex fields to JSON for Neo4j storage
        context_json = json.dumps(context) if context else None

        query = """
        CREATE (w:Workflow {
            id: $id,
            user_id: $user_id,
            status: $status,
            phase: $phase,
            message: $message,
            context: $context,
            progress: $progress,
            tasks_total: $tasks_total,
            tasks_completed: $tasks_completed,
            current_task: $current_task,
            created_at: $created_at,
            updated_at: $updated_at,
            error_message: $error_message
        })
        RETURN w
        """

        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            await session.run(
                query,
                {
                    "id": workflow_id,
                    "user_id": user_id,
                    "status": WorkflowStatusEnum.PLANNING.value,
                    "phase": "interview",
                    "message": message,
                    "context": context_json,
                    "progress": 0.0,
                    "tasks_total": 0,
                    "tasks_completed": 0,
                    "current_task": "Analyzing requirements",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "error_message": None,
                },
            )

        logger.info("Created workflow %s for user %s", workflow_id, user_id)
        return workflow

    async def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Get a workflow by ID.

        Args:
            workflow_id: The workflow ID

        Returns:
            Workflow data or None if not found
        """
        query = """
        MATCH (w:Workflow {id: $id})
        RETURN w
        """

        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            result = await session.run(query, {"id": workflow_id})
            record = await result.single()

            if record is None:
                return None

            return self._deserialize_workflow(dict(record["w"]))

    async def update_workflow(
        self, workflow_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update a workflow.

        Args:
            workflow_id: The workflow ID
            updates: Fields to update

        Returns:
            Updated workflow data or None if not found
        """
        # First check if workflow exists
        existing = await self.get_workflow(workflow_id)
        if existing is None:
            return None

        # Serialize complex fields
        serialized_updates = self._serialize_updates(updates)
        serialized_updates["updated_at"] = datetime.now(UTC).isoformat()

        # Build dynamic SET clause
        set_clauses = ", ".join(f"w.{key} = ${key}" for key in serialized_updates)
        query = f"""
        MATCH (w:Workflow {{id: $id}})
        SET {set_clauses}
        RETURN w
        """

        params = {"id": workflow_id, **serialized_updates}

        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            result = await session.run(query, params)
            record = await result.single()

            if record is None:
                return None

            return self._deserialize_workflow(dict(record["w"]))

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow.

        Args:
            workflow_id: The workflow ID

        Returns:
            True if deleted, False if not found
        """
        # First check if exists
        existing = await self.get_workflow(workflow_id)
        if existing is None:
            return False

        query = """
        MATCH (w:Workflow {id: $id})
        DELETE w
        """

        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            await session.run(query, {"id": workflow_id})

        logger.info("Deleted workflow %s", workflow_id)
        return True

    async def user_owns_workflow(self, user_id: str, workflow_id: str) -> bool:
        """Check if a user owns a workflow.

        Args:
            user_id: The user ID
            workflow_id: The workflow ID

        Returns:
            True if the user owns the workflow
        """
        query = """
        MATCH (w:Workflow {id: $workflow_id, user_id: $user_id})
        RETURN count(w) > 0 as owns
        """

        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            result = await session.run(
                query,
                {"workflow_id": workflow_id, "user_id": user_id},
            )
            record = await result.single()
            return record["owns"] if record else False

    async def list_user_workflows(self, user_id: str) -> list[dict[str, Any]]:
        """List all workflows for a user.

        Args:
            user_id: The user ID

        Returns:
            List of workflow data dictionaries, ordered by created_at descending
        """
        query = """
        MATCH (w:Workflow {user_id: $user_id})
        RETURN w
        ORDER BY w.created_at DESC
        """

        workflows = []
        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            result = await session.run(query, {"user_id": user_id})
            async for record in result:
                workflow = self._deserialize_workflow(dict(record["w"]))
                workflows.append(workflow)

        return workflows

    async def clear_all(self) -> None:
        """Clear all workflows (for testing).

        WARNING: This deletes ALL workflow data. Use only in tests.
        """
        query = """
        MATCH (w:Workflow)
        DELETE w
        """

        async with self._connection.driver.session(
            database=self._connection.database
        ) as session:
            await session.run(query)

        logger.warning("Cleared all workflows from database")

    def _serialize_updates(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Serialize update values for Neo4j storage.

        Converts complex Python objects to JSON strings.

        Args:
            updates: Dictionary of field updates

        Returns:
            Serialized updates suitable for Neo4j
        """
        serialized: dict[str, Any] = {}

        for key, value in updates.items():
            if key in (
                "context",
                "planner_state",
                "tasks",
                "kanban_tasks",
                "interview_state",
                "audit_log",
            ):
                # Serialize complex objects to JSON
                serialized[key] = json.dumps(value) if value is not None else None
            elif key == "status":
                # Handle enum values
                if hasattr(value, "value"):
                    serialized[key] = value.value
                else:
                    serialized[key] = value
            elif isinstance(value, datetime):
                # Convert datetime to ISO string
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value

        return serialized

    def _deserialize_workflow(self, node_data: dict[str, Any]) -> dict[str, Any]:
        """Deserialize a workflow node from Neo4j.

        Converts JSON strings back to Python objects and handles datetime parsing.

        Args:
            node_data: Raw node data from Neo4j

        Returns:
            Deserialized workflow dictionary
        """
        from daw_server.api.schemas import WorkflowStatusEnum

        workflow: dict[str, Any] = {}

        for key, value in node_data.items():
            if key in (
                "context",
                "planner_state",
                "tasks",
                "kanban_tasks",
                "interview_state",
                "audit_log",
            ):
                # Deserialize JSON fields
                if value is not None and isinstance(value, str):
                    try:
                        workflow[key] = json.loads(value)
                    except json.JSONDecodeError:
                        workflow[key] = value
                else:
                    workflow[key] = value
            elif key == "status":
                # Convert status string back to enum
                try:
                    workflow[key] = WorkflowStatusEnum(value)
                except ValueError:
                    workflow[key] = value
            elif key in ("created_at", "updated_at"):
                # Parse ISO datetime strings
                if isinstance(value, str):
                    try:
                        workflow[key] = datetime.fromisoformat(value)
                    except ValueError:
                        workflow[key] = value
                else:
                    workflow[key] = value
            else:
                workflow[key] = value

        return workflow


# Singleton instance for the repository
_workflow_repository: WorkflowRepository | None = None


def get_workflow_repository() -> WorkflowRepository:
    """Get the global WorkflowRepository instance.

    Returns:
        The global WorkflowRepository instance

    Raises:
        RuntimeError: If repository not initialized
    """
    global _workflow_repository
    if _workflow_repository is None:
        raise RuntimeError(
            "WorkflowRepository not initialized. Call init_workflow_repository() first."
        )
    return _workflow_repository


def init_workflow_repository(connection: Neo4jConnection) -> WorkflowRepository:
    """Initialize the global WorkflowRepository.

    Should be called at application startup after Neo4j connection is established.

    Args:
        connection: Neo4jConnection instance

    Returns:
        The initialized WorkflowRepository instance
    """
    global _workflow_repository
    _workflow_repository = WorkflowRepository(connection)
    return _workflow_repository


__all__ = [
    "WorkflowRepository",
    "get_workflow_repository",
    "init_workflow_repository",
]
