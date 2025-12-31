'use client';

/**
 * usePRD Hook - Fetch and manage PRD (Product Requirements Document) data.
 *
 * This hook provides:
 * - Fetching PRD data from the API by workflow ID
 * - Loading and error state management
 * - Refresh functionality
 * - PRD approval/rejection actions
 *
 * @example
 * ```tsx
 * const { prd, personasFeedback, isLoading, error, approve, reject } = usePRD('workflow-123');
 *
 * if (isLoading) return <Loading />;
 * if (error) return <Error message={error} />;
 *
 * return (
 *   <PlanPresentation
 *     workflowId="workflow-123"
 *     prd={prd}
 *     personasFeedback={personasFeedback}
 *     onApprove={approve}
 *     onReject={reject}
 *   />
 * );
 * ```
 */

import { useCallback, useEffect, useState } from 'react';
import type {
  PRD,
  PersonaFeedback,
  UserStory,
  TechSpec,
} from '../components/plan/PlanPresentation';
import type { ComplexityLevel } from '../components/plan/ComplexityBadge';
import type { PersonaRole } from '../components/plan/PersonaFeedbackCard';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** State for the usePRD hook */
export interface PRDState {
  /** The PRD data */
  prd: PRD | null;
  /** Feedback from roundtable personas */
  personasFeedback: PersonaFeedback[];
  /** Whether data is being loaded */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** Whether the PRD has been approved */
  isApproved: boolean;
  /** Whether the PRD has been rejected */
  isRejected: boolean;
  /** Rejection reason if rejected */
  rejectionReason: string | null;
}

/** Options for the usePRD hook */
export interface UsePRDOptions {
  /** API base URL (defaults to NEXT_PUBLIC_API_URL) */
  apiUrl?: string;
  /** Whether to fetch on mount */
  fetchOnMount?: boolean;
  /** Callback when PRD is successfully fetched */
  onSuccess?: (prd: PRD, feedback: PersonaFeedback[]) => void;
  /** Callback when fetch fails */
  onError?: (error: string) => void;
  /** Callback when PRD is approved */
  onApprove?: () => void;
  /** Callback when PRD is rejected */
  onReject?: (reason: string) => void;
}

/** Return type for the usePRD hook */
export interface UsePRDReturn extends PRDState {
  /** Refresh the PRD data */
  refresh: () => Promise<void>;
  /** Approve the PRD */
  approve: () => Promise<void>;
  /** Reject the PRD with a reason */
  reject: (reason: string) => Promise<void>;
  /** Clear any errors */
  clearError: () => void;
}

// -----------------------------------------------------------------------------
// API Response Types
// -----------------------------------------------------------------------------

/** API response for PRD data */
interface PRDApiResponse {
  workflow_id: string;
  title: string;
  overview: string;
  user_stories: Array<{
    id: string;
    description: string;
    priority: 'P0' | 'P1' | 'P2';
    acceptance_criteria: string[];
  }>;
  tech_specs: Array<{
    component: string;
    description: string;
    complexity: 'low' | 'medium' | 'high' | 'critical';
  }>;
  acceptance_criteria: string[];
  non_functional_requirements: string[];
  persona_feedback: Array<{
    persona: 'CTO' | 'UX Lead' | 'Security Expert';
    feedback: string;
    concerns: string[];
    recommendations: string[];
  }>;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Transform API response to frontend types.
 */
function transformApiResponse(response: PRDApiResponse): {
  prd: PRD;
  personasFeedback: PersonaFeedback[];
} {
  // Transform user stories
  const userStories: UserStory[] = response.user_stories.map((story) => ({
    id: story.id,
    description: story.description,
    priority: story.priority,
    acceptanceCriteria: story.acceptance_criteria,
  }));

  // Transform tech specs
  const techSpecs: TechSpec[] = response.tech_specs.map((spec) => ({
    component: spec.component,
    description: spec.description,
    complexity: spec.complexity as ComplexityLevel,
  }));

  // Transform persona feedback
  const personasFeedback: PersonaFeedback[] = response.persona_feedback.map((fb) => ({
    persona: fb.persona as PersonaRole,
    feedback: fb.feedback,
    concerns: fb.concerns,
    recommendations: fb.recommendations,
  }));

  // Construct PRD
  const prd: PRD = {
    title: response.title,
    overview: response.overview,
    userStories,
    techSpecs,
    acceptanceCriteria: response.acceptance_criteria,
    nonFunctionalRequirements: response.non_functional_requirements,
  };

  return { prd, personasFeedback };
}

// -----------------------------------------------------------------------------
// Initial State
// -----------------------------------------------------------------------------

const initialState: PRDState = {
  prd: null,
  personasFeedback: [],
  isLoading: false,
  error: null,
  isApproved: false,
  isRejected: false,
  rejectionReason: null,
};

// -----------------------------------------------------------------------------
// usePRD Hook
// -----------------------------------------------------------------------------

export function usePRD(
  workflowId: string | null,
  options: UsePRDOptions = {}
): UsePRDReturn {
  const {
    apiUrl = DEFAULT_API_URL,
    fetchOnMount = true,
    onSuccess,
    onError,
    onApprove,
    onReject,
  } = options;

  const [state, setState] = useState<PRDState>(initialState);

  /**
   * Fetch PRD data from the API.
   */
  const fetchPRD = useCallback(async () => {
    if (!workflowId) {
      setState((prev) => ({
        ...prev,
        error: 'No workflow ID provided',
        isLoading: false,
      }));
      return;
    }

    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: null,
    }));

    try {
      const response = await fetch(`${apiUrl}/api/workflows/${workflowId}/prd`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = (errorData as { message?: string }).message || `HTTP error! status: ${response.status}`;
        throw new Error(errorMessage);
      }

      const data: PRDApiResponse = await response.json();
      const { prd, personasFeedback } = transformApiResponse(data);

      setState((prev) => ({
        ...prev,
        prd,
        personasFeedback,
        isLoading: false,
        error: null,
      }));

      onSuccess?.(prd, personasFeedback);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch PRD';
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
      onError?.(errorMessage);
    }
  }, [workflowId, apiUrl, onSuccess, onError]);

  /**
   * Approve the PRD.
   */
  const approve = useCallback(async () => {
    if (!workflowId) return;

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(`${apiUrl}/api/workflows/${workflowId}/prd/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = (errorData as { message?: string }).message || `HTTP error! status: ${response.status}`;
        throw new Error(errorMessage);
      }

      setState((prev) => ({
        ...prev,
        isLoading: false,
        isApproved: true,
        isRejected: false,
        rejectionReason: null,
      }));

      onApprove?.();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to approve PRD';
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
      onError?.(errorMessage);
    }
  }, [workflowId, apiUrl, onApprove, onError]);

  /**
   * Reject the PRD with a reason.
   */
  const reject = useCallback(
    async (reason: string) => {
      if (!workflowId) return;

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const response = await fetch(`${apiUrl}/api/workflows/${workflowId}/prd/reject`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const errorMessage = (errorData as { message?: string }).message || `HTTP error! status: ${response.status}`;
          throw new Error(errorMessage);
        }

        setState((prev) => ({
          ...prev,
          isLoading: false,
          isApproved: false,
          isRejected: true,
          rejectionReason: reason,
        }));

        onReject?.(reason);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to reject PRD';
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: errorMessage,
        }));
        onError?.(errorMessage);
      }
    },
    [workflowId, apiUrl, onReject, onError]
  );

  /**
   * Clear error state.
   */
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  // Fetch on mount if enabled
  useEffect(() => {
    if (fetchOnMount && workflowId) {
      fetchPRD();
    }
  }, [fetchOnMount, workflowId, fetchPRD]);

  return {
    ...state,
    refresh: fetchPRD,
    approve,
    reject,
    clearError,
  };
}

export default usePRD;
