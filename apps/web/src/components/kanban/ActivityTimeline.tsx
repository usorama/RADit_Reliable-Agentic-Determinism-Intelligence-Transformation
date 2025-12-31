'use client';

/**
 * ActivityTimeline component for displaying task activity history.
 *
 * Features:
 * - Chronological list of task activities
 * - Icon and color coding by activity type
 * - Relative or absolute timestamps
 * - Expandable details for each activity
 * - Responsive design with dark mode support
 */

import React, { useMemo, useCallback, useState } from 'react';
import type { ActivityTimelineProps, TaskActivity, TaskActivityType } from '@/types/kanban';
import { ACTIVITY_COLORS } from '@/types/kanban';

// -----------------------------------------------------------------------------
// Icons
// -----------------------------------------------------------------------------

function StatusChangeIcon({ className }: { className?: string }) {
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
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

function CommitIcon({ className }: { className?: string }) {
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
        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
      />
    </svg>
  );
}

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
        d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"
      />
    </svg>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
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
        d="M19 9l-7 7-7-7"
      />
    </svg>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

/**
 * Get the icon component for an activity type.
 */
function getActivityIcon(type: TaskActivityType): React.ReactNode {
  const iconClass = 'h-4 w-4';
  switch (type) {
    case 'status_change':
      return <StatusChangeIcon className={iconClass} />;
    case 'commit':
      return <CommitIcon className={iconClass} />;
    case 'agent_action':
      return <AgentIcon className={iconClass} />;
    default:
      return <StatusChangeIcon className={iconClass} />;
  }
}

/**
 * Format a timestamp as relative time (e.g., "2 hours ago").
 */
function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) {
    return 'just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  } else {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  }
}

/**
 * Format a timestamp as absolute time.
 */
function formatAbsoluteTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/**
 * Get a human-readable label for an activity type.
 */
function getActivityTypeLabel(type: TaskActivityType): string {
  switch (type) {
    case 'status_change':
      return 'Status Change';
    case 'commit':
      return 'Commit';
    case 'agent_action':
      return 'Agent Action';
    default:
      return 'Activity';
  }
}

// -----------------------------------------------------------------------------
// ActivityItem Component
// -----------------------------------------------------------------------------

interface ActivityItemProps {
  activity: TaskActivity;
  relativeTime: boolean;
  isLast: boolean;
}

function ActivityItem({ activity, relativeTime, isLast }: ActivityItemProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const colors = ACTIVITY_COLORS[activity.type];
  const hasDetails = activity.details && Object.keys(activity.details).length > 0;

  const toggleExpand = useCallback(() => {
    if (hasDetails) {
      setIsExpanded((prev) => !prev);
    }
  }, [hasDetails]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleExpand();
      }
    },
    [toggleExpand]
  );

  return (
    <li className="relative pb-4">
      {/* Connecting line */}
      {!isLast && (
        <span
          className="absolute left-3 top-8 -ml-px h-full w-0.5 bg-gray-200 dark:bg-gray-700"
          aria-hidden="true"
        />
      )}

      <div className="relative flex items-start space-x-3">
        {/* Icon */}
        <div
          className={`relative flex h-6 w-6 items-center justify-center rounded-full ${colors.bg} ${colors.text} ring-2 ring-white dark:ring-gray-900`}
        >
          {getActivityIcon(activity.type)}
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div
            className={`flex items-center justify-between ${
              hasDetails ? 'cursor-pointer' : ''
            }`}
            onClick={toggleExpand}
            onKeyDown={handleKeyDown}
            role={hasDetails ? 'button' : undefined}
            tabIndex={hasDetails ? 0 : undefined}
            aria-expanded={hasDetails ? isExpanded : undefined}
          >
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
              >
                {getActivityTypeLabel(activity.type)}
              </span>
              {hasDetails && (
                <ChevronDownIcon
                  className={`h-4 w-4 text-gray-400 transition-transform duration-200 ${
                    isExpanded ? 'rotate-180' : ''
                  }`}
                />
              )}
            </div>
            <time
              className="flex-shrink-0 text-xs text-gray-500 dark:text-gray-400"
              dateTime={activity.timestamp}
              title={formatAbsoluteTime(activity.timestamp)}
            >
              {relativeTime
                ? formatRelativeTime(activity.timestamp)
                : formatAbsoluteTime(activity.timestamp)}
            </time>
          </div>

          <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">
            {activity.description}
          </p>

          {/* Expandable details */}
          {hasDetails && isExpanded && (
            <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-800 rounded-md">
              <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-x-auto">
                {JSON.stringify(activity.details, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

// -----------------------------------------------------------------------------
// ActivityTimeline Component
// -----------------------------------------------------------------------------

export function ActivityTimeline({
  activities,
  maxItems = 0,
  relativeTime = true,
}: ActivityTimelineProps) {
  // Sort activities by timestamp (most recent first)
  const sortedActivities = useMemo(() => {
    const sorted = [...activities].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
    return maxItems > 0 ? sorted.slice(0, maxItems) : sorted;
  }, [activities, maxItems]);

  if (activities.length === 0) {
    return (
      <div className="text-center py-6 text-gray-500 dark:text-gray-400">
        <StatusChangeIcon className="mx-auto h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No activity yet</p>
      </div>
    );
  }

  return (
    <div className="flow-root">
      <ul role="list" className="-mb-4">
        {sortedActivities.map((activity, index) => (
          <ActivityItem
            key={activity.id}
            activity={activity}
            relativeTime={relativeTime}
            isLast={index === sortedActivities.length - 1}
          />
        ))}
      </ul>
      {maxItems > 0 && activities.length > maxItems && (
        <p className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
          Showing {maxItems} of {activities.length} activities
        </p>
      )}
    </div>
  );
}

export default ActivityTimeline;
