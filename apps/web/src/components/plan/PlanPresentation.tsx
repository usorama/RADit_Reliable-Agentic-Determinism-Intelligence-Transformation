'use client';

/**
 * PlanPresentation - Main component for displaying PRD (Product Requirements Document).
 *
 * Features:
 * - Overview/Summary section
 * - User Stories section (expandable with priority badges)
 * - Technical Specifications section (expandable with complexity badges)
 * - Acceptance Criteria section (expandable)
 * - Non-Functional Requirements section (expandable)
 * - Roundtable persona feedback display
 * - Export to PDF functionality
 * - Approve/Reject actions
 *
 * Accessibility:
 * - WCAG 2.1 AA compliant
 * - Screen reader friendly
 * - Keyboard navigable
 * - Dark mode compatible
 *
 * @example
 * ```tsx
 * <PlanPresentation
 *   workflowId="wf-123"
 *   prd={prdData}
 *   personasFeedback={feedbackData}
 *   onApprove={() => console.log('Approved')}
 *   onReject={(reason) => console.log('Rejected:', reason)}
 * />
 * ```
 */

import React, { useState, useCallback, useRef } from 'react';
import { ExpandableSection } from './ExpandableSection';
import { ComplexityBadge, ComplexityLevel } from './ComplexityBadge';
import { PersonaFeedbackCard, PersonaRole } from './PersonaFeedbackCard';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** User story definition */
export interface UserStory {
  /** Unique identifier */
  id: string;
  /** Story description */
  description: string;
  /** Priority level */
  priority: 'P0' | 'P1' | 'P2';
  /** Acceptance criteria for this story */
  acceptanceCriteria: string[];
}

/** Technical specification definition */
export interface TechSpec {
  /** Component name */
  component: string;
  /** Component description */
  description: string;
  /** Complexity level */
  complexity: ComplexityLevel;
}

/** PRD (Product Requirements Document) structure */
export interface PRD {
  /** Document title */
  title: string;
  /** Overview/summary text */
  overview: string;
  /** List of user stories */
  userStories: UserStory[];
  /** Technical specifications */
  techSpecs: TechSpec[];
  /** Global acceptance criteria */
  acceptanceCriteria: string[];
  /** Non-functional requirements */
  nonFunctionalRequirements: string[];
}

/** Persona feedback structure */
export interface PersonaFeedback {
  /** The persona providing feedback */
  persona: PersonaRole;
  /** Main feedback text */
  feedback: string;
  /** List of concerns */
  concerns: string[];
  /** List of recommendations */
  recommendations: string[];
}

/** Props for PlanPresentation component */
export interface PlanPresentationProps {
  /** Workflow ID this PRD belongs to */
  workflowId: string;
  /** The PRD data to display */
  prd: PRD;
  /** Feedback from roundtable personas */
  personasFeedback: PersonaFeedback[];
  /** Callback when PRD is approved */
  onApprove?: () => void;
  /** Callback when PRD is rejected */
  onReject?: (reason: string) => void;
  /** Custom class name */
  className?: string;
  /** Whether the component is in loading state */
  isLoading?: boolean;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

/**
 * Priority badge configuration.
 */
const PRIORITY_CONFIG: Record<
  'P0' | 'P1' | 'P2',
  { label: string; bgColor: string; textColor: string }
> = {
  P0: {
    label: 'P0 - Critical',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    textColor: 'text-red-800 dark:text-red-300',
  },
  P1: {
    label: 'P1 - High',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    textColor: 'text-orange-800 dark:text-orange-300',
  },
  P2: {
    label: 'P2 - Medium',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    textColor: 'text-blue-800 dark:text-blue-300',
  },
};

// -----------------------------------------------------------------------------
// Sub-Components
// -----------------------------------------------------------------------------

/**
 * Priority badge component.
 */
function PriorityBadge({ priority }: { priority: 'P0' | 'P1' | 'P2' }) {
  const config = PRIORITY_CONFIG[priority];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${config.bgColor} ${config.textColor}`}
      aria-label={`Priority: ${config.label}`}
    >
      {config.label}
    </span>
  );
}

/**
 * User story card component.
 */
function UserStoryCard({ story }: { story: UserStory }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-mono text-gray-500 dark:text-gray-400">
              {story.id}
            </span>
            <PriorityBadge priority={story.priority} />
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {story.description}
          </p>
        </div>
      </div>

      {story.acceptanceCriteria.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
            aria-expanded={isExpanded}
          >
            <svg
              className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Acceptance Criteria ({story.acceptanceCriteria.length})
          </button>

          {isExpanded && (
            <ul className="mt-2 ml-4 space-y-1">
              {story.acceptanceCriteria.map((criterion, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 text-xs text-gray-600 dark:text-gray-400"
                >
                  <svg
                    className="w-3 h-3 mt-0.5 text-green-500 flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {criterion}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Tech spec card component.
 */
function TechSpecCard({ spec }: { spec: TechSpec }) {
  return (
    <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="font-medium text-gray-900 dark:text-white">
              {spec.component}
            </h4>
            <ComplexityBadge complexity={spec.complexity} size="sm" />
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {spec.description}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Reject modal component.
 */
function RejectModal({
  isOpen,
  onClose,
  onConfirm,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleConfirm = useCallback(() => {
    if (reason.trim()) {
      onConfirm(reason.trim());
      setReason('');
    }
  }, [reason, onConfirm]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-modal-title"
      onKeyDown={handleKeyDown}
    >
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-lg shadow-xl">
        <div className="p-6">
          <h3
            id="reject-modal-title"
            className="text-lg font-semibold text-gray-900 dark:text-white mb-4"
          >
            Reject PRD
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Please provide a reason for rejecting this PRD. This feedback will be used to improve the document.
          </p>
          <label htmlFor="reject-reason" className="sr-only">
            Rejection reason
          </label>
          <textarea
            ref={textareaRef}
            id="reject-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter your feedback..."
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            autoFocus
          />
        </div>
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!reason.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export function PlanPresentation({
  workflowId,
  prd,
  personasFeedback,
  onApprove,
  onReject,
  className = '',
  isLoading = false,
}: PlanPresentationProps) {
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  /**
   * Handle export to PDF using browser print functionality.
   */
  const handleExportPDF = useCallback(() => {
    if (contentRef.current) {
      // Create a print-specific stylesheet
      const printStyles = `
        @media print {
          body * { visibility: hidden; }
          #prd-content, #prd-content * { visibility: visible; }
          #prd-content { position: absolute; left: 0; top: 0; width: 100%; }
          .no-print { display: none !important; }
        }
      `;

      // Add print styles
      const styleSheet = document.createElement('style');
      styleSheet.id = 'prd-print-styles';
      styleSheet.textContent = printStyles;
      document.head.appendChild(styleSheet);

      // Trigger print
      window.print();

      // Cleanup
      setTimeout(() => {
        styleSheet.remove();
      }, 100);
    }
  }, []);

  const handleApprove = useCallback(() => {
    onApprove?.();
  }, [onApprove]);

  const handleRejectConfirm = useCallback(
    (reason: string) => {
      onReject?.(reason);
      setIsRejectModalOpen(false);
    },
    [onReject]
  );

  if (isLoading) {
    return (
      <div className={`animate-pulse ${className}`}>
        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4" />
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2" />
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 mb-2" />
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-4/5" />
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">
            {prd.title}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Workflow: <span className="font-mono">{workflowId}</span>
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 no-print">
          <button
            type="button"
            onClick={handleExportPDF}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            aria-label="Export to PDF"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Export PDF
          </button>
        </div>
      </header>

      {/* Content */}
      <div
        id="prd-content"
        ref={contentRef}
        className="flex-1 overflow-y-auto p-6 space-y-6"
      >
        {/* Overview Section */}
        <section aria-labelledby="overview-heading">
          <h2
            id="overview-heading"
            className="text-lg font-semibold text-gray-900 dark:text-white mb-3"
          >
            Overview
          </h2>
          <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
              {prd.overview}
            </p>
          </div>
        </section>

        {/* User Stories Section */}
        <ExpandableSection
          title="User Stories"
          badge={prd.userStories.length}
          defaultExpanded={true}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          }
        >
          <div className="space-y-3">
            {prd.userStories.map((story) => (
              <UserStoryCard key={story.id} story={story} />
            ))}
          </div>
        </ExpandableSection>

        {/* Technical Specifications Section */}
        <ExpandableSection
          title="Technical Specifications"
          badge={prd.techSpecs.length}
          defaultExpanded={true}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          }
        >
          <div className="space-y-3">
            {prd.techSpecs.map((spec, idx) => (
              <TechSpecCard key={idx} spec={spec} />
            ))}
          </div>
        </ExpandableSection>

        {/* Acceptance Criteria Section */}
        <ExpandableSection
          title="Acceptance Criteria"
          badge={prd.acceptanceCriteria.length}
          defaultExpanded={false}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          }
        >
          <ul className="space-y-2">
            {prd.acceptanceCriteria.map((criterion, idx) => (
              <li
                key={idx}
                className="flex items-start gap-3 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
              >
                <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full text-xs font-medium">
                  {idx + 1}
                </span>
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {criterion}
                </span>
              </li>
            ))}
          </ul>
        </ExpandableSection>

        {/* Non-Functional Requirements Section */}
        <ExpandableSection
          title="Non-Functional Requirements"
          badge={prd.nonFunctionalRequirements.length}
          defaultExpanded={false}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          }
        >
          <ul className="space-y-2">
            {prd.nonFunctionalRequirements.map((nfr, idx) => (
              <li
                key={idx}
                className="flex items-start gap-3 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
              >
                <svg
                  className="w-5 h-5 mt-0.5 text-purple-500 dark:text-purple-400 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
                  />
                </svg>
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {nfr}
                </span>
              </li>
            ))}
          </ul>
        </ExpandableSection>

        {/* Persona Feedback Section */}
        {personasFeedback.length > 0 && (
          <section aria-labelledby="feedback-heading">
            <h2
              id="feedback-heading"
              className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z"
                />
              </svg>
              Roundtable Feedback
            </h2>
            <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-3">
              {personasFeedback.map((feedback, idx) => (
                <PersonaFeedbackCard
                  key={idx}
                  persona={feedback.persona}
                  feedback={feedback.feedback}
                  concerns={feedback.concerns}
                  recommendations={feedback.recommendations}
                />
              ))}
            </div>
          </section>
        )}
      </div>

      {/* Footer with Actions */}
      {(onApprove || onReject) && (
        <footer className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 no-print">
          {onReject && (
            <button
              type="button"
              onClick={() => setIsRejectModalOpen(true)}
              className="px-6 py-2.5 text-sm font-medium text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg transition-colors"
            >
              Reject
            </button>
          )}
          {onApprove && (
            <button
              type="button"
              onClick={handleApprove}
              className="px-6 py-2.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
            >
              Approve PRD
            </button>
          )}
        </footer>
      )}

      {/* Reject Modal */}
      <RejectModal
        isOpen={isRejectModalOpen}
        onClose={() => setIsRejectModalOpen(false)}
        onConfirm={handleRejectConfirm}
      />
    </div>
  );
}

export default PlanPresentation;
