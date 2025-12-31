'use client';

/**
 * ApprovalGate - Human-in-the-loop approval checkpoint for PRD or task review.
 *
 * Features:
 * - Three action buttons: Approve, Reject, Request Changes
 * - Comment/feedback textarea for reject/modify actions
 * - Confirmation modal before actions
 * - Status indicator showing "Awaiting Your Approval"
 * - Loading state during action processing
 * - Keyboard accessible and screen reader friendly
 * - Dark mode compatible
 *
 * @example
 * ```tsx
 * <ApprovalGate
 *   workflowId="uuid-here"
 *   artifactType="prd"
 *   onApprove={() => handleApprove()}
 *   onReject={(feedback) => handleReject(feedback)}
 *   onModify={(feedback) => handleModify(feedback)}
 * />
 * ```
 */

import React, { useState, useCallback } from 'react';
import { ConfirmationModal, type ConfirmationVariant } from './ConfirmationModal';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** Type of artifact being reviewed */
export type ArtifactType = 'prd' | 'tasks';

/** Action types for the approval gate */
export type ApprovalAction = 'approve' | 'reject' | 'modify';

export interface ApprovalGateProps {
  /** Workflow ID for the review action */
  workflowId: string;
  /** Type of artifact being reviewed (PRD or tasks) */
  artifactType: ArtifactType;
  /** Callback when user approves */
  onApprove: () => void | Promise<void>;
  /** Callback when user rejects (requires feedback) */
  onReject: (feedback: string) => void | Promise<void>;
  /** Callback when user requests modifications (requires feedback) */
  onModify: (feedback: string) => void | Promise<void>;
  /** Whether an action is currently being processed */
  isProcessing?: boolean;
  /** Custom class name */
  className?: string;
  /** Test ID for testing purposes */
  testId?: string;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

const ARTIFACT_LABELS: Record<ArtifactType, { title: string; description: string }> = {
  prd: {
    title: 'Product Requirements Document',
    description: 'Review the generated PRD before proceeding to task execution.',
  },
  tasks: {
    title: 'Task Decomposition',
    description: 'Review the decomposed tasks before proceeding to implementation.',
  },
};

const ACTION_CONFIG: Record<
  ApprovalAction,
  {
    label: string;
    icon: React.ReactNode;
    variant: ConfirmationVariant;
    bgColor: string;
    hoverColor: string;
    textColor: string;
    requiresFeedback: boolean;
    modalTitle: string;
    modalMessage: string;
  }
> = {
  approve: {
    label: 'Approve',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    variant: 'success',
    bgColor: 'bg-green-600',
    hoverColor: 'hover:bg-green-700',
    textColor: 'text-white',
    requiresFeedback: false,
    modalTitle: 'Approve and Proceed?',
    modalMessage: 'Are you sure you want to approve this and proceed to the next phase? This action will start task execution.',
  },
  reject: {
    label: 'Reject',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    variant: 'danger',
    bgColor: 'bg-red-600',
    hoverColor: 'hover:bg-red-700',
    textColor: 'text-white',
    requiresFeedback: true,
    modalTitle: 'Reject and Return?',
    modalMessage: 'Are you sure you want to reject this? The workflow will return to the interview phase with your feedback.',
  },
  modify: {
    label: 'Request Changes',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
    variant: 'warning',
    bgColor: 'bg-yellow-500',
    hoverColor: 'hover:bg-yellow-600',
    textColor: 'text-white',
    requiresFeedback: true,
    modalTitle: 'Request Modifications?',
    modalMessage: 'Are you sure you want to request modifications? The system will regenerate with your feedback.',
  },
};

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------

export function ApprovalGate({
  workflowId,
  artifactType,
  onApprove,
  onReject,
  onModify,
  isProcessing = false,
  className = '',
  testId,
}: ApprovalGateProps) {
  // Local state
  const [feedback, setFeedback] = useState('');
  const [selectedAction, setSelectedAction] = useState<ApprovalAction | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const artifactLabel = ARTIFACT_LABELS[artifactType];

  // Handle action button click
  const handleActionClick = useCallback((action: ApprovalAction) => {
    const config = ACTION_CONFIG[action];

    // If action requires feedback and none provided, don't open modal
    if (config.requiresFeedback && !feedback.trim()) {
      // Focus the textarea
      const textarea = document.getElementById('approval-feedback');
      textarea?.focus();
      return;
    }

    setSelectedAction(action);
    setIsModalOpen(true);
  }, [feedback]);

  // Handle confirmation
  const handleConfirm = useCallback(async () => {
    if (!selectedAction) return;

    setIsSubmitting(true);

    try {
      switch (selectedAction) {
        case 'approve':
          await onApprove();
          break;
        case 'reject':
          await onReject(feedback);
          break;
        case 'modify':
          await onModify(feedback);
          break;
      }

      // Clear state on success
      setFeedback('');
      setSelectedAction(null);
      setIsModalOpen(false);
    } catch (error) {
      console.error('Approval action failed:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedAction, feedback, onApprove, onReject, onModify]);

  // Handle modal close
  const handleModalClose = useCallback(() => {
    if (!isSubmitting) {
      setIsModalOpen(false);
      setSelectedAction(null);
    }
  }, [isSubmitting]);

  // Determine if feedback is required for current action intent
  const needsFeedback = (action: ApprovalAction) => {
    const config = ACTION_CONFIG[action];
    return config.requiresFeedback && !feedback.trim();
  };

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm ${className}`}
      data-testid={testId}
    >
      {/* Header with status indicator */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {artifactLabel.title} Review
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {artifactLabel.description}
            </p>
          </div>

          {/* Status badge */}
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500" />
            </span>
            <span className="text-sm font-medium text-yellow-600 dark:text-yellow-400">
              Awaiting Your Approval
            </span>
          </div>
        </div>
      </div>

      {/* Feedback textarea */}
      <div className="px-4 py-4">
        <label
          htmlFor="approval-feedback"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          Feedback / Comments
          <span className="text-gray-400 dark:text-gray-500 font-normal">
            {' '}
            (required for reject or request changes)
          </span>
        </label>
        <textarea
          id="approval-feedback"
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:focus:ring-blue-400 dark:focus:border-blue-400 resize-none"
          placeholder="Enter your feedback here..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={isProcessing || isSubmitting}
          aria-describedby="feedback-help"
        />
        <p
          id="feedback-help"
          className="mt-1 text-xs text-gray-500 dark:text-gray-400"
        >
          Provide specific feedback to help improve the {artifactType === 'prd' ? 'requirements document' : 'task breakdown'}.
        </p>
      </div>

      {/* Action buttons */}
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-700 flex flex-wrap gap-3 justify-end">
        {/* Request Changes button */}
        <button
          type="button"
          onClick={() => handleActionClick('modify')}
          disabled={isProcessing || isSubmitting}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors
            ${needsFeedback('modify')
              ? 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              : `${ACTION_CONFIG.modify.bgColor} ${ACTION_CONFIG.modify.hoverColor} ${ACTION_CONFIG.modify.textColor}`
            }
            disabled:opacity-50 disabled:cursor-not-allowed`}
          aria-label="Request changes to the document"
          title={needsFeedback('modify') ? 'Please enter feedback first' : 'Request modifications'}
        >
          {ACTION_CONFIG.modify.icon}
          {ACTION_CONFIG.modify.label}
        </button>

        {/* Reject button */}
        <button
          type="button"
          onClick={() => handleActionClick('reject')}
          disabled={isProcessing || isSubmitting}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors
            ${needsFeedback('reject')
              ? 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              : `${ACTION_CONFIG.reject.bgColor} ${ACTION_CONFIG.reject.hoverColor} ${ACTION_CONFIG.reject.textColor}`
            }
            disabled:opacity-50 disabled:cursor-not-allowed`}
          aria-label="Reject the document"
          title={needsFeedback('reject') ? 'Please enter feedback first' : 'Reject and return to interview'}
        >
          {ACTION_CONFIG.reject.icon}
          {ACTION_CONFIG.reject.label}
        </button>

        {/* Approve button */}
        <button
          type="button"
          onClick={() => handleActionClick('approve')}
          disabled={isProcessing || isSubmitting}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${ACTION_CONFIG.approve.bgColor} ${ACTION_CONFIG.approve.hoverColor} ${ACTION_CONFIG.approve.textColor} disabled:opacity-50 disabled:cursor-not-allowed`}
          aria-label="Approve and proceed"
        >
          {ACTION_CONFIG.approve.icon}
          {ACTION_CONFIG.approve.label}
        </button>
      </div>

      {/* Confirmation Modal */}
      {selectedAction && (
        <ConfirmationModal
          isOpen={isModalOpen}
          onClose={handleModalClose}
          onConfirm={handleConfirm}
          title={ACTION_CONFIG[selectedAction].modalTitle}
          message={
            selectedAction === 'approve'
              ? ACTION_CONFIG[selectedAction].modalMessage
              : `${ACTION_CONFIG[selectedAction].modalMessage}\n\nYour feedback: "${feedback}"`
          }
          confirmLabel={ACTION_CONFIG[selectedAction].label}
          cancelLabel="Cancel"
          variant={ACTION_CONFIG[selectedAction].variant}
          isLoading={isSubmitting}
          testId={`${testId}-modal`}
        />
      )}

      {/* Loading overlay */}
      {isProcessing && (
        <div className="absolute inset-0 bg-white/50 dark:bg-gray-800/50 flex items-center justify-center rounded-lg">
          <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300">
            <svg
              className="animate-spin h-5 w-5"
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
            <span>Processing...</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default ApprovalGate;
