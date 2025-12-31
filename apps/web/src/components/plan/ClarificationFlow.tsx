/**
 * ClarificationFlow Component - Interview flow for Planner clarifying questions.
 *
 * Features:
 * - Displays interview questions one at a time
 * - Supports text, multi_choice, and checkbox question types
 * - Shows progress indicator
 * - Skip remaining questions with confirmation
 * - Auto-advance to next question on answer
 * - Loading state while waiting for next question
 * - Completed state when all questions answered
 * - Error handling with retry option
 * - Accessible (WCAG 2.1 AA)
 * - Smooth transitions between questions
 */

'use client';

import React, { useCallback, useState, useEffect, useRef } from 'react';
import { useInterview } from '@/hooks/useInterview';
import { ProgressIndicator } from './ProgressIndicator';
import { QuestionInput } from './QuestionInput';
import type { ClarificationFlowProps, SkipConfirmationModalProps } from '@/types/interview';

// -----------------------------------------------------------------------------
// Skip Confirmation Modal
// -----------------------------------------------------------------------------

function SkipConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  remainingQuestions,
}: SkipConfirmationModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  // Focus trap and escape key handling
  useEffect(() => {
    if (!isOpen) return;

    // Focus the cancel button when modal opens
    cancelButtonRef.current?.focus();

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Prevent scroll when modal is open
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

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="skip-modal-title"
      aria-describedby="skip-modal-description"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal content */}
      <div
        ref={modalRef}
        className="relative bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 p-6 animate-in fade-in zoom-in-95 duration-200"
      >
        {/* Warning icon */}
        <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 rounded-full bg-yellow-100 dark:bg-yellow-900/30">
          <svg
            className="w-6 h-6 text-yellow-600 dark:text-yellow-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Title */}
        <h2
          id="skip-modal-title"
          className="text-lg font-semibold text-gray-900 dark:text-white text-center mb-2"
        >
          Skip Remaining Questions?
        </h2>

        {/* Description */}
        <p
          id="skip-modal-description"
          className="text-gray-600 dark:text-gray-400 text-center mb-6"
        >
          You have {remainingQuestions} question{remainingQuestions !== 1 ? 's' : ''} remaining.
          Skipping may result in a less tailored plan. Are you sure you want to continue?
        </p>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            ref={cancelButtonRef}
            onClick={onClose}
            className="flex-1 px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Continue Interview
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2 text-white bg-yellow-600 hover:bg-yellow-700 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-yellow-400"
          >
            Skip Questions
          </button>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Loading State Component
// -----------------------------------------------------------------------------

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-12" aria-busy="true">
      <div className="relative w-16 h-16">
        {/* Outer ring */}
        <div className="absolute inset-0 rounded-full border-4 border-gray-200 dark:border-gray-700" />
        {/* Spinning indicator */}
        <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 animate-spin" />
      </div>
      <p className="mt-4 text-gray-600 dark:text-gray-400">
        Loading next question...
      </p>
      <span className="sr-only">Please wait while we load the next question.</span>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Completed State Component
// -----------------------------------------------------------------------------

function CompletedState({ onContinue }: { onContinue: () => void }) {
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    buttonRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {/* Success icon */}
      <div className="flex items-center justify-center w-16 h-16 mb-4 rounded-full bg-green-100 dark:bg-green-900/30">
        <svg
          className="w-8 h-8 text-green-600 dark:text-green-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
        Interview Complete!
      </h2>
      <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-sm">
        Thank you for providing your answers. The Planner is now generating a tailored plan for your project.
      </p>

      <button
        ref={buttonRef}
        onClick={onContinue}
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
      >
        Continue to Plan
      </button>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Error State Component
// -----------------------------------------------------------------------------

function ErrorState({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  const retryButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    retryButtonRef.current?.focus();
  }, []);

  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      role="alert"
    >
      {/* Error icon */}
      <div className="flex items-center justify-center w-16 h-16 mb-4 rounded-full bg-red-100 dark:bg-red-900/30">
        <svg
          className="w-8 h-8 text-red-600 dark:text-red-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
        Something went wrong
      </h2>
      <p className="text-gray-600 dark:text-gray-400 mb-2 max-w-sm">{error}</p>
      <p className="text-sm text-gray-500 dark:text-gray-500 mb-6">
        Please try again or contact support if the problem persists.
      </p>

      <button
        ref={retryButtonRef}
        onClick={onRetry}
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
      >
        Try Again
      </button>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main ClarificationFlow Component
// -----------------------------------------------------------------------------

export function ClarificationFlow({
  workflowId,
  onComplete,
  onSkip,
  className = '',
}: ClarificationFlowProps) {
  // Interview state
  const {
    currentQuestion,
    currentQuestionNumber,
    totalQuestions,
    isLoading,
    isComplete,
    error,
    submitAnswer,
    skipRemaining,
    retry,
  } = useInterview(workflowId, {
    onComplete,
    onSkip,
  });

  // Local state
  const [answerValue, setAnswerValue] = useState<string | string[]>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSkipModal, setShowSkipModal] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Reset answer value when question changes
  useEffect(() => {
    if (currentQuestion) {
      setAnswerValue(currentQuestion.type === 'checkbox' ? [] : '');
      setIsTransitioning(false);
    }
  }, [currentQuestion?.id, currentQuestion?.type]);

  // Handle answer submission
  const handleSubmit = useCallback(async () => {
    if (!currentQuestion || isSubmitting) return;

    // Validate required questions
    if (currentQuestion.required) {
      const isEmpty =
        currentQuestion.type === 'checkbox'
          ? !Array.isArray(answerValue) || answerValue.length === 0
          : !answerValue || (typeof answerValue === 'string' && !answerValue.trim());

      if (isEmpty) return;
    }

    setIsSubmitting(true);
    setIsTransitioning(true);

    try {
      await submitAnswer(answerValue);
    } finally {
      setIsSubmitting(false);
    }
  }, [currentQuestion, answerValue, isSubmitting, submitAnswer]);

  // Handle skip confirmation
  const handleSkipConfirm = useCallback(async () => {
    setShowSkipModal(false);
    await skipRemaining();
  }, [skipRemaining]);

  // Calculate remaining questions
  const remainingQuestions = totalQuestions - currentQuestionNumber + 1;

  // Render based on state
  if (error) {
    return (
      <div className={`w-full max-w-2xl mx-auto ${className}`}>
        <ErrorState error={error} onRetry={retry} />
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className={`w-full max-w-2xl mx-auto ${className}`}>
        <CompletedState onContinue={onComplete} />
      </div>
    );
  }

  if (isLoading && !currentQuestion) {
    return (
      <div className={`w-full max-w-2xl mx-auto ${className}`}>
        <LoadingState />
      </div>
    );
  }

  return (
    <div className={`w-full max-w-2xl mx-auto ${className}`}>
      {/* Progress indicator */}
      {totalQuestions > 0 && (
        <div className="mb-8">
          <ProgressIndicator
            current={currentQuestionNumber}
            total={totalQuestions}
          />
        </div>
      )}

      {/* Question card with transition */}
      <div
        className={`
          bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 md:p-8
          transition-opacity duration-300
          ${isTransitioning ? 'opacity-50' : 'opacity-100'}
        `}
      >
        {currentQuestion ? (
          <>
            {/* Question input */}
            <QuestionInput
              question={currentQuestion}
              value={answerValue}
              onChange={setAnswerValue}
              onSubmit={handleSubmit}
              disabled={isSubmitting || isLoading}
              inputId="clarification-question"
            />

            {/* Action buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
              {/* Skip button */}
              <button
                onClick={() => setShowSkipModal(true)}
                disabled={isSubmitting}
                className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:underline"
              >
                Skip remaining questions
              </button>

              {/* Submit button */}
              <button
                onClick={handleSubmit}
                disabled={
                  isSubmitting ||
                  isLoading ||
                  (currentQuestion.required &&
                    (currentQuestion.type === 'checkbox'
                      ? !Array.isArray(answerValue) || answerValue.length === 0
                      : !answerValue || (typeof answerValue === 'string' && !answerValue.trim())))
                }
                className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white font-medium rounded-lg transition-colors disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 flex items-center justify-center gap-2"
              >
                {isSubmitting || isLoading ? (
                  <>
                    <svg
                      className="w-5 h-5 animate-spin"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Submitting...
                  </>
                ) : currentQuestionNumber === totalQuestions ? (
                  'Finish Interview'
                ) : (
                  <>
                    Next Question
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                      />
                    </svg>
                  </>
                )}
              </button>
            </div>
          </>
        ) : (
          <LoadingState />
        )}
      </div>

      {/* Skip confirmation modal */}
      <SkipConfirmationModal
        isOpen={showSkipModal}
        onClose={() => setShowSkipModal(false)}
        onConfirm={handleSkipConfirm}
        remainingQuestions={remainingQuestions}
      />

      {/* Live region for screen reader announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {currentQuestion && !isLoading && (
          <>
            Question {currentQuestionNumber} of {totalQuestions}: {currentQuestion.text}
          </>
        )}
        {isLoading && 'Loading next question...'}
        {isComplete && 'Interview complete.'}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Exports
// -----------------------------------------------------------------------------

export default ClarificationFlow;
