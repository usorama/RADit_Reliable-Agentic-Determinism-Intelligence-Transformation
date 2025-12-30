/**
 * TypeScript types for Agent Trace visualization.
 *
 * These types correspond to the backend WebSocket streaming infrastructure
 * defined in packages/daw-agents/src/daw_agents/api/websocket.py
 */

/**
 * Status values for trace nodes with corresponding colors.
 * - PLANNING: Agent is planning/reasoning (blue)
 * - CODING: Agent is writing code (yellow)
 * - VALIDATING: Agent is running tests/validation (green)
 * - ERROR: An error occurred (red)
 * - PENDING: Waiting to start (gray)
 * - COMPLETED: Successfully finished (green)
 */
export enum TraceStatus {
  PLANNING = 'PLANNING',
  CODING = 'CODING',
  VALIDATING = 'VALIDATING',
  ERROR = 'ERROR',
  PENDING = 'PENDING',
  COMPLETED = 'COMPLETED',
}

/**
 * Event types that can be received from the WebSocket stream.
 * Must match EventType from backend websocket.py
 */
export enum EventType {
  STATE_CHANGE = 'STATE_CHANGE',
  THOUGHT = 'THOUGHT',
  TOOL_CALL = 'TOOL_CALL',
  ERROR = 'ERROR',
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
}

/**
 * A single trace event received from the WebSocket stream.
 * Matches AgentStreamEvent from backend.
 */
export interface TraceEvent {
  /** The type of event */
  event_type: EventType;
  /** ID of the workflow this event belongs to */
  workflow_id: string;
  /** Event-specific data payload */
  data: Record<string, unknown>;
  /** When the event occurred (ISO 8601 format) */
  timestamp: string;
}

/**
 * A node in the trace visualization representing a discrete agent action.
 */
export interface TraceNode {
  /** Unique identifier for this trace node */
  id: string;
  /** Display title for the node (e.g., "Planning", "Writing Test") */
  title: string;
  /** Agent name that generated this trace (e.g., "Planner", "Developer") */
  agentName: string;
  /** Current status of this node */
  status: TraceStatus;
  /** Timestamp when this node was created */
  timestamp: Date;
  /** Duration in milliseconds (null if not completed) */
  duration: number | null;
  /** The main content/reasoning text */
  content: string;
  /** Expandable details (tool inputs/outputs, full reasoning, etc.) */
  details: TraceNodeDetails | null;
  /** Parent node ID for nested traces (null for root nodes) */
  parentId: string | null;
  /** Child node IDs */
  childIds: string[];
}

/**
 * Detailed information for a trace node, shown in expanded view.
 */
export interface TraceNodeDetails {
  /** Tool name if this is a tool call */
  toolName?: string;
  /** Tool input parameters */
  toolInput?: Record<string, unknown>;
  /** Tool output/result */
  toolOutput?: string;
  /** LLM model used */
  model?: string;
  /** Token count for this interaction */
  tokenCount?: number;
  /** Raw event data for debugging */
  rawEvent?: TraceEvent;
  /** Error message if status is ERROR */
  errorMessage?: string;
  /** Stack trace if available */
  stackTrace?: string;
}

/**
 * Connection state for the WebSocket stream.
 */
export enum ConnectionState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  ERROR = 'ERROR',
}

/**
 * Configuration for WebSocket reconnection with exponential backoff.
 * Matches ReconnectionConfig from backend.
 */
export interface ReconnectionConfig {
  /** Initial delay before first retry (ms) */
  initialDelayMs: number;
  /** Maximum delay between retries (ms) */
  maxDelayMs: number;
  /** Maximum number of retry attempts */
  maxRetries: number;
  /** Multiplier for exponential backoff */
  backoffMultiplier: number;
}

/**
 * State of the agent stream hook.
 */
export interface AgentStreamState {
  /** Current connection state */
  connectionState: ConnectionState;
  /** List of trace nodes received */
  traceNodes: TraceNode[];
  /** Current retry attempt (0 if not retrying) */
  retryAttempt: number;
  /** Error message if connectionState is ERROR */
  error: string | null;
  /** Workflow ID currently connected to */
  workflowId: string | null;
}

/**
 * Actions available from the agent stream hook.
 */
export interface AgentStreamActions {
  /** Connect to a workflow's trace stream */
  connect: (workflowId: string, token?: string) => void;
  /** Disconnect from the current stream */
  disconnect: () => void;
  /** Clear all trace nodes */
  clearTrace: () => void;
  /** Load persisted trace data for replay */
  loadPersistedTrace: (nodes: TraceNode[]) => void;
}

/**
 * Props for the AgentTrace component.
 */
export interface AgentTraceProps {
  /** Workflow ID to display traces for */
  workflowId: string;
  /** Auth token for WebSocket connection */
  token?: string;
  /** Whether to auto-scroll to latest entry */
  autoScroll?: boolean;
  /** Persisted trace data for replay mode */
  persistedData?: TraceNode[];
  /** Custom class name for styling */
  className?: string;
  /** Whether the trace is in replay mode (not live) */
  isReplay?: boolean;
}

/**
 * Props for the TraceNode component.
 */
export interface TraceNodeProps {
  /** The trace node to display */
  node: TraceNode;
  /** Whether this node is currently expanded */
  isExpanded: boolean;
  /** Callback when expand/collapse is toggled */
  onToggleExpand: (nodeId: string) => void;
  /** Callback when copy button is clicked */
  onCopy: (content: string) => void;
  /** Nesting level for indentation */
  nestingLevel?: number;
}

/**
 * Map of TraceStatus to Tailwind CSS color classes.
 */
export const STATUS_COLORS: Record<TraceStatus, { bg: string; text: string; border: string }> = {
  [TraceStatus.PLANNING]: {
    bg: 'bg-blue-100',
    text: 'text-blue-800',
    border: 'border-blue-300',
  },
  [TraceStatus.CODING]: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    border: 'border-yellow-300',
  },
  [TraceStatus.VALIDATING]: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-300',
  },
  [TraceStatus.ERROR]: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-300',
  },
  [TraceStatus.PENDING]: {
    bg: 'bg-gray-100',
    text: 'text-gray-800',
    border: 'border-gray-300',
  },
  [TraceStatus.COMPLETED]: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-300',
  },
};

/**
 * Default reconnection configuration.
 */
export const DEFAULT_RECONNECTION_CONFIG: ReconnectionConfig = {
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  maxRetries: 5,
  backoffMultiplier: 2.0,
};

/**
 * Helper function to convert EventType to TraceStatus.
 */
export function eventTypeToStatus(eventType: EventType, data: Record<string, unknown>): TraceStatus {
  switch (eventType) {
    case EventType.STATE_CHANGE: {
      const status = data.status as string | undefined;
      if (status === 'completed') return TraceStatus.COMPLETED;
      const chainName = data.chain_name as string | undefined;
      if (chainName?.toLowerCase().includes('plan')) return TraceStatus.PLANNING;
      if (chainName?.toLowerCase().includes('valid')) return TraceStatus.VALIDATING;
      return TraceStatus.CODING;
    }
    case EventType.THOUGHT:
      return TraceStatus.PLANNING;
    case EventType.TOOL_CALL:
      return TraceStatus.CODING;
    case EventType.ERROR:
      return TraceStatus.ERROR;
    default:
      return TraceStatus.PENDING;
  }
}

/**
 * Helper function to generate a unique trace node ID.
 */
export function generateTraceNodeId(): string {
  return `trace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
