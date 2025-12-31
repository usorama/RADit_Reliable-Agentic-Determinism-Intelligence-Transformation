'use client';

/**
 * React hook for managing Kanban board state with WebSocket support.
 *
 * Features:
 * - Real-time updates via WebSocket connection
 * - Optimistic updates with rollback on failure
 * - Automatic reconnection with exponential backoff
 * - Task selection for detail panel
 * - Activity tracking for selected tasks
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  KanbanTask,
  TaskActivity,
  KanbanWebSocketEvent,
  UseKanbanOptions,
  UseKanbanState,
  UseKanbanActions,
  UseKanbanStateExtended,
  UseKanbanActionsExtended,
  TaskUpdatePayload,
  FullSyncPayload,
  AgentActivityPayload,
  ColumnInfo,
  KanbanStats,
  ReconnectionConfig,
} from '@/types/kanban';
import {
  KanbanColumn,
  KanbanEventType,
  ConnectionState,
  COLUMN_ORDER,
  COLUMN_TITLES,
  DEFAULT_RECONNECTION_CONFIG,
} from '@/types/kanban';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface PendingUpdate {
  taskId: string;
  previousColumn: KanbanColumn;
  newColumn: KanbanColumn;
  timestamp: number;
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

/**
 * Calculate the delay for a reconnection attempt using exponential backoff.
 */
function calculateBackoffDelay(attempt: number, config: ReconnectionConfig): number {
  const delay = config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt);
  return Math.min(delay, config.maxDelayMs);
}

/**
 * Group tasks by column.
 */
function groupTasksByColumn(tasks: KanbanTask[]): Record<KanbanColumn, KanbanTask[]> {
  const result: Record<KanbanColumn, KanbanTask[]> = {
    [KanbanColumn.BACKLOG]: [],
    [KanbanColumn.PLANNING]: [],
    [KanbanColumn.CODING]: [],
    [KanbanColumn.VALIDATING]: [],
    [KanbanColumn.DEPLOYING]: [],
    [KanbanColumn.DONE]: [],
  };

  for (const task of tasks) {
    const column = task.column as KanbanColumn;
    if (result[column]) {
      result[column].push(task);
    } else {
      // Default to backlog if unknown column
      result[KanbanColumn.BACKLOG].push(task);
    }
  }

  return result;
}

/**
 * Calculate board statistics.
 */
function calculateStats(tasks: KanbanTask[]): KanbanStats {
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter((t) => t.column === KanbanColumn.DONE).length;
  const inProgressTasks = tasks.filter(
    (t) =>
      t.column === KanbanColumn.PLANNING ||
      t.column === KanbanColumn.CODING ||
      t.column === KanbanColumn.VALIDATING ||
      t.column === KanbanColumn.DEPLOYING
  ).length;
  const blockedTasks = 0; // TODO: Implement blocking logic based on dependencies

  return {
    totalTasks,
    completedTasks,
    inProgressTasks,
    blockedTasks,
    completionPercent: totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0,
  };
}

/**
 * Build column info from tasks.
 */
function buildColumns(tasks: KanbanTask[]): ColumnInfo[] {
  const tasksByColumn = groupTasksByColumn(tasks);
  const totalTasks = tasks.length;

  return COLUMN_ORDER.map((columnId) => {
    const columnTasks = tasksByColumn[columnId] || [];
    return {
      id: columnId,
      title: COLUMN_TITLES[columnId],
      count: columnTasks.length,
      progressPercent: totalTasks > 0 ? Math.round((columnTasks.length / totalTasks) * 100) : 0,
    };
  });
}

/**
 * Generate a unique activity ID.
 */
function generateActivityId(): string {
  return `activity-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// -----------------------------------------------------------------------------
// Hook
// -----------------------------------------------------------------------------

export function useKanban(options: UseKanbanOptions = {}): {
  state: UseKanbanStateExtended;
  actions: UseKanbanActionsExtended;
} {
  const {
    wsUrl,
    reconnectionConfig: userReconnectionConfig,
    autoReconnect = true,
    onEvent,
    onConnectionStateChange,
    initialTasks = [],
    workflowId: initialWorkflowId,
    token: initialToken,
  } = options;

  const reconnectionConfig: ReconnectionConfig = {
    ...DEFAULT_RECONNECTION_CONFIG,
    ...userReconnectionConfig,
  };

  // Core state
  const [tasks, setTasks] = useState<KanbanTask[]>(initialTasks);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [activities, setActivities] = useState<Map<string, TaskActivity[]>>(new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  // WebSocket state
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.DISCONNECTED
  );
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [workflowId, setWorkflowId] = useState<string | null>(initialWorkflowId || null);

  // Pending updates for optimistic UI
  const [pendingUpdates, setPendingUpdates] = useState<PendingUpdate[]>([]);

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tokenRef = useRef<string | undefined>(initialToken);
  const mountedRef = useRef(true);

  // Derived state
  const tasksByColumn = useMemo(() => groupTasksByColumn(tasks), [tasks]);
  const columns = useMemo(() => buildColumns(tasks), [tasks]);
  const stats = useMemo(() => calculateStats(tasks), [tasks]);
  const selectedTask = useMemo(
    () => (selectedTaskId ? tasks.find((t) => t.id === selectedTaskId) || null : null),
    [selectedTaskId, tasks]
  );
  const selectedTaskActivities = useMemo(
    () => (selectedTaskId ? activities.get(selectedTaskId) || [] : []),
    [selectedTaskId, activities]
  );
  const hasPendingUpdate = pendingUpdates.length > 0;

  // Update connection state and notify callback
  const updateConnectionState = useCallback(
    (newState: ConnectionState) => {
      if (!mountedRef.current) return;
      setConnectionState(newState);
      onConnectionStateChange?.(newState);
    },
    [onConnectionStateChange]
  );

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

  // Handle incoming WebSocket events
  const handleWebSocketEvent = useCallback(
    (event: KanbanWebSocketEvent) => {
      if (!mountedRef.current) return;

      onEvent?.(event);

      switch (event.type) {
        case KanbanEventType.TASK_UPDATE: {
          const payload = event.payload as TaskUpdatePayload;
          setTasks((prev) => {
            const index = prev.findIndex((t) => t.id === payload.task.id);
            if (index >= 0) {
              const updated = [...prev];
              updated[index] = payload.task;
              return updated;
            }
            return [...prev, payload.task];
          });

          // Remove any pending updates for this task
          setPendingUpdates((prev) => prev.filter((u) => u.taskId !== payload.task.id));

          // Add activity for the task
          setActivities((prev) => {
            const taskActivities = prev.get(payload.task.id) || [];
            const newActivity: TaskActivity = {
              id: generateActivityId(),
              timestamp: event.timestamp,
              type: 'status_change',
              description: `Status changed to ${COLUMN_TITLES[payload.task.column as KanbanColumn]}`,
              details: {
                previousColumn: payload.previousColumn,
                source: payload.source,
              },
            };
            return new Map(prev).set(payload.task.id, [newActivity, ...taskActivities]);
          });

          setLastUpdated(event.timestamp);
          break;
        }

        case KanbanEventType.FULL_SYNC: {
          const payload = event.payload as FullSyncPayload;
          setTasks(payload.tasks);
          setPendingUpdates([]);
          setLastUpdated(payload.serverTimestamp);
          break;
        }

        case KanbanEventType.AGENT_ACTIVITY: {
          const payload = event.payload as AgentActivityPayload;

          // Add activity for the task
          setActivities((prev) => {
            const taskActivities = prev.get(payload.taskId) || [];
            const newActivity: TaskActivity = {
              id: generateActivityId(),
              timestamp: event.timestamp,
              type: 'agent_action',
              description: `${payload.agentName} ${payload.activity} work on this task`,
              details: payload.details,
            };
            return new Map(prev).set(payload.taskId, [newActivity, ...taskActivities]);
          });

          // Update task assignedAgent if agent started work
          if (payload.activity === 'started') {
            setTasks((prev) =>
              prev.map((t) =>
                t.id === payload.taskId ? { ...t, assignedAgent: payload.agentName } : t
              )
            );
          }

          setLastUpdated(event.timestamp);
          break;
        }
      }
    },
    [onEvent]
  );

  // Connect to WebSocket
  const connect = useCallback(
    (newWorkflowId: string, token?: string) => {
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
        const protocol =
          typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
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
          setLastUpdated(new Date().toISOString());
        };

        ws.onmessage = (event) => {
          if (!mountedRef.current) return;
          try {
            const wsEvent = JSON.parse(event.data) as KanbanWebSocketEvent;
            handleWebSocketEvent(wsEvent);
          } catch (parseError) {
            console.error('Failed to parse WebSocket message:', parseError);
          }
        };

        ws.onerror = () => {
          if (!mountedRef.current) return;
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
    },
    [
      wsUrl,
      autoReconnect,
      reconnectionConfig,
      handleWebSocketEvent,
      updateConnectionState,
      cleanup,
      retryAttempt,
    ]
  );

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    cleanup();
    setWorkflowId(null);
    setRetryAttempt(0);
    setError(null);
    updateConnectionState(ConnectionState.DISCONNECTED);
  }, [cleanup, updateConnectionState]);

  // Select a task
  const selectTask = useCallback((taskId: string | null) => {
    setSelectedTaskId(taskId);
  }, []);

  // Move a task with optimistic update
  const moveTask = useCallback(
    async (taskId: string, newColumn: KanbanColumn, priority?: string) => {
      const task = tasks.find((t) => t.id === taskId);
      if (!task) return;

      const previousColumn = task.column as KanbanColumn;
      if (previousColumn === newColumn) return;

      // Optimistic update
      const pendingUpdate: PendingUpdate = {
        taskId,
        previousColumn,
        newColumn,
        timestamp: Date.now(),
      };
      setPendingUpdates((prev) => [...prev, pendingUpdate]);

      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                column: newColumn,
                priority: priority ? (priority as KanbanTask['priority']) : t.priority,
                updatedAt: new Date().toISOString(),
              }
            : t
        )
      );

      // Send update via WebSocket if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(
            JSON.stringify({
              type: 'move_task',
              taskId,
              newColumn,
              priority,
            })
          );
        } catch (sendError) {
          // Rollback on send failure
          setTasks((prev) =>
            prev.map((t) =>
              t.id === taskId
                ? {
                    ...t,
                    column: previousColumn,
                  }
                : t
            )
          );
          setPendingUpdates((prev) => prev.filter((u) => u.taskId !== taskId));
          setError('Failed to send update');
        }
      } else {
        // Remove pending update if not connected (update is local only)
        setPendingUpdates((prev) => prev.filter((u) => u.taskId !== taskId));
      }
    },
    [tasks]
  );

  // Refresh board from server
  const refreshBoard = useCallback(async () => {
    if (!workflowId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Request full sync via WebSocket if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'request_sync' }));
      } else {
        // Fall back to HTTP if WebSocket not available
        const response = await fetch(`/api/kanban/${workflowId}`);
        if (!response.ok) {
          throw new Error('Failed to fetch board data');
        }
        const data = await response.json();
        setTasks(data.tasks || []);
        setLastUpdated(new Date().toISOString());
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to refresh board');
    } finally {
      setIsLoading(false);
    }
  }, [workflowId]);

  // Force refresh (same as refreshBoard but with explicit reconnect attempt)
  const forceRefresh = useCallback(async () => {
    if (connectionState === ConnectionState.ERROR || connectionState === ConnectionState.DISCONNECTED) {
      if (workflowId) {
        connect(workflowId, tokenRef.current);
      }
    }
    await refreshBoard();
  }, [connectionState, workflowId, connect, refreshBoard]);

  // Get a specific task
  const getTask = useCallback(
    (taskId: string): KanbanTask | undefined => {
      return tasks.find((t) => t.id === taskId);
    },
    [tasks]
  );

  // Load tasks (for initial data)
  const loadTasks = useCallback((newTasks: KanbanTask[]) => {
    setTasks(newTasks);
    setLastUpdated(new Date().toISOString());
  }, []);

  // Auto-connect if workflowId is provided
  useEffect(() => {
    if (initialWorkflowId && initialToken) {
      connect(initialWorkflowId, initialToken);
    }
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, []);

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

  // Cleanup pending updates that are too old (30 seconds)
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const now = Date.now();
      setPendingUpdates((prev) => prev.filter((u) => now - u.timestamp < 30000));
    }, 10000);

    return () => clearInterval(cleanupInterval);
  }, []);

  return {
    state: {
      columns,
      tasksByColumn,
      tasks,
      stats,
      isConnected: connectionState === ConnectionState.CONNECTED,
      isLoading,
      error,
      lastUpdated,
      connectionState,
      retryAttempt,
      hasPendingUpdate,
      selectedTask,
      selectedTaskActivities,
    },
    actions: {
      connect,
      disconnect,
      selectTask,
      moveTask,
      refreshBoard,
      forceRefresh,
      getTask,
    },
  };
}

export default useKanban;
