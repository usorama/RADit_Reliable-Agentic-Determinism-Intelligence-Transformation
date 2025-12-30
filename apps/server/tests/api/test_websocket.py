"""
Tests for WebSocket Streaming Infrastructure.

Following TDD workflow - PHASE 1: RED
These tests define the expected behavior for:
- WebSocketManager class for connection management
- AgentStreamEvent model (event_type, data, timestamp)
- WebSocket endpoint with auth validation
- LangGraph callback for state transition events
- Connection lifecycle (connect, disconnect, reconnect)
- Multiple concurrent clients per workflow
- Exponential backoff for reconnection
- Message serialization/deserialization
- Broadcast to all clients watching a workflow
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


class TestAgentStreamEventModel:
    """Tests for AgentStreamEvent Pydantic model."""

    def test_event_with_required_fields(self) -> None:
        """Event should accept required fields."""
        from daw_server.api.websocket import AgentStreamEvent, EventType

        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_123",
            data={"state": "planning"},
        )
        assert event.event_type == EventType.STATE_CHANGE
        assert event.workflow_id == "wf_123"
        assert event.data == {"state": "planning"}
        assert event.timestamp is not None

    def test_event_with_custom_timestamp(self) -> None:
        """Event should accept custom timestamp."""
        from daw_server.api.websocket import AgentStreamEvent, EventType

        custom_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        event = AgentStreamEvent(
            event_type=EventType.THOUGHT,
            workflow_id="wf_123",
            data={"thought": "Analyzing requirements..."},
            timestamp=custom_time,
        )
        assert event.timestamp == custom_time

    def test_event_serialization(self) -> None:
        """Event should serialize to JSON properly."""
        from daw_server.api.websocket import AgentStreamEvent, EventType

        event = AgentStreamEvent(
            event_type=EventType.TOOL_CALL,
            workflow_id="wf_123",
            data={"tool": "read_file", "params": {"path": "/src/main.py"}},
        )
        json_data = event.model_dump_json()
        assert "TOOL_CALL" in json_data
        assert "wf_123" in json_data
        assert "read_file" in json_data


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_defined(self) -> None:
        """EventType should have all required types."""
        from daw_server.api.websocket import EventType

        assert EventType.STATE_CHANGE is not None
        assert EventType.THOUGHT is not None
        assert EventType.TOOL_CALL is not None
        assert EventType.ERROR is not None
        assert EventType.CONNECTED is not None
        assert EventType.DISCONNECTED is not None

    def test_event_type_values(self) -> None:
        """EventType values should be strings."""
        from daw_server.api.websocket import EventType

        assert EventType.STATE_CHANGE.value == "STATE_CHANGE"
        assert EventType.THOUGHT.value == "THOUGHT"
        assert EventType.TOOL_CALL.value == "TOOL_CALL"
        assert EventType.ERROR.value == "ERROR"


class TestWebSocketManagerInit:
    """Tests for WebSocketManager initialization."""

    def test_manager_creation(self) -> None:
        """Manager should initialize with empty connections."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager()
        assert manager._connections == {}

    def test_manager_with_max_connections(self) -> None:
        """Manager should support max connections per workflow."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager(max_connections_per_workflow=10)
        assert manager._max_connections_per_workflow == 10


class TestWebSocketManagerConnections:
    """Tests for WebSocketManager connection management."""

    @pytest.mark.asyncio
    async def test_connect_adds_client(self) -> None:
        """Connect should add client to workflow connections."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await manager.connect("wf_123", mock_ws)

        assert "wf_123" in manager._connections
        assert mock_ws in manager._connections["wf_123"]
        mock_ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self) -> None:
        """Disconnect should remove client from workflow connections."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await manager.connect("wf_123", mock_ws)
        await manager.disconnect("wf_123", mock_ws)

        assert mock_ws not in manager._connections.get("wf_123", [])

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_workflow_safe(self) -> None:
        """Disconnect should handle nonexistent workflow gracefully."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager()
        mock_ws = AsyncMock()

        # Should not raise
        await manager.disconnect("nonexistent_wf", mock_ws)

    @pytest.mark.asyncio
    async def test_multiple_clients_per_workflow(self) -> None:
        """Manager should support multiple clients for same workflow."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()

        await manager.connect("wf_123", mock_ws1)
        await manager.connect("wf_123", mock_ws2)

        assert len(manager._connections["wf_123"]) == 2
        assert mock_ws1 in manager._connections["wf_123"]
        assert mock_ws2 in manager._connections["wf_123"]

    @pytest.mark.asyncio
    async def test_max_connections_limit(self) -> None:
        """Manager should enforce max connections per workflow."""
        from daw_server.api.websocket import (
            MaxConnectionsExceededError,
            WebSocketManager,
        )

        manager = WebSocketManager(max_connections_per_workflow=2)
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws3 = AsyncMock()
        mock_ws3.accept = AsyncMock()

        await manager.connect("wf_123", mock_ws1)
        await manager.connect("wf_123", mock_ws2)

        with pytest.raises(MaxConnectionsExceededError):
            await manager.connect("wf_123", mock_ws3)

    def test_get_connection_count(self) -> None:
        """Manager should return connection count for workflow."""
        from daw_server.api.websocket import WebSocketManager

        manager = WebSocketManager()
        assert manager.get_connection_count("wf_123") == 0


class TestWebSocketManagerBroadcast:
    """Tests for WebSocketManager broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_clients(self) -> None:
        """Broadcast should send message to all clients of a workflow."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect("wf_123", mock_ws1)
        await manager.connect("wf_123", mock_ws2)

        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_123",
            data={"state": "executing"},
        )

        await manager.broadcast("wf_123", event)

        mock_ws1.send_json.assert_awaited_once()
        mock_ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_workflow(self) -> None:
        """Broadcast to nonexistent workflow should not raise."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="nonexistent",
            data={},
        )

        # Should not raise
        await manager.broadcast("nonexistent", event)

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected_client(self) -> None:
        """Broadcast should handle and remove disconnected clients."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock(side_effect=Exception("Connection closed"))
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect("wf_123", mock_ws1)
        await manager.connect("wf_123", mock_ws2)

        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_123",
            data={},
        )

        await manager.broadcast("wf_123", event)

        # Working client should still receive message
        mock_ws2.send_json.assert_awaited_once()
        # Disconnected client should be removed
        assert mock_ws1 not in manager._connections["wf_123"]


class TestAgentStreamCallback:
    """Tests for LangGraph callback to emit state transitions."""

    def test_callback_creation(self) -> None:
        """Callback should initialize with manager and workflow_id."""
        from daw_server.api.websocket import AgentStreamCallback, WebSocketManager

        manager = WebSocketManager()
        callback = AgentStreamCallback(manager, "wf_123")

        assert callback._manager is manager
        assert callback._workflow_id == "wf_123"

    @pytest.mark.asyncio
    async def test_on_chain_start_emits_event(self) -> None:
        """on_chain_start should emit STATE_CHANGE event."""
        from daw_server.api.websocket import (
            AgentStreamCallback,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        manager.broadcast = AsyncMock()
        callback = AgentStreamCallback(manager, "wf_123")

        await callback.on_chain_start(
            serialized={"name": "planner_chain"},
            inputs={"query": "Create a todo app"},
        )

        manager.broadcast.assert_awaited_once()
        call_args = manager.broadcast.call_args
        assert call_args[0][0] == "wf_123"
        event = call_args[0][1]
        assert event.event_type == EventType.STATE_CHANGE

    @pytest.mark.asyncio
    async def test_on_tool_start_emits_event(self) -> None:
        """on_tool_start should emit TOOL_CALL event."""
        from daw_server.api.websocket import (
            AgentStreamCallback,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        manager.broadcast = AsyncMock()
        callback = AgentStreamCallback(manager, "wf_123")

        await callback.on_tool_start(
            serialized={"name": "read_file"},
            input_str="/src/main.py",
        )

        manager.broadcast.assert_awaited_once()
        call_args = manager.broadcast.call_args
        event = call_args[0][1]
        assert event.event_type == EventType.TOOL_CALL
        assert "read_file" in str(event.data)

    @pytest.mark.asyncio
    async def test_on_llm_start_emits_thought(self) -> None:
        """on_llm_start should emit THOUGHT event."""
        from daw_server.api.websocket import (
            AgentStreamCallback,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        manager.broadcast = AsyncMock()
        callback = AgentStreamCallback(manager, "wf_123")

        await callback.on_llm_start(
            serialized={"name": "claude-sonnet"},
            prompts=["Analyze the requirements..."],
        )

        manager.broadcast.assert_awaited_once()
        call_args = manager.broadcast.call_args
        event = call_args[0][1]
        assert event.event_type == EventType.THOUGHT

    @pytest.mark.asyncio
    async def test_on_chain_error_emits_error(self) -> None:
        """on_chain_error should emit ERROR event."""
        from daw_server.api.websocket import (
            AgentStreamCallback,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        manager.broadcast = AsyncMock()
        callback = AgentStreamCallback(manager, "wf_123")

        await callback.on_chain_error(error=ValueError("Something went wrong"))

        manager.broadcast.assert_awaited_once()
        call_args = manager.broadcast.call_args
        event = call_args[0][1]
        assert event.event_type == EventType.ERROR
        assert "Something went wrong" in str(event.data)


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint."""

    def test_websocket_endpoint_exists(self) -> None:
        """WebSocket endpoint should be registered."""
        from daw_server.api.websocket import create_websocket_router

        router = create_websocket_router()
        routes = [route.path for route in router.routes]
        assert "/ws/workflow/{workflow_id}" in routes

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self) -> None:
        """Test full WebSocket connection lifecycle."""
        from daw_server.api.websocket import (
            WebSocketManager,
            create_websocket_router,
        )

        app = FastAPI()
        manager = WebSocketManager()
        router = create_websocket_router(manager)
        app.include_router(router)

        with TestClient(app) as client:
            with client.websocket_connect("/ws/workflow/wf_123") as websocket:
                # Should receive connected event
                data = websocket.receive_json()
                assert data["event_type"] == "CONNECTED"

    @pytest.mark.asyncio
    async def test_websocket_auth_from_query_param(self) -> None:
        """WebSocket should accept auth token from query param."""
        from daw_server.api.websocket import (
            WebSocketManager,
            create_websocket_router,
        )

        app = FastAPI()
        manager = WebSocketManager()
        router = create_websocket_router(manager)
        app.include_router(router)

        # Token validation would be mocked in real test
        with TestClient(app) as client:
            with client.websocket_connect(
                "/ws/workflow/wf_123?token=valid_token"
            ) as websocket:
                data = websocket.receive_json()
                assert data["event_type"] == "CONNECTED"


class TestReconnectionConfig:
    """Tests for reconnection configuration."""

    def test_reconnection_config_creation(self) -> None:
        """ReconnectionConfig should have default values."""
        from daw_server.api.websocket import ReconnectionConfig

        config = ReconnectionConfig()
        assert config.initial_delay_ms == 1000
        assert config.max_delay_ms == 30000
        assert config.max_retries == 5
        assert config.backoff_multiplier == 2.0

    def test_reconnection_config_custom_values(self) -> None:
        """ReconnectionConfig should accept custom values."""
        from daw_server.api.websocket import ReconnectionConfig

        config = ReconnectionConfig(
            initial_delay_ms=500,
            max_delay_ms=60000,
            max_retries=10,
            backoff_multiplier=1.5,
        )
        assert config.initial_delay_ms == 500
        assert config.max_delay_ms == 60000
        assert config.max_retries == 10
        assert config.backoff_multiplier == 1.5

    def test_calculate_delay_exponential_backoff(self) -> None:
        """ReconnectionConfig should calculate exponential backoff."""
        from daw_server.api.websocket import ReconnectionConfig

        config = ReconnectionConfig(
            initial_delay_ms=1000,
            max_delay_ms=30000,
            backoff_multiplier=2.0,
        )

        assert config.calculate_delay(0) == 1000
        assert config.calculate_delay(1) == 2000
        assert config.calculate_delay(2) == 4000
        assert config.calculate_delay(3) == 8000

    def test_calculate_delay_caps_at_max(self) -> None:
        """ReconnectionConfig delay should cap at max_delay_ms."""
        from daw_server.api.websocket import ReconnectionConfig

        config = ReconnectionConfig(
            initial_delay_ms=1000,
            max_delay_ms=5000,
            backoff_multiplier=2.0,
        )

        assert config.calculate_delay(10) == 5000  # Should be capped


class TestMessageQueue:
    """Tests for message queue during reconnection."""

    def test_message_queue_creation(self) -> None:
        """MessageQueue should initialize with max size."""
        from daw_server.api.websocket import MessageQueue

        queue = MessageQueue(max_size=100)
        assert queue._max_size == 100
        assert len(queue) == 0

    def test_message_queue_add_and_get(self) -> None:
        """MessageQueue should store and retrieve messages."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            MessageQueue,
        )

        queue = MessageQueue(max_size=100)
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_123",
            data={"state": "planning"},
        )

        queue.add(event)
        assert len(queue) == 1

        messages = queue.get_all()
        assert len(messages) == 1
        assert messages[0].event_type == EventType.STATE_CHANGE

    def test_message_queue_clears_after_get_all(self) -> None:
        """MessageQueue should clear after get_all."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            MessageQueue,
        )

        queue = MessageQueue(max_size=100)
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_123",
            data={},
        )

        queue.add(event)
        queue.get_all()
        assert len(queue) == 0

    def test_message_queue_evicts_old_when_full(self) -> None:
        """MessageQueue should evict oldest messages when full."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            MessageQueue,
        )

        queue = MessageQueue(max_size=2)

        for i in range(3):
            event = AgentStreamEvent(
                event_type=EventType.STATE_CHANGE,
                workflow_id="wf_123",
                data={"index": i},
            )
            queue.add(event)

        messages = queue.get_all()
        assert len(messages) == 2
        # Should have events 1 and 2, not 0
        assert messages[0].data["index"] == 1
        assert messages[1].data["index"] == 2


class TestWebSocketManagerWithQueue:
    """Tests for WebSocketManager with message queueing."""

    @pytest.mark.asyncio
    async def test_manager_queues_messages_for_disconnected(self) -> None:
        """Manager should queue messages for recently disconnected clients."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager(enable_message_queue=True)
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        await manager.connect("wf_123", mock_ws)
        await manager.disconnect("wf_123", mock_ws)

        # Send event while disconnected
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_123",
            data={"state": "executing"},
        )
        await manager.broadcast("wf_123", event)

        # Reconnect and get queued messages
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect("wf_123", mock_ws2, replay_missed=True)

        # Should have sent the queued event
        assert mock_ws2.send_json.await_count >= 1


class TestWebSocketExceptions:
    """Tests for WebSocket-related exceptions."""

    def test_max_connections_exceeded_error(self) -> None:
        """MaxConnectionsExceededError should have proper message."""
        from daw_server.api.websocket import MaxConnectionsExceededError

        error = MaxConnectionsExceededError("wf_123", max_connections=10)
        assert "wf_123" in str(error)
        assert "10" in str(error)

    def test_websocket_auth_error(self) -> None:
        """WebSocketAuthError should have proper message."""
        from daw_server.api.websocket import WebSocketAuthError

        error = WebSocketAuthError("Invalid token")
        assert "Invalid token" in str(error)


class TestIntegrationWebSocketFlow:
    """Integration tests for full WebSocket flow."""

    @pytest.mark.asyncio
    async def test_full_workflow_event_stream(self) -> None:
        """Test streaming events through full workflow."""
        from daw_server.api.websocket import (
            AgentStreamCallback,
            AgentStreamEvent,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Connect client
        await manager.connect("wf_123", mock_ws)

        # Create callback for workflow
        callback = AgentStreamCallback(manager, "wf_123")

        # Simulate workflow events
        await callback.on_chain_start(
            serialized={"name": "planner"}, inputs={"query": "Build todo app"}
        )
        await callback.on_llm_start(
            serialized={"name": "claude"}, prompts=["Planning..."]
        )
        await callback.on_tool_start(
            serialized={"name": "create_file"}, input_str="main.py"
        )

        # Should have sent multiple events
        assert mock_ws.send_json.await_count == 3

    @pytest.mark.asyncio
    async def test_multiple_workflows_isolated(self) -> None:
        """Events for one workflow should not reach other workflow's clients."""
        from daw_server.api.websocket import (
            AgentStreamEvent,
            EventType,
            WebSocketManager,
        )

        manager = WebSocketManager()

        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()

        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect("wf_1", mock_ws1)
        await manager.connect("wf_2", mock_ws2)

        # Send event to wf_1 only
        event = AgentStreamEvent(
            event_type=EventType.STATE_CHANGE,
            workflow_id="wf_1",
            data={"state": "planning"},
        )
        await manager.broadcast("wf_1", event)

        # Only wf_1 client should receive
        mock_ws1.send_json.assert_awaited_once()
        mock_ws2.send_json.assert_not_awaited()
