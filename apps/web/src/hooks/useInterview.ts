/**
 * useInterview Hook - Manages interview/clarification flow with WebSocket updates.
 *
 * This hook provides:
 * - Real-time question updates via WebSocket
 * - Answer submission via REST API
 * - Skip remaining questions functionality
 * - Interview state management
 * - Error handling with retry capability
 * - Automatic reconnection on disconnect
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { InterviewStatus } from '@/types/interview';
import type {
  Answer,
  InterviewState,
  Question,
  SubmitAnswerResponse,
  SkipInterviewResponse,
  InterviewStatusResponse,
  UseInterviewOptions,
  UseInterviewReturn,
  InterviewEventType,
  QuestionEvent,
  AnswerAcknowledgedEvent,
  InterviewCompleteEvent,
  InterviewErrorEvent,
} from '@/types/interview';

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

const DEFAULT_RECONNECT_CONFIG = {
  maxRetries: 5,
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2.0,
};

// -----------------------------------------------------------------------------
// Initial State
// -----------------------------------------------------------------------------

const initialState: InterviewState = {
  currentQuestion: null,
  currentIndex: 0,
  totalQuestions: 0,
  answers: [],
  status: InterviewStatus.NOT_STARTED,
  isLoading: false,
  error: null,
  isComplete: false,
};

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Calculate reconnection delay using exponential backoff.
 */
function calculateDelay(
  attempt: number,
  initialDelayMs: number,
  maxDelayMs: number,
  backoffMultiplier: number
): number {
  const delay = initialDelayMs * Math.pow(backoffMultiplier, attempt);
  return Math.min(delay, maxDelayMs);
}

// -----------------------------------------------------------------------------
// useInterview Hook
// -----------------------------------------------------------------------------

/**
 * React hook for managing the interview/clarification flow.
 *
 * @param workflowId - The workflow ID for the interview
 * @param options - Configuration options
 * @returns State and actions for managing the interview
 *
 * @example
 * ```tsx
 * const {
 *   currentQuestion,
 *   currentQuestionNumber,
 *   totalQuestions,
 *   isLoading,
 *   isComplete,
 *   submitAnswer,
 *   skipRemaining,
 * } = useInterview('workflow-123', {
 *   onComplete: () => console.log('Interview completed'),
 *   onSkip: () => console.log('Interview skipped'),
 * });
 *
 * // Submit an answer
 * await submitAnswer('My answer');
 *
 * // Skip remaining questions
 * await skipRemaining();
 * ```
 */
export function useInterview(
  workflowId: string,
  options: UseInterviewOptions = {}
): UseInterviewReturn {
  const {
    apiUrl = DEFAULT_API_URL,
    wsUrl = DEFAULT_WS_URL,
    onComplete,
    onSkip,
    onError,
    onQuestion,
  } = options;

  // State
  const [state, setState] = useState<InterviewState>(initialState);

  // Refs for WebSocket management
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);
  const lastAnswerRef = useRef<{ questionId: string; answer: string | string[] } | null>(null);

  // -----------------------------------------------------------------------------
  // Error Handling
  // -----------------------------------------------------------------------------

  const handleError = useCallback(
    (error: string) => {
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        error,
        isLoading: false,
        status: InterviewStatus.ERROR,
      }));
      onError?.(error);
    },
    [onError]
  );

  // -----------------------------------------------------------------------------
  // WebSocket Event Handlers
  // -----------------------------------------------------------------------------

  const handleWebSocketMessage = useCallback(
    (event: MessageEvent) => {
      if (!mountedRef.current) return;

      try {
        const wsEvent = JSON.parse(event.data) as
          | QuestionEvent
          | AnswerAcknowledgedEvent
          | InterviewCompleteEvent
          | InterviewErrorEvent;

        switch (wsEvent.event_type) {
          case 'INTERVIEW_QUESTION' as InterviewEventType: {
            const questionEvent = wsEvent as QuestionEvent;
            const { question, currentIndex, totalQuestions } = questionEvent.data;
            setState((prev) => ({
              ...prev,
              currentQuestion: question,
              currentIndex,
              totalQuestions,
              status: InterviewStatus.IN_PROGRESS,
              isLoading: false,
              error: null,
            }));
            onQuestion?.(question);
            break;
          }

          case 'INTERVIEW_ANSWER_ACKNOWLEDGED' as InterviewEventType: {
            // Answer was received, waiting for next question
            setState((prev) => ({
              ...prev,
              isLoading: true,
            }));
            break;
          }

          case 'INTERVIEW_COMPLETE' as InterviewEventType: {
            const completeEvent = wsEvent as InterviewCompleteEvent;
            const { skipped } = completeEvent.data;
            setState((prev) => ({
              ...prev,
              currentQuestion: null,
              status: skipped ? InterviewStatus.SKIPPED : InterviewStatus.COMPLETED,
              isComplete: true,
              isLoading: false,
            }));
            if (skipped) {
              onSkip?.();
            } else {
              onComplete?.();
            }
            break;
          }

          case 'INTERVIEW_ERROR' as InterviewEventType: {
            const errorEvent = wsEvent as InterviewErrorEvent;
            handleError(errorEvent.data.error_message);
            break;
          }

          default:
            // Ignore other event types
            break;
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    },
    [handleError, onComplete, onSkip, onQuestion]
  );

  // -----------------------------------------------------------------------------
  // WebSocket Connection Management
  // -----------------------------------------------------------------------------

  const connectWebSocket = useCallback(() => {
    if (!mountedRef.current || !workflowId) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`${wsUrl}/ws/workflow/${workflowId}/interview`);

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectAttemptRef.current = 0;
      setState((prev) => ({
        ...prev,
        error: null,
      }));
    };

    ws.onmessage = handleWebSocketMessage;

    ws.onerror = () => {
      if (!mountedRef.current) return;
      handleError('WebSocket connection error');
    };

    ws.onclose = (event) => {
      if (!mountedRef.current) return;

      // Attempt reconnection if not a clean close
      if (!event.wasClean && reconnectAttemptRef.current < DEFAULT_RECONNECT_CONFIG.maxRetries) {
        const delay = calculateDelay(
          reconnectAttemptRef.current,
          DEFAULT_RECONNECT_CONFIG.initialDelayMs,
          DEFAULT_RECONNECT_CONFIG.maxDelayMs,
          DEFAULT_RECONNECT_CONFIG.backoffMultiplier
        );

        reconnectAttemptRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, delay);
      }
    };

    wsRef.current = ws;
  }, [workflowId, wsUrl, handleWebSocketMessage, handleError]);

  // -----------------------------------------------------------------------------
  // Fetch Initial Interview Status
  // -----------------------------------------------------------------------------

  const fetchInterviewStatus = useCallback(async () => {
    if (!mountedRef.current) return;

    setState((prev) => ({ ...prev, isLoading: true }));

    try {
      const response = await fetch(`${apiUrl}/api/workflow/${workflowId}/interview-status`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch interview status: ${response.status}`);
      }

      const data: InterviewStatusResponse = await response.json();

      if (!mountedRef.current) return;

      setState((prev) => ({
        ...prev,
        currentQuestion: data.current_question ?? null,
        currentIndex: data.current_index ?? 0,
        totalQuestions: data.total_questions ?? 0,
        status: data.status,
        isComplete: data.is_complete ?? false,
        isLoading: false,
      }));

      if (data.current_question) {
        onQuestion?.(data.current_question);
      }

      if (data.is_complete) {
        if (data.status === InterviewStatus.SKIPPED) {
          onSkip?.();
        } else {
          onComplete?.();
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch interview status';
      handleError(errorMessage);
    }
  }, [apiUrl, workflowId, handleError, onComplete, onSkip, onQuestion]);

  // -----------------------------------------------------------------------------
  // Submit Answer
  // -----------------------------------------------------------------------------

  const submitAnswer = useCallback(
    async (answer: string | string[]) => {
      if (!state.currentQuestion || !mountedRef.current) return;

      const questionId = state.currentQuestion.id;
      lastAnswerRef.current = { questionId, answer };

      setState((prev) => ({
        ...prev,
        isLoading: true,
        error: null,
      }));

      try {
        const response = await fetch(
          `${apiUrl}/api/workflow/${workflowId}/interview-answer`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              question_id: questionId,
              answer,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to submit answer: ${response.status}`);
        }

        const data: SubmitAnswerResponse = await response.json();

        if (!mountedRef.current) return;

        if (!data.success) {
          throw new Error(data.error || 'Failed to submit answer');
        }

        // Add the answer to our list
        const newAnswer: Answer = {
          questionId,
          value: answer,
          timestamp: new Date(),
        };

        setState((prev) => ({
          ...prev,
          answers: [...prev.answers, newAnswer],
        }));

        // Handle next question or completion from REST response
        // (WebSocket will also send updates, but REST provides immediate feedback)
        if (data.is_complete) {
          setState((prev) => ({
            ...prev,
            currentQuestion: null,
            status: InterviewStatus.COMPLETED,
            isComplete: true,
            isLoading: false,
          }));
          onComplete?.();
        } else if (data.next_question) {
          setState((prev) => ({
            ...prev,
            currentQuestion: data.next_question ?? null,
            currentIndex: data.current_index ?? prev.currentIndex + 1,
            totalQuestions: data.total_questions ?? prev.totalQuestions,
            isLoading: false,
          }));
          if (data.next_question) {
            onQuestion?.(data.next_question);
          }
        } else {
          // Waiting for WebSocket to provide next question
          setState((prev) => ({ ...prev, isLoading: true }));
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to submit answer';
        handleError(errorMessage);
      }
    },
    [apiUrl, workflowId, state.currentQuestion, handleError, onComplete, onQuestion]
  );

  // -----------------------------------------------------------------------------
  // Skip Remaining Questions
  // -----------------------------------------------------------------------------

  const skipRemaining = useCallback(async () => {
    if (!mountedRef.current) return;

    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: null,
    }));

    try {
      const response = await fetch(
        `${apiUrl}/api/workflow/${workflowId}/interview-skip`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            reason: 'User chose to skip remaining questions',
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to skip interview: ${response.status}`);
      }

      const data: SkipInterviewResponse = await response.json();

      if (!mountedRef.current) return;

      if (!data.success) {
        throw new Error('Failed to skip interview');
      }

      setState((prev) => ({
        ...prev,
        currentQuestion: null,
        status: InterviewStatus.SKIPPED,
        isComplete: true,
        isLoading: false,
      }));

      onSkip?.();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to skip interview';
      handleError(errorMessage);
    }
  }, [apiUrl, workflowId, handleError, onSkip]);

  // -----------------------------------------------------------------------------
  // Retry After Error
  // -----------------------------------------------------------------------------

  const retry = useCallback(async () => {
    setState((prev) => ({
      ...prev,
      error: null,
      status: prev.status === InterviewStatus.ERROR ? InterviewStatus.IN_PROGRESS : prev.status,
    }));

    // If we have a last answer that failed, retry it
    if (lastAnswerRef.current && state.currentQuestion?.id === lastAnswerRef.current.questionId) {
      await submitAnswer(lastAnswerRef.current.answer);
    } else {
      // Otherwise, re-fetch the interview status
      await fetchInterviewStatus();
    }
  }, [state.currentQuestion?.id, submitAnswer, fetchInterviewStatus]);

  // -----------------------------------------------------------------------------
  // Effects
  // -----------------------------------------------------------------------------

  // Initialize: fetch status and connect WebSocket
  useEffect(() => {
    mountedRef.current = true;
    fetchInterviewStatus();
    connectWebSocket();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [fetchInterviewStatus, connectWebSocket]);

  // -----------------------------------------------------------------------------
  // Return
  // -----------------------------------------------------------------------------

  return {
    currentQuestion: state.currentQuestion,
    currentQuestionNumber: state.currentIndex + 1,
    totalQuestions: state.totalQuestions,
    isLoading: state.isLoading,
    isComplete: state.isComplete,
    error: state.error,
    submitAnswer,
    skipRemaining,
    retry,
  };
}

export default useInterview;
