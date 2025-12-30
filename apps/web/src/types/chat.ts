/**
 * TypeScript types for Chat Interface.
 *
 * This module defines the data types for:
 * - MessageRole: Enum for message sender types
 * - ChatMessage: Individual message in the chat
 * - ChatState: Overall chat state
 * - FileAttachment: Uploaded file data
 * - WebSocketEvent: Events from the WebSocket stream
 */

// -----------------------------------------------------------------------------
// Enums
// -----------------------------------------------------------------------------

/**
 * Role of the message sender in a chat conversation.
 */
export enum MessageRole {
  USER = 'user',
  ASSISTANT = 'assistant',
  SYSTEM = 'system',
}

/**
 * Connection status for WebSocket.
 */
export enum ConnectionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTING = 'reconnecting',
  ERROR = 'error',
}

/**
 * Types of events received from WebSocket stream.
 */
export enum EventType {
  STATE_CHANGE = 'STATE_CHANGE',
  THOUGHT = 'THOUGHT',
  TOOL_CALL = 'TOOL_CALL',
  ERROR = 'ERROR',
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  MESSAGE = 'MESSAGE',
  TYPING = 'TYPING',
}

// -----------------------------------------------------------------------------
// Message Types
// -----------------------------------------------------------------------------

/**
 * File attachment in a chat message.
 */
export interface FileAttachment {
  id: string;
  name: string;
  size: number;
  type: string;
  /** Base64 encoded file data or URL */
  data?: string;
  /** Preview URL for images */
  previewUrl?: string;
}

/**
 * Code block within a message for syntax highlighting.
 */
export interface CodeBlock {
  language: string;
  code: string;
  filename?: string;
}

/**
 * Individual chat message.
 */
export interface ChatMessage {
  /** Unique message identifier */
  id: string;
  /** Role of the message sender */
  role: MessageRole;
  /** Message content (may contain markdown) */
  content: string;
  /** Timestamp when the message was created */
  timestamp: Date;
  /** Workflow ID this message belongs to */
  workflowId?: string;
  /** File attachments (for user messages) */
  attachments?: FileAttachment[];
  /** Whether the message is still being streamed */
  isStreaming?: boolean;
  /** Current phase in the workflow */
  phase?: string;
  /** Error message if something went wrong */
  error?: string;
  /** Metadata from the backend */
  metadata?: Record<string, unknown>;
}

// -----------------------------------------------------------------------------
// State Types
// -----------------------------------------------------------------------------

/**
 * Overall chat state managed by useChat hook.
 */
export interface ChatState {
  /** Array of messages in the conversation */
  messages: ChatMessage[];
  /** Whether the assistant is currently responding */
  isLoading: boolean;
  /** Whether the assistant is typing (before response starts streaming) */
  isTyping: boolean;
  /** Current workflow ID */
  workflowId: string | null;
  /** Current error if any */
  error: string | null;
  /** WebSocket connection status */
  connectionStatus: ConnectionStatus;
  /** Files pending upload */
  pendingFiles: FileAttachment[];
}

// -----------------------------------------------------------------------------
// WebSocket Event Types
// -----------------------------------------------------------------------------

/**
 * Event received from the WebSocket stream.
 */
export interface WebSocketEvent {
  event_type: EventType;
  workflow_id: string;
  data: Record<string, unknown>;
  timestamp: string;
}

/**
 * Message event with content update.
 */
export interface MessageEvent extends WebSocketEvent {
  event_type: EventType.MESSAGE;
  data: {
    content: string;
    isComplete: boolean;
    phase?: string;
  };
}

/**
 * Typing indicator event.
 */
export interface TypingEvent extends WebSocketEvent {
  event_type: EventType.TYPING;
  data: {
    isTyping: boolean;
  };
}

/**
 * State change event from the agent workflow.
 */
export interface StateChangeEvent extends WebSocketEvent {
  event_type: EventType.STATE_CHANGE;
  data: {
    chain_name?: string;
    status: 'started' | 'completed';
    inputs?: Record<string, unknown>;
    outputs?: Record<string, unknown>;
  };
}

/**
 * Thought/reasoning event from the agent.
 */
export interface ThoughtEvent extends WebSocketEvent {
  event_type: EventType.THOUGHT;
  data: {
    model: string;
    status: 'thinking' | 'complete';
    prompt_count?: number;
    thought?: string;
  };
}

/**
 * Tool call event from the agent.
 */
export interface ToolCallEvent extends WebSocketEvent {
  event_type: EventType.TOOL_CALL;
  data: {
    tool_name: string;
    status: 'executing' | 'completed';
    input?: string;
    output_preview?: string;
  };
}

/**
 * Error event from the agent.
 */
export interface ErrorEvent extends WebSocketEvent {
  event_type: EventType.ERROR;
  data: {
    error_type: string;
    error_message: string;
  };
}

// -----------------------------------------------------------------------------
// Hook Return Types
// -----------------------------------------------------------------------------

/**
 * Options for the useChat hook.
 */
export interface UseChatOptions {
  /** Backend API base URL */
  apiUrl?: string;
  /** WebSocket URL */
  wsUrl?: string;
  /** Initial workflow ID to connect to */
  initialWorkflowId?: string;
  /** Reconnection configuration */
  reconnect?: {
    enabled: boolean;
    maxRetries: number;
    initialDelayMs: number;
    maxDelayMs: number;
    backoffMultiplier: number;
  };
  /** Called when a message is received */
  onMessage?: (message: ChatMessage) => void;
  /** Called when an error occurs */
  onError?: (error: string) => void;
  /** Called when connection status changes */
  onConnectionChange?: (status: ConnectionStatus) => void;
}

/**
 * Return type for the useChat hook.
 */
export interface UseChatReturn {
  /** Current chat state */
  state: ChatState;
  /** Send a message to the agent */
  sendMessage: (content: string, attachments?: FileAttachment[]) => Promise<void>;
  /** Clear all messages */
  clearMessages: () => void;
  /** Retry the last failed message */
  retryLastMessage: () => Promise<void>;
  /** Cancel the current streaming response */
  cancelResponse: () => void;
  /** Connect to a workflow */
  connect: (workflowId?: string) => void;
  /** Disconnect from the current workflow */
  disconnect: () => void;
  /** Add a file to pending uploads */
  addFile: (file: File) => Promise<void>;
  /** Remove a pending file */
  removeFile: (fileId: string) => void;
  /** Clear pending files */
  clearPendingFiles: () => void;
}

// -----------------------------------------------------------------------------
// API Types
// -----------------------------------------------------------------------------

/**
 * Request body for POST /api/chat.
 */
export interface ChatRequest {
  message: string;
  context?: Record<string, unknown>;
  workflow_id?: string;
}

/**
 * Response from POST /api/chat.
 */
export interface ChatResponse {
  workflow_id: string;
  message: string;
  status: string;
  tasks_generated?: number;
  phase?: string;
}

export type {
  ChatMessage as Message,
};
