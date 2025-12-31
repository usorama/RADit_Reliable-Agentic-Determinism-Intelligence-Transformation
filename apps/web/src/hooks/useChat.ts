/**
 * useChat Hook - WebSocket-based chat interaction with the Planner agent.
 *
 * This hook provides:
 * - Message sending and receiving
 * - WebSocket connection management with reconnection
 * - File attachment handling
 * - Streaming response support
 * - Message history management
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ChatMessage,
  ChatState,
  ConnectionStatus,
  EventType,
  FileAttachment,
  MessageRole,
  UseChatOptions,
  UseChatReturn,
  WebSocketEvent,
  ChatRequest,
  ChatResponse,
} from '../types/chat';

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

const DEFAULT_RECONNECT_CONFIG = {
  enabled: true,
  maxRetries: 5,
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2.0,
};

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Generate a unique ID for messages.
 */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Calculate reconnection delay using exponential backoff.
 */
function calculateDelay(
  attempt: number,
  initialDelayMs: number,
  maxDelayMs: number,
  backoffMultiplier: number
): number {
  const delay = initialDelayMs * Math.pow(backoffMultiplier, attempt);
  return Math.min(delay, maxDelayMs);
}

/**
 * Convert a File to FileAttachment.
 */
async function fileToAttachment(file: File): Promise<FileAttachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const attachment: FileAttachment = {
        id: generateId(),
        name: file.name,
        size: file.size,
        type: file.type,
        data: reader.result as string,
      };

      // Create preview URL for images
      if (file.type.startsWith('image/')) {
        attachment.previewUrl = URL.createObjectURL(file);
      }

      resolve(attachment);
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

// -----------------------------------------------------------------------------
// Initial State
// -----------------------------------------------------------------------------

const initialState: ChatState = {
  messages: [],
  isLoading: false,
  isTyping: false,
  workflowId: null,
  error: null,
  connectionStatus: ConnectionStatus.DISCONNECTED,
  pendingFiles: [],
};

// -----------------------------------------------------------------------------
// useChat Hook
// -----------------------------------------------------------------------------

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const {
    apiUrl = DEFAULT_API_URL,
    wsUrl = DEFAULT_WS_URL,
    initialWorkflowId,
    reconnect = DEFAULT_RECONNECT_CONFIG,
    onMessage,
    onError,
    onConnectionChange,
  } = options;

  // State
  const [state, setState] = useState<ChatState>({
    ...initialState,
    workflowId: initialWorkflowId || null,
  });

  // Refs for WebSocket management
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastMessageRef = useRef<{ content: string; attachments?: FileAttachment[] } | null>(null);

  // Ref to track current streaming message
  const streamingMessageIdRef = useRef<string | null>(null);

  // Ref for callbacks to avoid stale closures
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  // -----------------------------------------------------------------------------
  // Connection Status Update
  // -----------------------------------------------------------------------------

  const updateConnectionStatus = useCallback(
    (status: ConnectionStatus) => {
      setState((prev) => ({ ...prev, connectionStatus: status }));
      onConnectionChange?.(status);
    },
    [onConnectionChange]
  );

  // -----------------------------------------------------------------------------
  // Error Handling
  // -----------------------------------------------------------------------------

  const handleError = useCallback(
    (error: string) => {
      setState((prev) => ({ ...prev, error, isLoading: false, isTyping: false }));
      onError?.(error);
    },
    [onError]
  );

  // -----------------------------------------------------------------------------
  // WebSocket Event Handlers
  // -----------------------------------------------------------------------------

  const handleWebSocketMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const wsEvent: WebSocketEvent = JSON.parse(event.data);

        switch (wsEvent.event_type) {
          case EventType.CONNECTED:
            updateConnectionStatus(ConnectionStatus.CONNECTED);
            reconnectAttemptRef.current = 0;
            break;

          case EventType.MESSAGE: {
            const { content, isComplete, phase } = wsEvent.data as {
              content: string;
              isComplete: boolean;
              phase?: string;
            };

            if (streamingMessageIdRef.current) {
              const currentStreamingId = streamingMessageIdRef.current;
              // Update existing streaming message
              setState((prev) => {
                const updatedMessages = prev.messages.map((msg) =>
                  msg.id === currentStreamingId
                    ? {
                        ...msg,
                        content: msg.content + content,
                        isStreaming: !isComplete,
                        phase,
                      }
                    : msg
                );

                // Call onMessage callback if complete (using ref to avoid stale closure)
                if (isComplete) {
                  const completedMsg = updatedMessages.find((m) => m.id === currentStreamingId);
                  if (completedMsg) {
                    onMessageRef.current?.({ ...completedMsg });
                  }
                }

                return {
                  ...prev,
                  messages: updatedMessages,
                  isTyping: false,
                  isLoading: !isComplete,
                };
              });

              if (isComplete) {
                streamingMessageIdRef.current = null;
              }
            }
            break;
          }

          case EventType.TYPING: {
            const { isTyping } = wsEvent.data as { isTyping: boolean };
            setState((prev) => ({ ...prev, isTyping }));
            break;
          }

          case EventType.STATE_CHANGE: {
            const { status, chain_name } = wsEvent.data as {
              status: string;
              chain_name?: string;
            };

            // Update the current message with phase info
            if (streamingMessageIdRef.current && chain_name) {
              setState((prev) => ({
                ...prev,
                messages: prev.messages.map((msg) =>
                  msg.id === streamingMessageIdRef.current
                    ? { ...msg, phase: chain_name }
                    : msg
                ),
              }));
            }

            if (status === 'completed') {
              setState((prev) => ({ ...prev, isLoading: false }));
            }
            break;
          }

          case EventType.THOUGHT: {
            const { status } = wsEvent.data as { status: string };
            setState((prev) => ({
              ...prev,
              isTyping: status === 'thinking',
            }));
            break;
          }

          case EventType.ERROR: {
            const { error_message } = wsEvent.data as { error_message: string };
            handleError(error_message);

            // Mark streaming message as having error
            if (streamingMessageIdRef.current) {
              setState((prev) => ({
                ...prev,
                messages: prev.messages.map((msg) =>
                  msg.id === streamingMessageIdRef.current
                    ? { ...msg, error: error_message, isStreaming: false }
                    : msg
                ),
              }));
              streamingMessageIdRef.current = null;
            }
            break;
          }

          case EventType.TOOL_CALL: {
            // Could update UI to show tool being called
            const { tool_name, status } = wsEvent.data as {
              tool_name: string;
              status: string;
            };
            console.log(`Tool ${tool_name}: ${status}`);
            break;
          }

          default:
            console.log('Unknown event type:', wsEvent.event_type);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    },
    [handleError, updateConnectionStatus]
  );

  // -----------------------------------------------------------------------------
  // WebSocket Connection Management
  // -----------------------------------------------------------------------------

  const connectWebSocket = useCallback(
    (workflowId: string) => {
      // Close existing connection
      if (wsRef.current) {
        wsRef.current.close();
      }

      updateConnectionStatus(ConnectionStatus.CONNECTING);

      const ws = new WebSocket(`${wsUrl}/ws/workflow/${workflowId}`);

      ws.onopen = () => {
        updateConnectionStatus(ConnectionStatus.CONNECTED);
        reconnectAttemptRef.current = 0;
      };

      ws.onmessage = handleWebSocketMessage;

      ws.onerror = () => {
        handleError('WebSocket connection error');
      };

      ws.onclose = (event) => {
        updateConnectionStatus(ConnectionStatus.DISCONNECTED);

        // Attempt reconnection if enabled and not a clean close
        if (reconnect.enabled && !event.wasClean && reconnectAttemptRef.current < reconnect.maxRetries) {
          updateConnectionStatus(ConnectionStatus.RECONNECTING);

          const delay = calculateDelay(
            reconnectAttemptRef.current,
            reconnect.initialDelayMs,
            reconnect.maxDelayMs,
            reconnect.backoffMultiplier
          );

          reconnectAttemptRef.current += 1;

          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket(workflowId);
          }, delay);
        }
      };

      wsRef.current = ws;
    },
    [wsUrl, reconnect, handleWebSocketMessage, updateConnectionStatus, handleError]
  );

  // -----------------------------------------------------------------------------
  // Public Methods
  // -----------------------------------------------------------------------------

  const connect = useCallback(
    (workflowId?: string) => {
      const id = workflowId || state.workflowId;
      if (id) {
        setState((prev) => ({ ...prev, workflowId: id }));
        connectWebSocket(id);
      }
    },
    [state.workflowId, connectWebSocket]
  );

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    updateConnectionStatus(ConnectionStatus.DISCONNECTED);
  }, [updateConnectionStatus]);

  const sendMessage = useCallback(
    async (content: string, attachments?: FileAttachment[]) => {
      if (!content.trim() && (!attachments || attachments.length === 0)) {
        return;
      }

      setState((prev) => ({ ...prev, error: null }));

      // Create user message
      const userMessage: ChatMessage = {
        id: generateId(),
        role: MessageRole.USER,
        content: content.trim(),
        timestamp: new Date(),
        workflowId: state.workflowId || undefined,
        attachments: attachments || state.pendingFiles,
      };

      // Store for retry
      lastMessageRef.current = { content, attachments };

      // Add user message to state
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        pendingFiles: [], // Clear pending files after sending
      }));

      try {
        // Send to backend API
        const requestBody: ChatRequest = {
          message: content.trim(),
          workflow_id: state.workflowId || undefined,
        };

        const response = await fetch(`${apiUrl}/api/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data: ChatResponse = await response.json();

        // Update workflow ID if new
        if (data.workflow_id && data.workflow_id !== state.workflowId) {
          setState((prev) => ({ ...prev, workflowId: data.workflow_id }));
          // Connect to WebSocket for real-time updates
          connectWebSocket(data.workflow_id);
        }

        // Create assistant message (may be updated via WebSocket)
        const assistantMessageId = generateId();
        streamingMessageIdRef.current = assistantMessageId;

        const assistantMessage: ChatMessage = {
          id: assistantMessageId,
          role: MessageRole.ASSISTANT,
          content: data.message || '',
          timestamp: new Date(),
          workflowId: data.workflow_id,
          phase: data.phase,
          isStreaming: true,
        };

        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
        }));

        onMessage?.(assistantMessage);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
        handleError(errorMessage);
      }
    },
    [apiUrl, state.workflowId, state.pendingFiles, connectWebSocket, handleError, onMessage]
  );

  const clearMessages = useCallback(() => {
    setState((prev) => ({
      ...prev,
      messages: [],
      workflowId: null,
      error: null,
    }));
    streamingMessageIdRef.current = null;
    lastMessageRef.current = null;
  }, []);

  const retryLastMessage = useCallback(async () => {
    if (lastMessageRef.current) {
      // Remove the last error message if present
      setState((prev) => ({
        ...prev,
        messages: prev.messages.filter((m) => !m.error),
      }));
      await sendMessage(lastMessageRef.current.content, lastMessageRef.current.attachments);
    }
  }, [sendMessage]);

  const cancelResponse = useCallback(() => {
    if (streamingMessageIdRef.current) {
      setState((prev) => ({
        ...prev,
        messages: prev.messages.map((msg) =>
          msg.id === streamingMessageIdRef.current
            ? { ...msg, isStreaming: false, content: msg.content + ' [Cancelled]' }
            : msg
        ),
        isLoading: false,
        isTyping: false,
      }));
      streamingMessageIdRef.current = null;
    }
  }, []);

  const addFile = useCallback(async (file: File) => {
    try {
      const attachment = await fileToAttachment(file);
      setState((prev) => ({
        ...prev,
        pendingFiles: [...prev.pendingFiles, attachment],
      }));
    } catch {
      handleError('Failed to process file');
    }
  }, [handleError]);

  const removeFile = useCallback((fileId: string) => {
    setState((prev) => {
      const file = prev.pendingFiles.find((f) => f.id === fileId);
      // Revoke preview URL if exists
      if (file?.previewUrl) {
        URL.revokeObjectURL(file.previewUrl);
      }
      return {
        ...prev,
        pendingFiles: prev.pendingFiles.filter((f) => f.id !== fileId),
      };
    });
  }, []);

  const clearPendingFiles = useCallback(() => {
    setState((prev) => {
      // Revoke all preview URLs
      prev.pendingFiles.forEach((file) => {
        if (file.previewUrl) {
          URL.revokeObjectURL(file.previewUrl);
        }
      });
      return {
        ...prev,
        pendingFiles: [],
      };
    });
  }, []);

  // -----------------------------------------------------------------------------
  // Effects
  // -----------------------------------------------------------------------------

  // Connect to initial workflow if provided
  useEffect(() => {
    if (initialWorkflowId) {
      connectWebSocket(initialWorkflowId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialWorkflowId]);

  // Cleanup WebSocket on unmount (separate effect to avoid circular deps)
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      // Revoke all file preview URLs
      state.pendingFiles.forEach((file) => {
        if (file.previewUrl) {
          URL.revokeObjectURL(file.previewUrl);
        }
      });
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    state,
    sendMessage,
    clearMessages,
    retryLastMessage,
    cancelResponse,
    connect,
    disconnect,
    addFile,
    removeFile,
    clearPendingFiles,
  };
}

export default useChat;
