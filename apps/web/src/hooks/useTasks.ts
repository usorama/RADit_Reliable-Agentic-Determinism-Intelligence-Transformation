'use client';

/**
 * useTasks Hook - Manages task list fetching and review actions.
 *
 * This hook provides:
 * - Task list fetching for a workflow
 * - Approve/reject task review actions
 * - Loading and error state management
 * - Authenticated API calls
 */

import { useCallback, useState } from 'react';
import { useAuthenticatedFetch } from './useAuth';
import {
  TasksListResponse,
  TaskReviewResponse,
  UseTasksState,
  UseTasksReturn,
} from '../types/tasks';

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// -----------------------------------------------------------------------------
// Initial State
// -----------------------------------------------------------------------------

const initialState: UseTasksState = {
  isLoading: false,
  error: null,
  data: null,
  isReviewing: false,
};

// -----------------------------------------------------------------------------
// useTasks Hook
// -----------------------------------------------------------------------------

/**
 * Hook for managing workflow tasks.
 *
 * @param workflowId - The workflow ID to fetch tasks for
 * @returns UseTasksReturn with state and actions
 *
 * @example
 * ```tsx
 * const { state, fetchTasks, approveTasks, rejectTasks } = useTasks(workflowId);
 *
 * useEffect(() => {
 *   fetchTasks();
 * }, [fetchTasks]);
 *
 * const handleApprove = async () => {
 *   const success = await approveTasks();
 *   if (success) {
 *     onApproved();
 *   }
 * };
 * ```
 */
export function useTasks(workflowId: string): UseTasksReturn {
  const [state, setState] = useState<UseTasksState>(initialState);
  const { fetchWithAuth } = useAuthenticatedFetch();

  /**
   * Fetch tasks for the workflow.
   */
  const fetchTasks = useCallback(async (): Promise<void> => {
    if (!workflowId) {
      setState((prev) => ({
        ...prev,
        error: 'Workflow ID is required',
      }));
      return;
    }

    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: null,
    }));

    try {
      const response = await fetchWithAuth(
        `${API_URL}/api/workflow/${workflowId}/tasks`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Failed to fetch tasks: ${response.status}`
        );
      }

      const data: TasksListResponse = await response.json();

      setState((prev) => ({
        ...prev,
        isLoading: false,
        data,
        error: null,
      }));
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch tasks';
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, [workflowId, fetchWithAuth]);

  /**
   * Approve tasks to start execution.
   *
   * @returns True if approval was successful
   */
  const approveTasks = useCallback(async (): Promise<boolean> => {
    if (!workflowId) {
      setState((prev) => ({
        ...prev,
        error: 'Workflow ID is required',
      }));
      return false;
    }

    setState((prev) => ({
      ...prev,
      isReviewing: true,
      error: null,
    }));

    try {
      const response = await fetchWithAuth(
        `${API_URL}/api/workflow/${workflowId}/tasks-review`,
        {
          method: 'POST',
          body: JSON.stringify({ action: 'approve' }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Failed to approve tasks: ${response.status}`
        );
      }

      const data: TaskReviewResponse = await response.json();

      setState((prev) => ({
        ...prev,
        isReviewing: false,
        error: null,
      }));

      return data.success;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to approve tasks';
      setState((prev) => ({
        ...prev,
        isReviewing: false,
        error: errorMessage,
      }));
      return false;
    }
  }, [workflowId, fetchWithAuth]);

  /**
   * Reject tasks with feedback.
   *
   * @param feedback - Feedback explaining why tasks were rejected
   * @returns True if rejection was successful
   */
  const rejectTasks = useCallback(
    async (feedback: string): Promise<boolean> => {
      if (!workflowId) {
        setState((prev) => ({
          ...prev,
          error: 'Workflow ID is required',
        }));
        return false;
      }

      if (!feedback.trim()) {
        setState((prev) => ({
          ...prev,
          error: 'Feedback is required when rejecting tasks',
        }));
        return false;
      }

      setState((prev) => ({
        ...prev,
        isReviewing: true,
        error: null,
      }));

      try {
        const response = await fetchWithAuth(
          `${API_URL}/api/workflow/${workflowId}/tasks-review`,
          {
            method: 'POST',
            body: JSON.stringify({ action: 'reject', feedback }),
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Failed to reject tasks: ${response.status}`
          );
        }

        const data: TaskReviewResponse = await response.json();

        setState((prev) => ({
          ...prev,
          isReviewing: false,
          error: null,
        }));

        return data.success;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to reject tasks';
        setState((prev) => ({
          ...prev,
          isReviewing: false,
          error: errorMessage,
        }));
        return false;
      }
    },
    [workflowId, fetchWithAuth]
  );

  /**
   * Clear the current error.
   */
  const clearError = useCallback(() => {
    setState((prev) => ({
      ...prev,
      error: null,
    }));
  }, []);

  return {
    state,
    fetchTasks,
    approveTasks,
    rejectTasks,
    clearError,
  };
}

export default useTasks;
