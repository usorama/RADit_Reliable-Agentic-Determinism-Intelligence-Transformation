'use client';

/**
 * TaskCard component for displaying individual task cards on the Kanban board.
 *
 * Features:
 * - Priority indicator (P0=red, P1=yellow, P2=blue)
 * - Dependency status (blocked/ready/has_dependents)
 * - Assigned agent badge
 * - Click to expand/show details
 * - Truncated description with full text on hover
 * - Dark mode compatible
 * - WCAG 2.1 AA accessible
 */

import { useCallback, useState } from 'react';
import type { KanbanTask, TaskCardProps, DependencyStatus, TaskPriority } from '@/types/kanban';
import { PRIORITY_COLORS, getTaskDependencyStatus, truncateText } from '@/types/kanban';

/**
 * Icon for blocked tasks (chain/link icon).
 */
function BlockedIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
      />
    </svg>
  );
}

/**
 * Icon for tasks with dependents (arrow pointing down).
 */
function HasDependentsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 13l-7 7-7-7m14-8l-7 7-7-7"
      />
    </svg>
  );
}

/**
 * Icon for ready tasks (checkmark).
 */
function ReadyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 13l4 4L19 7"
      />
    </svg>
  );
}

/**
 * Icon for agent assignment.
 */
function AgentIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  );
}

/**
 * Priority badge component.
 */
function PriorityBadge({ priority }: { priority: TaskPriority }) {
  const colors = PRIORITY_COLORS[priority];

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-semibold ${colors.bg} ${colors.text}`}
      role="status"
      aria-label={`Priority: ${priority}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} aria-hidden="true" />
      {priority}
    </span>
  );
}

/**
 * Dependency status indicator component.
 */
function DependencyIndicator({ status }: { status: DependencyStatus }) {
  const config: Record<DependencyStatus, { icon: React.ReactNode; label: string; color: string }> = {
    blocked: {
      icon: <BlockedIcon className="w-3.5 h-3.5" />,
      label: 'Blocked by dependencies',
      color: 'text-red-500 dark:text-red-400',
    },
    has_dependents: {
      icon: <HasDependentsIcon className="w-3.5 h-3.5" />,
      label: 'Has dependent tasks',
      color: 'text-yellow-500 dark:text-yellow-400',
    },
    ready: {
      icon: <ReadyIcon className="w-3.5 h-3.5" />,
      label: 'Ready to start',
      color: 'text-green-500 dark:text-green-400',
    },
  };

  const { icon, label, color } = config[status];

  return (
    <span
      className={`inline-flex items-center ${color}`}
      title={label}
      aria-label={label}
    >
      {icon}
    </span>
  );
}

/**
 * TaskCard component for displaying individual task cards.
 */
export function TaskCard({
  task,
  onTaskClick,
  isSelected = false,
  className = '',
  allTasks = [],
}: TaskCardProps & { allTasks?: KanbanTask[] }) {
  const [isHovered, setIsHovered] = useState(false);

  const dependencyStatus = getTaskDependencyStatus(task, allTasks);
  const colors = PRIORITY_COLORS[task.priority];
  const truncatedDescription = truncateText(task.description, 80);
  const hasFullDescription = task.description.length > 80;

  const handleClick = useCallback(() => {
    onTaskClick?.(task.id);
  }, [task.id, onTaskClick]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleClick();
      }
    },
    [handleClick]
  );

  return (
    <article
      className={`
        relative
        bg-white dark:bg-gray-800
        border ${colors.border}
        rounded-lg
        shadow-sm
        hover:shadow-md
        transition-all duration-200
        cursor-pointer
        ${isSelected ? 'ring-2 ring-blue-500 dark:ring-blue-400' : ''}
        ${className}
      `}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      role="button"
      tabIndex={0}
      aria-label={`Task: ${task.title}`}
      aria-selected={isSelected}
    >
      {/* Priority stripe */}
      <div
        className={`absolute top-0 left-0 w-1 h-full rounded-l-lg ${colors.dot}`}
        aria-hidden="true"
      />

      <div className="p-3 pl-4">
        {/* Header: Task ID and Priority */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-mono text-gray-500 dark:text-gray-400">
            {task.id}
          </span>
          <PriorityBadge priority={task.priority} />
        </div>

        {/* Title */}
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1 line-clamp-2">
          {task.title}
        </h3>

        {/* Description (truncated) */}
        <p
          className="text-xs text-gray-600 dark:text-gray-300 mb-2"
          title={hasFullDescription ? task.description : undefined}
        >
          {isHovered && hasFullDescription ? task.description : truncatedDescription}
        </p>

        {/* Footer: Status indicators and agent */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DependencyIndicator status={dependencyStatus} />
            {task.dependencies.length > 0 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {task.dependencies.length} dep{task.dependencies.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {task.assignedAgent && (
            <div className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
              <AgentIcon className="w-3.5 h-3.5" />
              <span className="truncate max-w-[80px]">{task.assignedAgent}</span>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

export default TaskCard;
