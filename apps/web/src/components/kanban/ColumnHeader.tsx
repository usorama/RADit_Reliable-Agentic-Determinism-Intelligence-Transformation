'use client';

/**
 * ColumnHeader component for Kanban board columns.
 *
 * Features:
 * - Column title
 * - Task count badge
 * - Progress percentage indicator
 * - Dark mode compatible
 * - WCAG 2.1 AA accessible
 */

import type { ColumnHeaderProps } from '@/types/kanban';
import { COLUMN_STYLES, KanbanColumn } from '@/types/kanban';

/**
 * Get the accent color for a column based on its status.
 */
function getColumnAccent(columnId: KanbanColumn): string {
  return COLUMN_STYLES[columnId]?.accent ?? 'border-gray-400';
}

/**
 * Get the header background color for a column.
 */
function getColumnHeaderBg(columnId: KanbanColumn): string {
  return COLUMN_STYLES[columnId]?.header ?? 'bg-gray-100 dark:bg-gray-800';
}

/**
 * Progress bar component.
 */
function ProgressBar({ percent }: { percent: number }) {
  // Clamp between 0 and 100
  const clampedPercent = Math.max(0, Math.min(100, percent));

  return (
    <div
      className="h-1 w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden"
      role="progressbar"
      aria-valuenow={clampedPercent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${clampedPercent.toFixed(0)}% complete`}
    >
      <div
        className="h-full bg-blue-500 dark:bg-blue-400 transition-all duration-300"
        style={{ width: `${clampedPercent}%` }}
      />
    </div>
  );
}

/**
 * Count badge component.
 */
function CountBadge({ count }: { count: number }) {
  return (
    <span
      className="
        inline-flex items-center justify-center
        min-w-[1.5rem] h-6
        px-2
        bg-gray-200 dark:bg-gray-700
        text-gray-700 dark:text-gray-300
        text-sm font-medium
        rounded-full
      "
      aria-label={`${count} task${count !== 1 ? 's' : ''}`}
    >
      {count}
    </span>
  );
}

/**
 * ColumnHeader component for Kanban board columns.
 */
export function ColumnHeader({ column, className = '' }: ColumnHeaderProps) {
  const headerBg = getColumnHeaderBg(column.id);
  const accentColor = getColumnAccent(column.id);

  return (
    <header
      className={`
        ${headerBg}
        border-t-4 ${accentColor}
        rounded-t-lg
        p-3
        ${className}
      `}
    >
      {/* Title row */}
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
          {column.title}
        </h2>
        <CountBadge count={column.count} />
      </div>

      {/* Progress bar */}
      {column.count > 0 && (
        <div className="flex items-center gap-2">
          <ProgressBar percent={column.progressPercent} />
          <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
            {column.progressPercent.toFixed(0)}%
          </span>
        </div>
      )}
    </header>
  );
}

export default ColumnHeader;
