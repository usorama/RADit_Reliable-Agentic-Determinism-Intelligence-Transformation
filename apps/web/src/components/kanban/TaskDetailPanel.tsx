'use client';

/**
 * TaskDetailPanel component for displaying detailed task information.
 *
 * Features:
 * - Slide-out panel from the right side
 * - Full task information display
 * - Activity timeline
 * - Dependencies and artifacts list
 * - Link to agent trace view
 * - Close button and escape key to dismiss
 * - Responsive design with dark mode support
 */

import React, { useCallback, useEffect, useId } from 'react';
import Link from 'next/link';
import type { TaskDetailPanelProps } from '@/types/kanban';
import { PRIORITY_COLORS, COLUMN_TITLES, KanbanColumn } from '@/types/kanban';
import { ActivityTimeline } from './ActivityTimeline';

// -----------------------------------------------------------------------------
// Icons
// -----------------------------------------------------------------------------

function CloseIcon({ className }: { className?: string }) {
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
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  );
}

function DependencyIcon({ className }: { className?: string }) {
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
        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
      />
    </svg>
  );
}

function ArtifactIcon({ className }: { className?: string }) {
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
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
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

function ExternalLinkIcon({ className }: { className?: string }) {
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
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

/**
 * Format a date for display.
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

// -----------------------------------------------------------------------------
// Section Components
// -----------------------------------------------------------------------------

interface SectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

function Section({ title, icon, children }: SectionProps) {
  return (
    <div className="py-4 border-b border-gray-200 dark:border-gray-700 last:border-b-0">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white mb-3">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  );
}

// -----------------------------------------------------------------------------
// TaskDetailPanel Component
// -----------------------------------------------------------------------------

export function TaskDetailPanel({
  task,
  isOpen,
  onClose,
  activities,
  artifacts,
  workflowId,
}: TaskDetailPanelProps) {
  const panelId = useId();

  // Handle escape key
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        onClose();
      }
    },
    [isOpen, onClose]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Prevent body scroll when panel is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!task) {
    return null;
  }

  const priorityColors = PRIORITY_COLORS[task.priority];
  const columnTitle = COLUMN_TITLES[task.column as KanbanColumn] || task.column;

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black transition-opacity duration-300 ${
          isOpen ? 'bg-opacity-50' : 'bg-opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        id={panelId}
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-[480px] bg-white dark:bg-gray-900 shadow-xl transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${panelId}-title`}
      >
        <div className="h-full flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex-shrink-0 px-4 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 text-xs font-mono font-medium bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                  {task.id}
                </span>
                <span
                  className={`px-2 py-0.5 text-xs font-medium rounded ${priorityColors.bg} ${priorityColors.text}`}
                >
                  {task.priority}
                </span>
              </div>
              <button
                onClick={onClose}
                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                aria-label="Close panel"
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>
            <h2
              id={`${panelId}-title`}
              className="mt-2 text-lg font-semibold text-gray-900 dark:text-white"
            >
              {task.title}
            </h2>
            <div className="mt-2 flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
              <span>
                Status: <span className="font-medium">{columnTitle}</span>
              </span>
              <span>Updated: {formatDate(task.updatedAt)}</span>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-4">
            {/* Description */}
            <Section
              title="Description"
              icon={<ArtifactIcon className="h-4 w-4 text-gray-500" />}
            >
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {task.description || 'No description provided.'}
              </p>
            </Section>

            {/* Assigned Agent */}
            {task.assignedAgent && (
              <Section
                title="Assigned Agent"
                icon={<AgentIcon className="h-4 w-4 text-gray-500" />}
              >
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1.5 text-sm font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-lg">
                    {task.assignedAgent}
                  </span>
                </div>
              </Section>
            )}

            {/* Dependencies */}
            <Section
              title="Dependencies"
              icon={<DependencyIcon className="h-4 w-4 text-gray-500" />}
            >
              {task.dependencies.length > 0 ? (
                <ul className="space-y-2">
                  {task.dependencies.map((depId) => (
                    <li key={depId}>
                      <span className="inline-flex items-center px-2 py-1 text-xs font-mono bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
                        {depId}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No dependencies
                </p>
              )}
            </Section>

            {/* Dependents */}
            {task.dependents && task.dependents.length > 0 && (
              <Section
                title="Dependent Tasks"
                icon={<DependencyIcon className="h-4 w-4 text-gray-500" />}
              >
                <ul className="space-y-2">
                  {task.dependents.map((depId) => (
                    <li key={depId}>
                      <span className="inline-flex items-center px-2 py-1 text-xs font-mono bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
                        {depId}
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Artifacts */}
            <Section
              title="Artifacts"
              icon={<ArtifactIcon className="h-4 w-4 text-gray-500" />}
            >
              {artifacts.length > 0 ? (
                <ul className="space-y-2">
                  {artifacts.map((artifact, index) => (
                    <li key={index}>
                      <span className="inline-flex items-center px-2 py-1 text-xs font-mono bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded">
                        {artifact}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No artifacts produced yet
                </p>
              )}
            </Section>

            {/* Activity Timeline */}
            <Section
              title="Activity"
              icon={
                <svg
                  className="h-4 w-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
            >
              <ActivityTimeline activities={activities} maxItems={10} relativeTime />
            </Section>
          </div>

          {/* Footer */}
          <div className="flex-shrink-0 px-4 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
            <div className="flex items-center justify-between">
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Created: {formatDate(task.createdAt)}
              </div>
              {workflowId && (
                <Link
                  href={`/trace/${workflowId}?task=${task.id}`}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                >
                  View Agent Trace
                  <ExternalLinkIcon className="h-4 w-4" />
                </Link>
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

export default TaskDetailPanel;
