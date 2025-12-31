"""
WebSocket Streaming Infrastructure for Real-Time Agent Updates.

This module provides:
- WebSocketManager for connection management
- AgentStreamEvent model for event data
- AgentStreamCallback for LangGraph integration
- WebSocket endpoint with auth validation
- Reconnection configuration with exponential backoff
- Message queue for missed events during reconnect
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be streamed to clients."""

    STATE_CHANGE = "STATE_CHANGE"
    THOUGHT = "THOUGHT"
    TOOL_CALL = "TOOL_CALL"
    ERROR = "ERROR"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class KanbanEventType(str, Enum):
    """Types of kanban-specific events that can be streamed to clients."""

    TASK_UPDATE = "kanban_update"
    FULL_SYNC = "kanban_sync"
    AGENT_ACTIVITY = "kanban_agent_activity"


class AgentStreamEvent(BaseModel):
    """Model for events streamed to WebSocket clients.

    Attributes:
        event_type: The type of event (STATE_CHANGE, THOUGHT, etc.)
        workflow_id: ID of the workflow this event belongs to
        data: Event-specific data payload
        timestamp: When the event occurred (defaults to now)
    """

    event_type: EventType
    workflow_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KanbanTask(BaseModel):
    """Model for a task on the kanban board.

    Attributes:
        id: Unique task identifier
        title: Short title for the task
        description: Full description of the task
        column: Current column/stage
        priority: Task priority (P0, P1, P2)
        assigned_agent: Agent currently assigned to this task (if any)
        dependencies: List of task IDs this task depends on
        dependents: List of task IDs that depend on this task
        updated_at: ISO timestamp of last update
        created_at: ISO timestamp of creation
    """

    id: str
    title: str
    description: str = ""
    column: str
    priority: str = "P2"
    assigned_agent: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class TaskUpdatePayload(BaseModel):
    """Payload for a task update event.

    Attributes:
        task: The updated task
        previous_column: Previous column (for undo)
        source: Source of the update (user, agent, system)
    """

    task: KanbanTask
    previous_column: str | None = None
    source: str = "system"


class FullSyncPayload(BaseModel):
    """Payload for a full sync event.

    Attributes:
        tasks: All tasks in the workflow
        server_timestamp: Server timestamp for synchronization
    """

    tasks: list[KanbanTask]
    server_timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class AgentActivityPayload(BaseModel):
    """Payload for an agent activity event.

    Attributes:
        task_id: Task ID the agent is working on
        agent_name: Agent name
        activity: Activity type (started, completed, failed, paused)
        details: Additional details
    """

    task_id: str
    agent_name: str
    activity: str
    details: dict[str, Any] = Field(default_factory=dict)


class KanbanWebSocketEvent(BaseModel):
    """Model for kanban events streamed to WebSocket clients.

    Attributes:
        type: Event type (kanban_update, kanban_sync, kanban_agent_activity)
        workflow_id: ID of the workflow this event belongs to
        payload: Event payload (varies by type)
        timestamp: When the event occurred (defaults to now)
    """

    type: KanbanEventType
    workflow_id: str
    payload: TaskUpdatePayload | FullSyncPayload | AgentActivityPayload
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ReconnectionConfig(BaseModel):
    """Configuration for client reconnection with exponential backoff.

    Attributes:
        initial_delay_ms: Initial delay before first retry (default 1000ms)
        max_delay_ms: Maximum delay between retries (default 30000ms)
        max_retries: Maximum number of retry attempts (default 5)
        backoff_multiplier: Multiplier for exponential backoff (default 2.0)
    """

    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    max_retries: int = 5
    backoff_multiplier: float = 2.0

    def calculate_delay(self, attempt: int) -> int:
        """Calculate delay for a given retry attempt using exponential backoff.

        Args:
            attempt: The retry attempt number (0-indexed)

        Returns:
            Delay in milliseconds, capped at max_delay_ms
        """
        delay = self.initial_delay_ms * (self.backoff_multiplier**attempt)
        return min(int(delay), self.max_delay_ms)


class MessageQueue:
    """Queue for storing messages during client disconnection.

    Messages are queued when clients disconnect and replayed on reconnection.
    Old messages are evicted when the queue exceeds max_size.

    Attributes:
        _max_size: Maximum number of messages to store
        _messages: List of queued messages
    """

    def __init__(self, max_size: int = 100) -> None:
        """Initialize the message queue.

        Args:
            max_size: Maximum number of messages to store
        """
        self._max_size = max_size
        self._messages: list[AgentStreamEvent] = []

    def __len__(self) -> int:
        """Return the number of messages in the queue."""
        return len(self._messages)

    def add(self, event: AgentStreamEvent) -> None:
        """Add an event to the queue, evicting oldest if full.

        Args:
            event: The event to add
        """
        if len(self._messages) >= self._max_size:
            self._messages.pop(0)
        self._messages.append(event)

    def get_all(self) -> list[AgentStreamEvent]:
        """Get all messages and clear the queue.

        Returns:
            List of all queued messages
        """
        messages = self._messages.copy()
        self._messages.clear()
        return messages


class MaxConnectionsExceededError(Exception):
    """Exception raised when max connections per workflow is exceeded."""

    def __init__(self, workflow_id: str, max_connections: int) -> None:
        """Initialize the exception.

        Args:
            workflow_id: The workflow that exceeded its connection limit
            max_connections: The maximum allowed connections
        """
        self.workflow_id = workflow_id
        self.max_connections = max_connections
        super().__init__(
            f"Maximum connections ({max_connections}) exceeded for workflow {workflow_id}"
        )


class WebSocketAuthError(Exception):
    """Exception raised for WebSocket authentication errors."""

    def __init__(self, message: str) -> None:
        """Initialize the exception.

        Args:
            message: Error message describing the auth failure
        """
        self.message = message
        super().__init__(message)


class WebSocketManager:
    """Manager for WebSocket connections organized by workflow.

    Handles connection lifecycle, broadcasting events, and message queueing
    for reconnecting clients.

    Attributes:
        _connections: Dict mapping workflow_id to list of WebSocket connections
        _max_connections_per_workflow: Max concurrent connections per workflow
        _enable_message_queue: Whether to queue messages for disconnected clients
        _message_queues: Dict mapping workflow_id to MessageQueue
    """

    def __init__(
        self,
        max_connections_per_workflow: int = 100,
        enable_message_queue: bool = False,
        message_queue_size: int = 100,
    ) -> None:
        """Initialize the WebSocket manager.

        Args:
            max_connections_per_workflow: Maximum concurrent connections per workflow
            enable_message_queue: Whether to enable message queueing for reconnection
            message_queue_size: Maximum size of each workflow's message queue
        """
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._max_connections_per_workflow = max_connections_per_workflow
        self._enable_message_queue = enable_message_queue
        self._message_queue_size = message_queue_size
        self._message_queues: dict[str, MessageQueue] = defaultdict(
            lambda: MessageQueue(message_queue_size)
        )

    async def connect(
        self,
        workflow_id: str,
        websocket: WebSocket,
        replay_missed: bool = False,
    ) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            workflow_id: ID of the workflow to connect to
            websocket: The WebSocket connection
            replay_missed: Whether to replay queued messages on reconnection

        Raises:
            MaxConnectionsExceededError: If max connections exceeded for workflow
        """
        current_count = len(self._connections[workflow_id])
        if current_count >= self._max_connections_per_workflow:
            raise MaxConnectionsExceededError(
                workflow_id, self._max_connections_per_workflow
            )

        await websocket.accept()
        self._connections[workflow_id].append(websocket)

        # Replay missed messages if enabled and requested
        if replay_missed and self._enable_message_queue:
            queue = self._message_queues[workflow_id]
            messages = queue.get_all()
            for msg in messages:
                try:
                    await websocket.send_json(msg.model_dump(mode="json"))
                except Exception as e:
                    logger.warning(f"Failed to replay message: {e}")

        logger.info(
            f"WebSocket connected for workflow {workflow_id}. "
            f"Total connections: {len(self._connections[workflow_id])}"
        )

    async def disconnect(self, workflow_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            workflow_id: ID of the workflow
            websocket: The WebSocket connection to remove
        """
        if workflow_id in self._connections:
            try:
                self._connections[workflow_id].remove(websocket)
                logger.info(
                    f"WebSocket disconnected for workflow {workflow_id}. "
                    f"Remaining: {len(self._connections[workflow_id])}"
                )
            except ValueError:
                pass  # Already removed

    def get_connection_count(self, workflow_id: str) -> int:
        """Get the number of active connections for a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Number of active connections
        """
        return len(self._connections.get(workflow_id, []))

    async def broadcast(self, workflow_id: str, event: AgentStreamEvent) -> None:
        """Broadcast an event to all clients connected to a workflow.

        Handles disconnected clients by removing them from the connection list.
        If message queueing is enabled, also queues the message for reconnection.

        Args:
            workflow_id: ID of the workflow
            event: The event to broadcast
        """
        # Queue message if enabled
        if self._enable_message_queue:
            self._message_queues[workflow_id].add(event)

        if workflow_id not in self._connections:
            return

        connections = self._connections[workflow_id].copy()
        disconnected: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception as e:
                logger.warning(f"Failed to send message: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            try:
                self._connections[workflow_id].remove(ws)
            except ValueError:
                pass


class AgentStreamCallback:
    """LangGraph callback handler for streaming agent events to WebSocket clients.

    This callback integrates with LangGraph workflows to emit real-time events
    for state transitions, LLM thinking, tool calls, and errors.

    Attributes:
        _manager: The WebSocketManager to use for broadcasting
        _workflow_id: The workflow ID to broadcast events for
    """

    def __init__(self, manager: WebSocketManager, workflow_id: str) -> None:
        """Initialize the callback.

        Args:
            manager: WebSocketManager for broadcasting events
            workflow_id: ID of the workflow this callback is for
        """
        self._manager = manager
        self._workflow_id = workflow_id

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Handle chain start event - emits STATE_CHANGE.

        Args:
            serialized: Serialized chain information
            inputs: Chain inputs
            **kwargs: Additional arguments
        """
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id=self._workflow_id,
            data={
                "chain_name": serialized.get("name", "unknown"),
                "inputs": inputs,
                "status": "started",
            },
        )
        await self._manager.broadcast(self._workflow_id, event)

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Handle chain end event - emits STATE_CHANGE.

        Args:
            outputs: Chain outputs
            **kwargs: Additional arguments
        """
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id=self._workflow_id,
            data={
                "status": "completed",
                "outputs": outputs,
            },
        )
        await self._manager.broadcast(self._workflow_id, event)

    async def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Handle chain error - emits ERROR event.

        Args:
            error: The error that occurred
            **kwargs: Additional arguments
        """
        event = AgentStreamEvent(
            event_type=EventType.ERROR,
            workflow_id=self._workflow_id,
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
        await self._manager.broadcast(self._workflow_id, event)

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: Sequence[str],
        **kwargs: Any,
    ) -> None:
        """Handle LLM start - emits THOUGHT event.

        Args:
            serialized: Serialized LLM information
            prompts: The prompts being sent to the LLM
            **kwargs: Additional arguments
        """
        event = AgentStreamEvent(
            event_type=EventType.THOUGHT,
            workflow_id=self._workflow_id,
            data={
                "model": serialized.get("name", "unknown"),
                "status": "thinking",
                # Don't include full prompts for security
                "prompt_count": len(prompts),
            },
        )
        await self._manager.broadcast(self._workflow_id, event)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Handle tool start - emits TOOL_CALL event.

        Args:
            serialized: Serialized tool information
            input_str: Tool input string
            **kwargs: Additional arguments
        """
        event = AgentStreamEvent(
            event_type=EventType.TOOL_CALL,
            workflow_id=self._workflow_id,
            data={
                "tool_name": serialized.get("name", "unknown"),
                "input": input_str,
                "status": "executing",
            },
        )
        await self._manager.broadcast(self._workflow_id, event)

    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Handle tool end - emits TOOL_CALL completed event.

        Args:
            output: Tool output
            **kwargs: Additional arguments
        """
        event = AgentStreamEvent(
            event_type=EventType.TOOL_CALL,
            workflow_id=self._workflow_id,
            data={
                "status": "completed",
                # Truncate long outputs
                "output_preview": output[:500] if len(output) > 500 else output,
            },
        )
        await self._manager.broadcast(self._workflow_id, event)


def create_websocket_router(
    manager: WebSocketManager | None = None,
) -> APIRouter:
    """Create a FastAPI router with WebSocket endpoints.

    Args:
        manager: WebSocketManager instance (creates default if None)

    Returns:
        FastAPI APIRouter with WebSocket routes
    """
    if manager is None:
        manager = WebSocketManager()

    router = APIRouter()

    @router.websocket("/ws/workflow/{workflow_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        workflow_id: str,
        token: str | None = Query(default=None),
    ) -> None:
        """WebSocket endpoint for streaming workflow events.

        Args:
            websocket: The WebSocket connection
            workflow_id: ID of the workflow to stream events for
            token: Optional auth token from query param
        """
        # TODO: Implement full token validation when AUTH is integrated
        # For now, accept all connections

        try:
            await manager.connect(workflow_id, websocket)

            # Send connected event
            connected_event = AgentStreamEvent(
                event_type=EventType.CONNECTED,
                workflow_id=workflow_id,
                data={"message": f"Connected to workflow {workflow_id}"},
            )
            await websocket.send_json(connected_event.model_dump(mode="json"))

            # Keep connection alive and handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    # Handle any client messages (e.g., heartbeat)
                    if data == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    break

        except MaxConnectionsExceededError as e:
            await websocket.close(code=1013, reason=str(e))
        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
        finally:
            await manager.disconnect(workflow_id, websocket)

    return router


# Default manager instance for convenience
_default_manager: WebSocketManager | None = None


def get_default_manager() -> WebSocketManager:
    """Get or create the default WebSocketManager instance.

    Returns:
        The default WebSocketManager
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = WebSocketManager()
    return _default_manager


class KanbanBroadcaster:
    """Broadcaster for kanban-specific events.

    Provides convenience methods for broadcasting task updates, full syncs,
    and agent activity events to all connected clients for a workflow.

    Attributes:
        _manager: The WebSocketManager to use for broadcasting
    """

    def __init__(self, manager: WebSocketManager | None = None) -> None:
        """Initialize the broadcaster.

        Args:
            manager: WebSocketManager for broadcasting events (uses default if None)
        """
        self._manager = manager or get_default_manager()

    async def broadcast_task_update(
        self,
        workflow_id: str,
        task: KanbanTask,
        previous_column: str | None = None,
        source: str = "system",
    ) -> None:
        """Broadcast a task update event.

        Args:
            workflow_id: ID of the workflow
            task: The updated task
            previous_column: Previous column (for undo)
            source: Source of the update (user, agent, system)
        """
        event = KanbanWebSocketEvent(
            type=KanbanEventType.TASK_UPDATE,
            workflow_id=workflow_id,
            payload=TaskUpdatePayload(
                task=task,
                previous_column=previous_column,
                source=source,
            ),
        )
        await self._broadcast_kanban_event(workflow_id, event)

    async def broadcast_full_sync(
        self,
        workflow_id: str,
        tasks: list[KanbanTask],
    ) -> None:
        """Broadcast a full sync event.

        Args:
            workflow_id: ID of the workflow
            tasks: All tasks in the workflow
        """
        event = KanbanWebSocketEvent(
            type=KanbanEventType.FULL_SYNC,
            workflow_id=workflow_id,
            payload=FullSyncPayload(tasks=tasks),
        )
        await self._broadcast_kanban_event(workflow_id, event)

    async def broadcast_agent_activity(
        self,
        workflow_id: str,
        task_id: str,
        agent_name: str,
        activity: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast an agent activity event.

        Args:
            workflow_id: ID of the workflow
            task_id: Task ID the agent is working on
            agent_name: Agent name
            activity: Activity type (started, completed, failed, paused)
            details: Additional details
        """
        event = KanbanWebSocketEvent(
            type=KanbanEventType.AGENT_ACTIVITY,
            workflow_id=workflow_id,
            payload=AgentActivityPayload(
                task_id=task_id,
                agent_name=agent_name,
                activity=activity,
                details=details or {},
            ),
        )
        await self._broadcast_kanban_event(workflow_id, event)

    async def _broadcast_kanban_event(
        self,
        workflow_id: str,
        event: KanbanWebSocketEvent,
    ) -> None:
        """Internal method to broadcast a kanban event.

        Converts the Pydantic model to JSON and broadcasts to all connected clients.

        Args:
            workflow_id: ID of the workflow
            event: The kanban event to broadcast
        """
        if workflow_id not in self._manager._connections:
            return

        connections = self._manager._connections[workflow_id].copy()
        disconnected: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception as e:
                logger.warning(f"Failed to send kanban event: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            try:
                self._manager._connections[workflow_id].remove(ws)
            except ValueError:
                pass


# Default kanban broadcaster instance
_default_kanban_broadcaster: KanbanBroadcaster | None = None


def get_kanban_broadcaster() -> KanbanBroadcaster:
    """Get or create the default KanbanBroadcaster instance.

    Returns:
        The default KanbanBroadcaster
    """
    global _default_kanban_broadcaster
    if _default_kanban_broadcaster is None:
        _default_kanban_broadcaster = KanbanBroadcaster()
    return _default_kanban_broadcaster


__all__ = [
    "AgentActivityPayload",
    "AgentStreamCallback",
    "AgentStreamEvent",
    "EventType",
    "FullSyncPayload",
    "KanbanBroadcaster",
    "KanbanEventType",
    "KanbanTask",
    "KanbanWebSocketEvent",
    "MaxConnectionsExceededError",
    "MessageQueue",
    "ReconnectionConfig",
    "TaskUpdatePayload",
    "WebSocketAuthError",
    "WebSocketManager",
    "create_websocket_router",
    "get_default_manager",
    "get_kanban_broadcaster",
]
