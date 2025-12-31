/**
 * TypeScript types for Kanban board visualization.
 *
 * These types support the workflow task visualization with:
 * - 6 workflow columns (Backlog -> Done)
 * - Task cards with priority indicators
 * - Real-time WebSocket updates
 * - Dependency tracking
 */

/**
 * Kanban column identifiers representing workflow stages.
 */
export enum KanbanColumn {
  BACKLOG = 'backlog',
  PLANNING = 'planning',
  CODING = 'coding',
  VALIDATING = 'validating',
  DEPLOYING = 'deploying',
  DONE = 'done',
}

/**
 * Priority levels for tasks.
 * P0 = Critical (red), P1 = High (yellow), P2 = Normal (blue)
 */
export type TaskPriority = 'P0' | 'P1' | 'P2';

/**
 * Dependency status for a task.
 */
export type DependencyStatus = 'blocked' | 'ready' | 'has_dependents';

/**
 * A single task on the Kanban board.
 */
export interface KanbanTask {
  /** Unique task identifier */
  id: string;
  /** Short title for the task */
  title: string;
  /** Full description of the task */
  description: string;
  /** Current column/stage */
  column: KanbanColumn;
  /** Task priority (P0 = critical, P1 = high, P2 = normal) */
  priority: TaskPriority;
  /** Agent currently assigned to this task (if any) */
  assignedAgent?: string;
  /** List of task IDs this task depends on */
  dependencies: string[];
  /** List of task IDs that depend on this task */
  dependents: string[];
  /** ISO timestamp of last update */
  updatedAt: string;
  /** ISO timestamp of creation */
  createdAt: string;
}

/**
 * Column metadata for display.
 */
export interface ColumnInfo {
  /** Column identifier */
  id: KanbanColumn;
  /** Display title */
  title: string;
  /** Number of tasks in this column */
  count: number;
  /** Progress percentage (0-100) */
  progressPercent: number;
}

/**
 * Overall board statistics.
 */
export interface KanbanStats {
  /** Total number of tasks */
  totalTasks: number;
  /** Number of completed tasks */
  completedTasks: number;
  /** Number of in-progress tasks */
  inProgressTasks: number;
  /** Number of blocked tasks */
  blockedTasks: number;
  /** Overall completion percentage (0-100) */
  completionPercent: number;
}

/**
 * Full Kanban board state.
 */
export interface KanbanBoardState {
  /** Column metadata */
  columns: ColumnInfo[];
  /** All tasks on the board */
  tasks: KanbanTask[];
  /** Board statistics */
  stats: KanbanStats;
  /** Last update timestamp */
  lastUpdated: string;
}

/**
 * WebSocket event for Kanban updates.
 */
export interface KanbanUpdateEvent {
  /** Event type */
  type: 'kanban_update';
  /** Task that was updated */
  taskId: string;
  /** New column for the task */
  newColumn: KanbanColumn;
  /** Previous column (if moving) */
  previousColumn?: KanbanColumn;
  /** New assigned agent (if any) */
  assignedAgent?: string;
  /** ISO timestamp */
  timestamp: string;
}

/**
 * Request to update a task's position.
 */
export interface KanbanMoveRequest {
  /** Target column */
  column: KanbanColumn;
  /** New priority (optional) */
  priority?: TaskPriority;
}

/**
 * Props for the KanbanBoard component.
 */
export interface KanbanBoardProps {
  /** Workflow ID to display */
  workflowId: string;
  /** Auth token for WebSocket (optional, uses session if not provided) */
  token?: string;
  /** Custom class name for styling */
  className?: string;
}

/**
 * Props for the TaskCard component.
 */
export interface TaskCardProps {
  /** The task to display */
  task: KanbanTask;
  /** Callback when task is clicked for details */
  onTaskClick?: (taskId: string) => void;
  /** Whether the card is currently selected */
  isSelected?: boolean;
  /** Custom class name for styling */
  className?: string;
}

/**
 * Props for the ColumnHeader component.
 */
export interface ColumnHeaderProps {
  /** Column information */
  column: ColumnInfo;
  /** Custom class name for styling */
  className?: string;
}

/**
 * State returned by useKanban hook.
 */
export interface UseKanbanState {
  /** Column metadata */
  columns: ColumnInfo[];
  /** All tasks keyed by column */
  tasksByColumn: Record<KanbanColumn, KanbanTask[]>;
  /** All tasks */
  tasks: KanbanTask[];
  /** Board statistics */
  stats: KanbanStats;
  /** Whether WebSocket is connected */
  isConnected: boolean;
  /** Whether data is loading */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** Last update timestamp */
  lastUpdated: string | null;
}

/**
 * Actions returned by useKanban hook.
 */
export interface UseKanbanActions {
  /** Refresh the board data */
  refreshBoard: () => Promise<void>;
  /** Move a task to a new column */
  moveTask: (taskId: string, newColumn: KanbanColumn, priority?: TaskPriority) => Promise<void>;
  /** Get a specific task by ID */
  getTask: (taskId: string) => KanbanTask | undefined;
}

/**
 * Color mapping for priority levels.
 */
export const PRIORITY_COLORS: Record<TaskPriority, { bg: string; text: string; border: string; dot: string }> = {
  P0: {
    bg: 'bg-red-50 dark:bg-red-900/20',
    text: 'text-red-700 dark:text-red-300',
    border: 'border-red-300 dark:border-red-700',
    dot: 'bg-red-500',
  },
  P1: {
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    text: 'text-yellow-700 dark:text-yellow-300',
    border: 'border-yellow-300 dark:border-yellow-700',
    dot: 'bg-yellow-500',
  },
  P2: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-700 dark:text-blue-300',
    border: 'border-blue-300 dark:border-blue-700',
    dot: 'bg-blue-500',
  },
};

/**
 * Color and styling for each column.
 */
export const COLUMN_STYLES: Record<KanbanColumn, { header: string; accent: string }> = {
  [KanbanColumn.BACKLOG]: {
    header: 'bg-gray-100 dark:bg-gray-800',
    accent: 'border-gray-400',
  },
  [KanbanColumn.PLANNING]: {
    header: 'bg-blue-100 dark:bg-blue-900/30',
    accent: 'border-blue-500',
  },
  [KanbanColumn.CODING]: {
    header: 'bg-yellow-100 dark:bg-yellow-900/30',
    accent: 'border-yellow-500',
  },
  [KanbanColumn.VALIDATING]: {
    header: 'bg-purple-100 dark:bg-purple-900/30',
    accent: 'border-purple-500',
  },
  [KanbanColumn.DEPLOYING]: {
    header: 'bg-orange-100 dark:bg-orange-900/30',
    accent: 'border-orange-500',
  },
  [KanbanColumn.DONE]: {
    header: 'bg-green-100 dark:bg-green-900/30',
    accent: 'border-green-500',
  },
};

/**
 * Human-readable column titles.
 */
export const COLUMN_TITLES: Record<KanbanColumn, string> = {
  [KanbanColumn.BACKLOG]: 'Backlog',
  [KanbanColumn.PLANNING]: 'Planning',
  [KanbanColumn.CODING]: 'Coding',
  [KanbanColumn.VALIDATING]: 'Validating',
  [KanbanColumn.DEPLOYING]: 'Deploying',
  [KanbanColumn.DONE]: 'Done',
};

/**
 * Order of columns for display.
 */
export const COLUMN_ORDER: KanbanColumn[] = [
  KanbanColumn.BACKLOG,
  KanbanColumn.PLANNING,
  KanbanColumn.CODING,
  KanbanColumn.VALIDATING,
  KanbanColumn.DEPLOYING,
  KanbanColumn.DONE,
];

/**
 * Helper to get dependency status of a task.
 */
export function getTaskDependencyStatus(task: KanbanTask, allTasks: KanbanTask[]): DependencyStatus {
  // Check if any dependencies are not done
  const hasBlockingDeps = task.dependencies.some((depId) => {
    const dep = allTasks.find((t) => t.id === depId);
    return dep && dep.column !== KanbanColumn.DONE;
  });

  if (hasBlockingDeps) {
    return 'blocked';
  }

  if (task.dependents.length > 0) {
    return 'has_dependents';
  }

  return 'ready';
}

/**
 * Helper to truncate text with ellipsis.
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 3)}...`;
}

// -----------------------------------------------------------------------------
// Task Detail Panel Types (KANBAN-002)
// -----------------------------------------------------------------------------

/**
 * Types of activities that can occur on a task.
 */
export type TaskActivityType = 'status_change' | 'commit' | 'agent_action';

/**
 * Represents an activity event on a task.
 */
export interface TaskActivity {
  /** Unique identifier for this activity */
  id: string;
  /** ISO timestamp when the activity occurred */
  timestamp: string;
  /** Type of activity */
  type: TaskActivityType;
  /** Human-readable description */
  description: string;
  /** Additional activity-specific details */
  details?: Record<string, unknown>;
}

/**
 * Props for the TaskDetailPanel component.
 */
export interface TaskDetailPanelProps {
  /** The task to display (null to hide panel) */
  task: KanbanTask | null;
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback when the panel is closed */
  onClose: () => void;
  /** Activity history for this task */
  activities: TaskActivity[];
  /** Artifacts produced by this task */
  artifacts: string[];
  /** Workflow ID for linking to agent trace */
  workflowId?: string;
}

/**
 * Props for the ActivityTimeline component.
 */
export interface ActivityTimelineProps {
  /** List of activities to display */
  activities: TaskActivity[];
  /** Maximum number of activities to show (0 = unlimited) */
  maxItems?: number;
  /** Whether to show timestamps in relative format */
  relativeTime?: boolean;
}

// -----------------------------------------------------------------------------
// Connection Status Types (KANBAN-003)
// -----------------------------------------------------------------------------

/**
 * Connection state for WebSocket.
 */
export enum ConnectionState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  ERROR = 'ERROR',
}

/**
 * Props for the ConnectionStatus component.
 */
export interface ConnectionStatusProps {
  /** Current connection state */
  state: ConnectionState;
  /** Last successful sync timestamp */
  lastSync: string | null;
  /** Current retry attempt (if reconnecting) */
  retryAttempt?: number;
  /** Maximum retry attempts (for display) */
  maxRetries?: number;
  /** Callback when refresh is clicked */
  onRefresh?: () => void;
}

// -----------------------------------------------------------------------------
// WebSocket Event Types (KANBAN-003)
// -----------------------------------------------------------------------------

/**
 * Types of kanban-specific WebSocket events.
 */
export enum KanbanEventType {
  /** Single task was updated */
  TASK_UPDATE = 'kanban_update',
  /** Full board synchronization */
  FULL_SYNC = 'kanban_sync',
  /** Agent started/completed work on a task */
  AGENT_ACTIVITY = 'kanban_agent_activity',
}

/**
 * Payload for a task update event.
 */
export interface TaskUpdatePayload {
  /** The updated task */
  task: KanbanTask;
  /** Previous column (for undo) */
  previousColumn?: KanbanColumn;
  /** Source of the update (user, agent, system) */
  source: 'user' | 'agent' | 'system';
}

/**
 * Payload for a full sync event.
 */
export interface FullSyncPayload {
  /** All tasks in the workflow */
  tasks: KanbanTask[];
  /** Server timestamp for synchronization */
  serverTimestamp: string;
}

/**
 * Payload for an agent activity event.
 */
export interface AgentActivityPayload {
  /** Task ID the agent is working on */
  taskId: string;
  /** Agent name */
  agentName: string;
  /** Activity type */
  activity: 'started' | 'completed' | 'failed' | 'paused';
  /** Additional details */
  details?: Record<string, unknown>;
}

/**
 * A kanban WebSocket event.
 */
export interface KanbanWebSocketEvent {
  /** Event type */
  type: KanbanEventType;
  /** Workflow ID this event belongs to */
  workflowId: string;
  /** Event payload (varies by type) */
  payload: TaskUpdatePayload | FullSyncPayload | AgentActivityPayload;
  /** ISO timestamp when the event occurred */
  timestamp: string;
}

// -----------------------------------------------------------------------------
// useKanban Hook Extended Types (KANBAN-003)
// -----------------------------------------------------------------------------

/**
 * Reconnection configuration.
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
 * Default reconnection configuration.
 */
export const DEFAULT_RECONNECTION_CONFIG: ReconnectionConfig = {
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  maxRetries: 5,
  backoffMultiplier: 2.0,
};

/**
 * Configuration for the useKanban hook.
 */
export interface UseKanbanOptions {
  /** WebSocket server URL (defaults to relative ws:// URL) */
  wsUrl?: string;
  /** Reconnection configuration */
  reconnectionConfig?: Partial<ReconnectionConfig>;
  /** Whether to automatically reconnect on disconnect */
  autoReconnect?: boolean;
  /** Callback when a kanban event is received */
  onEvent?: (event: KanbanWebSocketEvent) => void;
  /** Callback when connection state changes */
  onConnectionStateChange?: (state: ConnectionState) => void;
  /** Initial tasks to load */
  initialTasks?: KanbanTask[];
  /** Workflow ID to connect to */
  workflowId?: string;
  /** Auth token for WebSocket */
  token?: string;
}

/**
 * Extended state returned by useKanban hook with WebSocket support.
 */
export interface UseKanbanStateExtended extends UseKanbanState {
  /** WebSocket connection state */
  connectionState: ConnectionState;
  /** Current retry attempt (0 if not retrying) */
  retryAttempt: number;
  /** Whether an optimistic update is pending server confirmation */
  hasPendingUpdate: boolean;
  /** Currently selected task (for detail panel) */
  selectedTask: KanbanTask | null;
  /** Activities for the selected task */
  selectedTaskActivities: TaskActivity[];
}

/**
 * Extended actions returned by useKanban hook with WebSocket support.
 */
export interface UseKanbanActionsExtended extends UseKanbanActions {
  /** Connect to WebSocket */
  connect: (workflowId: string, token?: string) => void;
  /** Disconnect from WebSocket */
  disconnect: () => void;
  /** Select a task to show in detail panel */
  selectTask: (taskId: string | null) => void;
  /** Force refresh from server */
  forceRefresh: () => Promise<void>;
}

// -----------------------------------------------------------------------------
// Activity Styling
// -----------------------------------------------------------------------------

/**
 * Icons for activity types.
 */
export const ACTIVITY_ICONS: Record<TaskActivityType, string> = {
  status_change: 'arrow-path',
  commit: 'code-bracket',
  agent_action: 'cpu-chip',
};

/**
 * Colors for activity types.
 */
export const ACTIVITY_COLORS: Record<TaskActivityType, { bg: string; text: string; border: string }> = {
  status_change: {
    bg: 'bg-blue-100 dark:bg-blue-900/20',
    text: 'text-blue-700 dark:text-blue-300',
    border: 'border-blue-300 dark:border-blue-700',
  },
  commit: {
    bg: 'bg-purple-100 dark:bg-purple-900/20',
    text: 'text-purple-700 dark:text-purple-300',
    border: 'border-purple-300 dark:border-purple-700',
  },
  agent_action: {
    bg: 'bg-green-100 dark:bg-green-900/20',
    text: 'text-green-700 dark:text-green-300',
    border: 'border-green-300 dark:border-green-700',
  },
};

/**
 * Connection state colors for display.
 */
export const CONNECTION_STATE_COLORS: Record<ConnectionState, { bg: string; text: string; dot: string }> = {
  [ConnectionState.CONNECTED]: {
    bg: 'bg-green-100 dark:bg-green-900/20',
    text: 'text-green-700 dark:text-green-300',
    dot: 'bg-green-500',
  },
  [ConnectionState.CONNECTING]: {
    bg: 'bg-yellow-100 dark:bg-yellow-900/20',
    text: 'text-yellow-700 dark:text-yellow-300',
    dot: 'bg-yellow-500 animate-pulse',
  },
  [ConnectionState.RECONNECTING]: {
    bg: 'bg-yellow-100 dark:bg-yellow-900/20',
    text: 'text-yellow-700 dark:text-yellow-300',
    dot: 'bg-yellow-500 animate-pulse',
  },
  [ConnectionState.DISCONNECTED]: {
    bg: 'bg-gray-100 dark:bg-gray-800',
    text: 'text-gray-700 dark:text-gray-300',
    dot: 'bg-gray-500',
  },
  [ConnectionState.ERROR]: {
    bg: 'bg-red-100 dark:bg-red-900/20',
    text: 'text-red-700 dark:text-red-300',
    dot: 'bg-red-500',
  },
};
