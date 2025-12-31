'use client';

/**
 * TaskList - Hierarchical display of workflow tasks for review.
 *
 * Features:
 * - Hierarchical display: Phase -> Story -> Task
 * - Expandable/collapsible tree structure
 * - Dependency indicators
 * - Complexity badges per task
 * - "Approve and Begin" button
 * - "Reject" button with feedback option
 *
 * @example
 * ```tsx
 * <TaskList
 *   workflowId={workflowId}
 *   onApprove={handleApprove}
 *   onReject={handleReject}
 * />
 * ```
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ExpandableSection } from './ExpandableSection';
import { TaskTreeNode } from './TaskTreeNode';
import { useTasks } from '../../hooks/useTasks';
import {
  Phase,
  Story,
  TaskListProps,
  PRIORITY_CONFIG,
} from '../../types/tasks';

// -----------------------------------------------------------------------------
// Story Section Component
// -----------------------------------------------------------------------------

interface StorySectionProps {
  story: Story;
  expandedTasks: Set<string>;
  onToggleTask: (taskId: string) => void;
}

function StorySection({ story, expandedTasks, onToggleTask }: StorySectionProps) {
  const priorityConfig = PRIORITY_CONFIG[story.priority];
  const totalEstimatedHours = story.tasks.reduce(
    (sum, task) => sum + (task.estimatedHours || 0),
    0
  );

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mb-3">
      {/* Story Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800">
        <div className="flex items-center gap-3">
          {/* Priority Badge */}
          <span
            className={`px-2 py-0.5 text-xs font-medium rounded-full ${priorityConfig.color}`}
          >
            {story.priority}
          </span>

          {/* Story Title */}
          <h4 className="text-sm font-medium text-gray-900 dark:text-white">
            {story.title}
          </h4>

          {/* Task Count */}
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {story.tasks.length} task{story.tasks.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Estimated Hours */}
        {totalEstimatedHours > 0 && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            ~{totalEstimatedHours.toFixed(1)}h total
          </span>
        )}
      </div>

      {/* Tasks List */}
      <div className="p-2 bg-white dark:bg-gray-900">
        {story.tasks.map((task) => (
          <TaskTreeNode
            key={task.id}
            task={task}
            isExpanded={expandedTasks.has(task.id)}
            onToggle={onToggleTask}
            level={0}
            showDependencies={true}
          />
        ))}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Phase Section Component
// -----------------------------------------------------------------------------

interface PhaseSectionProps {
  phase: Phase;
  expandedTasks: Set<string>;
  onToggleTask: (taskId: string) => void;
  defaultExpanded?: boolean;
}

function PhaseSection({
  phase,
  expandedTasks,
  onToggleTask,
  defaultExpanded = true,
}: PhaseSectionProps) {
  const totalTasks = phase.stories.reduce(
    (sum, story) => sum + story.tasks.length,
    0
  );

  return (
    <ExpandableSection
      title={phase.name}
      badge={totalTasks}
      defaultExpanded={defaultExpanded}
      icon={
        <svg
          className="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
      }
      className="mb-4"
    >
      {/* Phase Description */}
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {phase.description}
      </p>

      {/* Stories */}
      {phase.stories.map((story) => (
        <StorySection
          key={story.id}
          story={story}
          expandedTasks={expandedTasks}
          onToggleTask={onToggleTask}
        />
      ))}
    </ExpandableSection>
  );
}

// -----------------------------------------------------------------------------
// Reject Modal Component
// -----------------------------------------------------------------------------

interface RejectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (feedback: string) => void;
  isLoading: boolean;
}

function RejectModal({ isOpen, onClose, onConfirm, isLoading }: RejectModalProps) {
  const [feedback, setFeedback] = useState('');

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (feedback.trim()) {
        onConfirm(feedback.trim());
      }
    },
    [feedback, onConfirm]
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Reject Task List
        </h3>

        <form onSubmit={handleSubmit}>
          <label
            htmlFor="reject-feedback"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
          >
            Please provide feedback for why you&apos;re rejecting the task list:
          </label>

          <textarea
            id="reject-feedback"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
            rows={4}
            placeholder="Describe what changes you'd like to see..."
            required
            disabled={isLoading}
          />

          <div className="flex justify-end gap-3 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLoading || !feedback.trim()}
            >
              {isLoading ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Summary Stats Component
// -----------------------------------------------------------------------------

interface SummaryStatsProps {
  totalPhases: number;
  totalStories: number;
  totalTasks: number;
  totalEstimatedHours: number;
}

function SummaryStats({
  totalPhases,
  totalStories,
  totalTasks,
  totalEstimatedHours,
}: SummaryStatsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-center">
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {totalPhases}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Phase{totalPhases !== 1 ? 's' : ''}
        </div>
      </div>

      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-center">
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {totalStories}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Stor{totalStories !== 1 ? 'ies' : 'y'}
        </div>
      </div>

      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-center">
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {totalTasks}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Task{totalTasks !== 1 ? 's' : ''}
        </div>
      </div>

      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-center">
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {totalEstimatedHours.toFixed(1)}h
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Estimated
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// TaskList Component
// -----------------------------------------------------------------------------

export function TaskList({ workflowId, onApprove, onReject }: TaskListProps) {
  const { state, fetchTasks, approveTasks, rejectTasks, clearError } =
    useTasks(workflowId);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);

  // Fetch tasks on mount
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Toggle task expansion
  const handleToggleTask = useCallback((taskId: string) => {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  }, []);

  // Handle approve
  const handleApprove = useCallback(async () => {
    const success = await approveTasks();
    if (success) {
      onApprove();
    }
  }, [approveTasks, onApprove]);

  // Handle reject confirmation
  const handleRejectConfirm = useCallback(
    async (feedback: string) => {
      const success = await rejectTasks(feedback);
      if (success) {
        setIsRejectModalOpen(false);
        onReject(feedback);
      }
    },
    [rejectTasks, onReject]
  );

  // Calculate summary stats
  const summaryStats = React.useMemo(() => {
    if (!state.data) {
      return {
        totalPhases: 0,
        totalStories: 0,
        totalTasks: 0,
        totalEstimatedHours: 0,
      };
    }

    const totalEstimatedHours = state.data.tasks.reduce(
      (sum, task) => sum + (task.estimatedHours || 0),
      0
    );

    return {
      totalPhases: state.data.phases.length,
      totalStories: state.data.stories.length,
      totalTasks: state.data.tasks.length,
      totalEstimatedHours,
    };
  }, [state.data]);

  // Loading state
  if (state.isLoading && !state.data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        <span className="ml-3 text-gray-600 dark:text-gray-400">
          Loading tasks...
        </span>
      </div>
    );
  }

  // Error state
  if (state.error && !state.data) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <svg
            className="w-5 h-5 text-red-600 dark:text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <span className="text-red-800 dark:text-red-200">{state.error}</span>
        </div>
        <button
          onClick={() => {
            clearError();
            fetchTasks();
          }}
          className="mt-3 text-sm text-red-600 dark:text-red-400 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  // No data state
  if (!state.data) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        No tasks available for review.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Task List Review
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Review the decomposed tasks before execution begins.
          </p>
        </div>
      </div>

      {/* Summary Stats */}
      <SummaryStats {...summaryStats} />

      {/* Error Banner (if error with data) */}
      {state.error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 flex items-center justify-between">
          <span className="text-red-800 dark:text-red-200 text-sm">
            {state.error}
          </span>
          <button
            onClick={clearError}
            className="text-red-600 dark:text-red-400 hover:text-red-700"
            aria-label="Dismiss error"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Phases */}
      <div className="space-y-4">
        {state.data.phases.map((phase, index) => (
          <PhaseSection
            key={phase.id}
            phase={phase}
            expandedTasks={expandedTasks}
            onToggleTask={handleToggleTask}
            defaultExpanded={index === 0}
          />
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setIsRejectModalOpen(true)}
          className="px-6 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 border border-red-200 dark:border-red-800 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={state.isReviewing}
        >
          Reject
        </button>
        <button
          onClick={handleApprove}
          className="px-6 py-2.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          disabled={state.isReviewing}
        >
          {state.isReviewing ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Processing...
            </>
          ) : (
            <>
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              Approve and Begin
            </>
          )}
        </button>
      </div>

      {/* Reject Modal */}
      <RejectModal
        isOpen={isRejectModalOpen}
        onClose={() => setIsRejectModalOpen(false)}
        onConfirm={handleRejectConfirm}
        isLoading={state.isReviewing}
      />
    </div>
  );
}

export default TaskList;
