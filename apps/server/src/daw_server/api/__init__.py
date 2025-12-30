"""DAW Server API package.

Provides FastAPI routes and WebSocket infrastructure for agent communication.
"""

from daw_server.api.routes import (
    WorkflowManager,
    create_router,
    create_trace_websocket_router,
)
from daw_server.api.schemas import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalResponse,
    ChatRequest,
    ChatResponse,
    DeleteWorkflowResponse,
    ErrorResponse,
    WebSocketMessage,
    WorkflowStatus,
    WorkflowStatusEnum,
)
from daw_server.api.websocket import (
    AgentStreamCallback,
    AgentStreamEvent,
    EventType,
    MaxConnectionsExceededError,
    MessageQueue,
    ReconnectionConfig,
    WebSocketAuthError,
    WebSocketManager,
    create_websocket_router,
    get_default_manager,
)

__all__ = [
    # Routes
    "create_router",
    "create_trace_websocket_router",
    "WorkflowManager",
    # Schemas - Enums
    "WorkflowStatusEnum",
    "ApprovalAction",
    # Schemas - Chat
    "ChatRequest",
    "ChatResponse",
    # Schemas - Workflow
    "WorkflowStatus",
    "ApprovalRequest",
    "ApprovalResponse",
    "DeleteWorkflowResponse",
    # Schemas - WebSocket
    "WebSocketMessage",
    # Schemas - Error
    "ErrorResponse",
    # WebSocket infrastructure
    "AgentStreamCallback",
    "AgentStreamEvent",
    "EventType",
    "MaxConnectionsExceededError",
    "MessageQueue",
    "ReconnectionConfig",
    "WebSocketAuthError",
    "WebSocketManager",
    "create_websocket_router",
    "get_default_manager",
]
