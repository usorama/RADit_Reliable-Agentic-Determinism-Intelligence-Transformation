'use client';

/**
 * TaskTreeNode - Individual task node in the hierarchical task list.
 *
 * Features:
 * - Task type badge with icon
 * - Complexity indicator
 * - Estimated hours display
 * - Dependency indicators
 * - Expandable details (future enhancement)
 *
 * @example
 * ```tsx
 * <TaskTreeNode
 *   task={task}
 *   isExpanded={false}
 *   onToggle={handleToggle}
 *   level={1}
 * />
 * ```
 */

import React, { useCallback } from 'react';
import { ComplexityBadge } from './ComplexityBadge';
import { Task, TaskTreeNodeProps, TASK_TYPE_CONFIG } from '../../types/tasks';

// -----------------------------------------------------------------------------
// Task Type Badge Component
// -----------------------------------------------------------------------------

interface TaskTypeBadgeProps {
  type: Task['type'];
  size?: 'sm' | 'md';
}

function TaskTypeBadge({ type, size = 'sm' }: TaskTypeBadgeProps) {
  const config = TASK_TYPE_CONFIG[type];
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium ${config.color} ${sizeClasses}`}
      title={config.label}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}

// -----------------------------------------------------------------------------
// Dependency Indicator Component
// -----------------------------------------------------------------------------

interface DependencyIndicatorProps {
  count: number;
}

function DependencyIndicator({ count }: DependencyIndicatorProps) {
  if (count === 0) return null;

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-gray-600 bg-gray-100 dark:bg-gray-700 dark:text-gray-300 rounded-full"
      title={`Depends on ${count} task${count > 1 ? 's' : ''}`}
    >
      <svg
        className="w-3 h-3"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M13 10V3L4 14h7v7l9-11h-7z"
        />
      </svg>
      <span>{count}</span>
    </span>
  );
}

// -----------------------------------------------------------------------------
// Estimated Hours Display
// -----------------------------------------------------------------------------

interface EstimatedHoursProps {
  hours: number;
}

function EstimatedHours({ hours }: EstimatedHoursProps) {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"
      title={`Estimated ${hours} hour${hours !== 1 ? 's' : ''}`}
    >
      <svg
        className="w-3 h-3"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span>{hours}h</span>
    </span>
  );
}

// -----------------------------------------------------------------------------
// TaskTreeNode Component
// -----------------------------------------------------------------------------

export function TaskTreeNode({
  task,
  isExpanded,
  onToggle,
  level = 0,
  showDependencies = true,
}: TaskTreeNodeProps) {
  const handleClick = useCallback(() => {
    onToggle(task.id);
  }, [task.id, onToggle]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onToggle(task.id);
      }
    },
    [task.id, onToggle]
  );

  // Calculate indentation based on level
  const indentClass = level > 0 ? `ml-${Math.min(level * 4, 12)}` : '';

  return (
    <div
      className={`group border-l-2 border-transparent hover:border-blue-400 transition-colors ${indentClass}`}
    >
      <div
        className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer rounded-r-md transition-colors"
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
      >
        {/* Expand/Collapse Chevron */}
        <button
          type="button"
          className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex-shrink-0"
          onClick={(e) => {
            e.stopPropagation();
            onToggle(task.id);
          }}
          aria-label={isExpanded ? 'Collapse task details' : 'Expand task details'}
        >
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${
              isExpanded ? 'rotate-90' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>

        {/* Task Type Badge */}
        <TaskTypeBadge type={task.type} />

        {/* Task Description */}
        <span className="flex-1 text-sm text-gray-900 dark:text-white truncate">
          {task.description}
        </span>

        {/* Metadata Badges */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Dependency Count */}
          {showDependencies && task.dependencies.length > 0 && (
            <DependencyIndicator count={task.dependencies.length} />
          )}

          {/* Estimated Hours */}
          {task.estimatedHours !== undefined && task.estimatedHours > 0 && (
            <EstimatedHours hours={task.estimatedHours} />
          )}

          {/* Complexity Badge */}
          <ComplexityBadge complexity={task.complexity} size="sm" />
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="ml-8 px-3 py-2 bg-gray-50 dark:bg-gray-800/30 rounded-md mb-1">
          <dl className="space-y-1 text-sm">
            <div className="flex">
              <dt className="w-24 text-gray-500 dark:text-gray-400">Task ID:</dt>
              <dd className="text-gray-900 dark:text-gray-100 font-mono text-xs">
                {task.id}
              </dd>
            </div>

            <div className="flex">
              <dt className="w-24 text-gray-500 dark:text-gray-400">Type:</dt>
              <dd className="text-gray-900 dark:text-gray-100">
                {TASK_TYPE_CONFIG[task.type].label}
              </dd>
            </div>

            <div className="flex">
              <dt className="w-24 text-gray-500 dark:text-gray-400">Complexity:</dt>
              <dd className="text-gray-900 dark:text-gray-100 capitalize">
                {task.complexity}
              </dd>
            </div>

            {task.estimatedHours !== undefined && (
              <div className="flex">
                <dt className="w-24 text-gray-500 dark:text-gray-400">Estimate:</dt>
                <dd className="text-gray-900 dark:text-gray-100">
                  {task.estimatedHours} hour{task.estimatedHours !== 1 ? 's' : ''}
                </dd>
              </div>
            )}

            {task.dependencies.length > 0 && (
              <div className="flex">
                <dt className="w-24 text-gray-500 dark:text-gray-400">Depends on:</dt>
                <dd className="text-gray-900 dark:text-gray-100">
                  <ul className="list-none space-y-0.5">
                    {task.dependencies.map((depId) => (
                      <li key={depId} className="font-mono text-xs">
                        {depId}
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}

export default TaskTreeNode;
