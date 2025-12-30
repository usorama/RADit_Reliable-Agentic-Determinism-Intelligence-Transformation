'use client';

/**
 * React hook for connecting to the agent trace WebSocket stream.
 *
 * Provides real-time agent state updates with automatic reconnection
 * using exponential backoff.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AgentStreamActions,
  AgentStreamState,
  ReconnectionConfig,
  TraceEvent,
  TraceNode,
  TraceNodeDetails,
} from '@/types/trace';
import {
  ConnectionState,
  DEFAULT_RECONNECTION_CONFIG,
  EventType,
  eventTypeToStatus,
  generateTraceNodeId,
  TraceStatus,
} from '@/types/trace';

/**
 * Configuration options for the useAgentStream hook.
 */
export interface UseAgentStreamOptions {
  /** WebSocket server URL (defaults to relative ws:// URL) */
  wsUrl?: string;
  /** Reconnection configuration */
  reconnectionConfig?: Partial<ReconnectionConfig>;
  /** Whether to automatically reconnect on disconnect */
  autoReconnect?: boolean;
  /** Callback when a new trace event is received */
  onTraceEvent?: (event: TraceEvent) => void;
  /** Callback when connection state changes */
  onConnectionStateChange?: (state: ConnectionState) => void;
}

/**
 * Calculate the delay for a reconnection attempt using exponential backoff.
 */
function calculateBackoffDelay(attempt: number, config: ReconnectionConfig): number {
  const delay = config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt);
  return Math.min(delay, config.maxDelayMs);
}

/**
 * Convert a TraceEvent to a TraceNode for display.
 */
function eventToTraceNode(event: TraceEvent): TraceNode {
  const status = eventTypeToStatus(event.event_type, event.data);

  let title = 'Agent Activity';
  let agentName = 'Agent';
  let content = '';
  let details: TraceNodeDetails | null = null;

  switch (event.event_type) {
    case EventType.STATE_CHANGE: {
      const chainName = event.data.chain_name as string | undefined;
      const eventStatus = event.data.status as string | undefined;
      title = chainName ? `${chainName} - ${eventStatus || 'in progress'}` : 'State Change';
      agentName = chainName?.split('_')[0] || 'Agent';
      content = eventStatus === 'completed'
        ? 'Step completed successfully'
        : 'Processing...';
      if (event.data.outputs) {
        details = {
          rawEvent: event,
          toolOutput: JSON.stringify(event.data.outputs, null, 2),
        };
      }
      break;
    }
    case EventType.THOUGHT: {
      title = 'Thinking';
      agentName = (event.data.model as string) || 'LLM';
      content = `Processing with ${agentName}...`;
      details = {
        model: event.data.model as string | undefined,
        tokenCount: event.data.prompt_count as number | undefined,
        rawEvent: event,
      };
      break;
    }
    case EventType.TOOL_CALL: {
      const toolName = event.data.tool_name as string | undefined;
      const toolStatus = event.data.status as string | undefined;
      title = toolName ? `Tool: ${toolName}` : 'Tool Call';
      agentName = 'Executor';
      content = toolStatus === 'completed'
        ? 'Tool execution completed'
        : `Executing ${toolName || 'tool'}...`;
      details = {
        toolName,
        toolInput: event.data.input ? { input: event.data.input } : undefined,
        toolOutput: event.data.output_preview as string | undefined,
        rawEvent: event,
      };
      break;
    }
    case EventType.ERROR: {
      title = 'Error';
      agentName = 'System';
      content = (event.data.error_message as string) || 'An error occurred';
      details = {
        errorMessage: event.data.error_message as string | undefined,
        rawEvent: event,
      };
      break;
    }
    case EventType.CONNECTED: {
      title = 'Connected';
      agentName = 'System';
      content = (event.data.message as string) || 'Connected to workflow';
      break;
    }
    case EventType.DISCONNECTED: {
      title = 'Disconnected';
      agentName = 'System';
      content = 'Connection closed';
      break;
    }
  }

  return {
    id: generateTraceNodeId(),
    title,
    agentName,
    status,
    timestamp: new Date(event.timestamp),
    duration: null,
    content,
    details,
    parentId: null,
    childIds: [],
  };
}

/**
 * React hook for connecting to the agent trace WebSocket stream.
 *
 * @param options - Configuration options
 * @returns State and actions for managing the stream
 *
 * @example
 * ```tsx
 * const { state, actions } = useAgentStream({
 *   wsUrl: 'ws://localhost:8000',
 *   onTraceEvent: (event) => console.log('Event:', event),
 * });
 *
 * // Connect to a workflow
 * actions.connect('workflow-123', 'auth-token');
 *
 * // Access trace nodes
 * state.traceNodes.map(node => <TraceNode key={node.id} node={node} />);
 * ```
 */
export function useAgentStream(options: UseAgentStreamOptions = {}): {
  state: AgentStreamState;
  actions: AgentStreamActions;
} {
  const {
    wsUrl,
    reconnectionConfig: userReconnectionConfig,
    autoReconnect = true,
    onTraceEvent,
    onConnectionStateChange,
  } = options;

  const reconnectionConfig: ReconnectionConfig = {
    ...DEFAULT_RECONNECTION_CONFIG,
    ...userReconnectionConfig,
  };

  // State
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);
  const [traceNodes, setTraceNodes] = useState<TraceNode[]>([]);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);

  // Refs for cleanup and reconnection
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tokenRef = useRef<string | undefined>(undefined);
  const mountedRef = useRef(true);

  // Update connection state and notify callback
  const updateConnectionState = useCallback((newState: ConnectionState) => {
    if (!mountedRef.current) return;
    setConnectionState(newState);
    onConnectionStateChange?.(newState);
  }, [onConnectionStateChange]);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback((newWorkflowId: string, token?: string) => {
    if (!mountedRef.current) return;

    cleanup();
    setWorkflowId(newWorkflowId);
    setError(null);
    setRetryAttempt(0);
    tokenRef.current = token;
    updateConnectionState(ConnectionState.CONNECTING);

    // Determine WebSocket URL
    let baseUrl = wsUrl;
    if (!baseUrl) {
      // Default to current host with ws/wss protocol
      const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:'
        ? 'wss:'
        : 'ws:';
      const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
      baseUrl = `${protocol}//${host}`;
    }

    const url = new URL(`/ws/workflow/${newWorkflowId}`, baseUrl);
    if (token) {
      url.searchParams.set('token', token);
    }

    try {
      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        updateConnectionState(ConnectionState.CONNECTED);
        setRetryAttempt(0);
        setError(null);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const traceEvent = JSON.parse(event.data) as TraceEvent;
          onTraceEvent?.(traceEvent);

          // Convert event to trace node and add to list
          const node = eventToTraceNode(traceEvent);
          setTraceNodes((prev) => [...prev, node]);
        } catch (parseError) {
          console.error('Failed to parse WebSocket message:', parseError);
        }
      };

      ws.onerror = (wsError) => {
        if (!mountedRef.current) return;
        console.error('WebSocket error:', wsError);
        setError('WebSocket connection error');
        updateConnectionState(ConnectionState.ERROR);
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;

        wsRef.current = null;

        // Handle normal closure
        if (event.code === 1000 || event.code === 1001) {
          updateConnectionState(ConnectionState.DISCONNECTED);
          return;
        }

        // Handle abnormal closure with reconnection
        if (autoReconnect && retryAttempt < reconnectionConfig.maxRetries) {
          updateConnectionState(ConnectionState.RECONNECTING);
          const delay = calculateBackoffDelay(retryAttempt, reconnectionConfig);

          reconnectTimeoutRef.current = setTimeout(() => {
            if (!mountedRef.current) return;
            setRetryAttempt((prev) => prev + 1);
            connect(newWorkflowId, tokenRef.current);
          }, delay);
        } else {
          setError(
            retryAttempt >= reconnectionConfig.maxRetries
              ? 'Maximum reconnection attempts reached'
              : 'Connection closed'
          );
          updateConnectionState(ConnectionState.ERROR);
        }
      };
    } catch (connectError) {
      setError('Failed to create WebSocket connection');
      updateConnectionState(ConnectionState.ERROR);
    }
  }, [wsUrl, autoReconnect, reconnectionConfig, onTraceEvent, updateConnectionState, cleanup, retryAttempt]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    cleanup();
    setWorkflowId(null);
    setRetryAttempt(0);
    setError(null);
    updateConnectionState(ConnectionState.DISCONNECTED);
  }, [cleanup, updateConnectionState]);

  // Clear trace nodes
  const clearTrace = useCallback(() => {
    setTraceNodes([]);
  }, []);

  // Load persisted trace data
  const loadPersistedTrace = useCallback((nodes: TraceNode[]) => {
    setTraceNodes(nodes);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [cleanup]);

  // Heartbeat to keep connection alive
  useEffect(() => {
    if (connectionState !== ConnectionState.CONNECTED || !wsRef.current) {
      return;
    }

    const heartbeatInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000); // Send ping every 30 seconds

    return () => clearInterval(heartbeatInterval);
  }, [connectionState]);

  return {
    state: {
      connectionState,
      traceNodes,
      retryAttempt,
      error,
      workflowId,
    },
    actions: {
      connect,
      disconnect,
      clearTrace,
      loadPersistedTrace,
    },
  };
}

export default useAgentStream;
