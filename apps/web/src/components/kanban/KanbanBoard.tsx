'use client';

/**
 * KanbanBoard component for displaying a workflow task visualization.
 *
 * Features:
 * - 6 columns: Backlog, Planning, Coding, Validating, Deploying, Done
 * - Task cards with priority indicators
 * - Real-time updates via WebSocket
 * - Connection status indicator
 * - Click to select task for details
 * - Dark mode compatible
 * - WCAG 2.1 AA accessible
 * - Responsive design
 */

import { useCallback, useState } from 'react';
import type { KanbanBoardProps, KanbanTask, ColumnInfo } from '@/types/kanban';
import { COLUMN_ORDER, COLUMN_STYLES, ConnectionState } from '@/types/kanban';
import { useKanban } from '@/hooks/useKanban';
import { ColumnHeader } from './ColumnHeader';
import { TaskCard } from './TaskCard';

/**
 * Connection status indicator component.
 */
function ConnectionStatusIndicator({
  state,
  retryAttempt,
  onRefresh,
}: {
  state: ConnectionState;
  retryAttempt: number;
  onRefresh?: () => void;
}) {
  const statusConfig: Record<ConnectionState, { color: string; text: string; icon: React.ReactNode }> = {
    [ConnectionState.CONNECTED]: {
      color: 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-300',
      text: 'Connected',
      icon: (
        <span className="w-2 h-2 rounded-full bg-green-500" aria-hidden="true" />
      ),
    },
    [ConnectionState.CONNECTING]: {
      color: 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300',
      text: 'Connecting...',
      icon: (
        <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" aria-hidden="true" />
      ),
    },
    [ConnectionState.RECONNECTING]: {
      color: 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300',
      text: `Reconnecting (${retryAttempt}/5)...`,
      icon: (
        <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" aria-hidden="true" />
      ),
    },
    [ConnectionState.DISCONNECTED]: {
      color: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300',
      text: 'Disconnected',
      icon: (
        <span className="w-2 h-2 rounded-full bg-gray-500" aria-hidden="true" />
      ),
    },
    [ConnectionState.ERROR]: {
      color: 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300',
      text: 'Connection Error',
      icon: (
        <span className="w-2 h-2 rounded-full bg-red-500" aria-hidden="true" />
      ),
    },
  };

  const config = statusConfig[state];

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${config.color}`}
      role="status"
      aria-live="polite"
    >
      {config.icon}
      <span>{config.text}</span>
      {(state === ConnectionState.DISCONNECTED || state === ConnectionState.ERROR) && onRefresh && (
        <button
          onClick={onRefresh}
          className="ml-1 hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded"
          aria-label="Retry connection"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Empty column placeholder.
 */
function EmptyColumnPlaceholder() {
  return (
    <div className="flex items-center justify-center h-24 text-gray-400 dark:text-gray-600 text-sm italic">
      No tasks
    </div>
  );
}

/**
 * Loading skeleton for a task card.
 */
function TaskCardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="h-3 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
        <div className="h-4 w-8 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
      <div className="h-4 w-full bg-gray-200 dark:bg-gray-700 rounded mb-2" />
      <div className="h-3 w-3/4 bg-gray-200 dark:bg-gray-700 rounded" />
    </div>
  );
}

/**
 * Loading skeleton for a column.
 */
function ColumnSkeleton() {
  return (
    <div className="flex flex-col min-w-[280px] max-w-[320px] bg-gray-50 dark:bg-gray-900 rounded-lg">
      <div className="p-3 border-t-4 border-gray-300 dark:border-gray-600 rounded-t-lg">
        <div className="flex items-center justify-between mb-2">
          <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-6 w-8 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
        </div>
      </div>
      <div className="flex-1 p-2 space-y-2">
        <TaskCardSkeleton />
        <TaskCardSkeleton />
      </div>
    </div>
  );
}

/**
 * Single column component.
 */
function KanbanColumn({
  column,
  tasks,
  allTasks,
  selectedTaskId,
  onTaskClick,
  isLoading,
}: {
  column: ColumnInfo;
  tasks: KanbanTask[];
  allTasks: KanbanTask[];
  selectedTaskId: string | null;
  onTaskClick: (taskId: string) => void;
  isLoading: boolean;
}) {
  const columnStyle = COLUMN_STYLES[column.id];

  return (
    <section
      className={`
        flex flex-col
        min-w-[280px] max-w-[320px] w-full
        bg-gray-50 dark:bg-gray-900
        rounded-lg
        shadow-sm
      `}
      aria-labelledby={`column-${column.id}-title`}
    >
      <ColumnHeader column={column} />

      <div
        className="flex-1 p-2 space-y-2 overflow-y-auto max-h-[calc(100vh-240px)]"
        role="list"
        aria-label={`${column.title} tasks`}
      >
        {isLoading ? (
          <>
            <TaskCardSkeleton />
            <TaskCardSkeleton />
          </>
        ) : tasks.length === 0 ? (
          <EmptyColumnPlaceholder />
        ) : (
          tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              allTasks={allTasks}
              onTaskClick={onTaskClick}
              isSelected={task.id === selectedTaskId}
            />
          ))
        )}
      </div>
    </section>
  );
}

/**
 * Board statistics bar.
 */
function StatsBar({
  stats,
  className = '',
}: {
  stats: { totalTasks: number; completedTasks: number; inProgressTasks: number; blockedTasks: number; completionPercent: number };
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-4 text-sm ${className}`}>
      <div className="flex items-center gap-1">
        <span className="text-gray-500 dark:text-gray-400">Total:</span>
        <span className="font-medium text-gray-900 dark:text-gray-100">{stats.totalTasks}</span>
      </div>
      <div className="flex items-center gap-1">
        <span className="w-2 h-2 rounded-full bg-green-500" aria-hidden="true" />
        <span className="text-gray-500 dark:text-gray-400">Done:</span>
        <span className="font-medium text-gray-900 dark:text-gray-100">{stats.completedTasks}</span>
      </div>
      <div className="flex items-center gap-1">
        <span className="w-2 h-2 rounded-full bg-blue-500" aria-hidden="true" />
        <span className="text-gray-500 dark:text-gray-400">In Progress:</span>
        <span className="font-medium text-gray-900 dark:text-gray-100">{stats.inProgressTasks}</span>
      </div>
      {stats.blockedTasks > 0 && (
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500" aria-hidden="true" />
          <span className="text-gray-500 dark:text-gray-400">Blocked:</span>
          <span className="font-medium text-red-600 dark:text-red-400">{stats.blockedTasks}</span>
        </div>
      )}
      <div className="flex items-center gap-1">
        <span className="text-gray-500 dark:text-gray-400">Progress:</span>
        <span className="font-medium text-gray-900 dark:text-gray-100">{stats.completionPercent.toFixed(0)}%</span>
      </div>
    </div>
  );
}

/**
 * Main KanbanBoard component.
 */
export function KanbanBoard({ workflowId, token, className = '' }: KanbanBoardProps) {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const { state, actions } = useKanban({
    workflowId,
    token,
    autoReconnect: true,
  });

  const {
    columns,
    tasksByColumn,
    tasks,
    stats,
    isLoading,
    error,
    connectionState,
    retryAttempt,
  } = state;

  const handleTaskClick = useCallback((taskId: string) => {
    setSelectedTaskId((prev) => (prev === taskId ? null : taskId));
  }, []);

  const handleRefresh = useCallback(async () => {
    await actions.forceRefresh();
  }, [actions]);

  return (
    <div
      className={`flex flex-col h-full ${className}`}
      role="region"
      aria-label="Kanban Board"
    >
      {/* Header bar */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Task Board
        </h1>
        <div className="flex items-center gap-4">
          <StatsBar stats={stats} className="hidden md:flex" />
          <ConnectionStatusIndicator
            state={connectionState}
            retryAttempt={retryAttempt}
            onRefresh={handleRefresh}
          />
        </div>
      </header>

      {/* Mobile stats */}
      <div className="md:hidden px-4 py-2 bg-gray-50 dark:bg-gray-900">
        <StatsBar stats={stats} className="flex-wrap" />
      </div>

      {/* Error message */}
      {error && (
        <div
          className="mx-4 mt-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm"
          role="alert"
        >
          {error}
          <button
            onClick={handleRefresh}
            className="ml-2 underline hover:no-underline focus:outline-none"
          >
            Try again
          </button>
        </div>
      )}

      {/* Board columns */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden p-4">
        <div className="flex gap-4 h-full min-w-max">
          {COLUMN_ORDER.map((columnId) => {
            const column = columns.find((c) => c.id === columnId);
            const columnTasks = tasksByColumn[columnId] || [];

            if (!column) {
              return <ColumnSkeleton key={columnId} />;
            }

            return (
              <KanbanColumn
                key={columnId}
                column={column}
                tasks={columnTasks}
                allTasks={tasks}
                selectedTaskId={selectedTaskId}
                onTaskClick={handleTaskClick}
                isLoading={isLoading}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default KanbanBoard;
