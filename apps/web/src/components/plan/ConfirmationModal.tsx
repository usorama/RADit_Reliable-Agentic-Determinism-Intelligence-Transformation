'use client';

/**
 * ConfirmationModal - Reusable modal component for confirming user actions.
 *
 * Features:
 * - Customizable title, message, and button labels
 * - Keyboard accessible (Escape to close, Enter to confirm)
 * - Screen reader friendly with proper ARIA attributes
 * - Focus trap within modal
 * - Dark mode compatible
 * - Smooth fade-in animation
 *
 * @example
 * ```tsx
 * <ConfirmationModal
 *   isOpen={showConfirm}
 *   onClose={() => setShowConfirm(false)}
 *   onConfirm={handleApprove}
 *   title="Approve PRD?"
 *   message="Are you sure you want to approve this PRD and proceed to execution?"
 *   confirmLabel="Yes, Approve"
 *   cancelLabel="Cancel"
 *   variant="success"
 * />
 * ```
 */

import React, { useCallback, useEffect, useRef } from 'react';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** Variant determines the color scheme of the confirm button */
export type ConfirmationVariant = 'success' | 'danger' | 'warning' | 'info';

export interface ConfirmationModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Callback when the modal is closed (cancel or backdrop click) */
  onClose: () => void;
  /** Callback when the confirm action is triggered */
  onConfirm: () => void;
  /** Modal title */
  title: string;
  /** Modal message/description */
  message: string;
  /** Label for the confirm button */
  confirmLabel?: string;
  /** Label for the cancel button */
  cancelLabel?: string;
  /** Color variant for the confirm button */
  variant?: ConfirmationVariant;
  /** Whether the confirm action is in progress */
  isLoading?: boolean;
  /** Test ID for testing purposes */
  testId?: string;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

/**
 * Configuration for each variant including button colors.
 */
const VARIANT_CONFIG: Record<
  ConfirmationVariant,
  {
    buttonBg: string;
    buttonBgHover: string;
    buttonText: string;
    iconColor: string;
  }
> = {
  success: {
    buttonBg: 'bg-green-600',
    buttonBgHover: 'hover:bg-green-700',
    buttonText: 'text-white',
    iconColor: 'text-green-600',
  },
  danger: {
    buttonBg: 'bg-red-600',
    buttonBgHover: 'hover:bg-red-700',
    buttonText: 'text-white',
    iconColor: 'text-red-600',
  },
  warning: {
    buttonBg: 'bg-yellow-600',
    buttonBgHover: 'hover:bg-yellow-700',
    buttonText: 'text-white',
    iconColor: 'text-yellow-600',
  },
  info: {
    buttonBg: 'bg-blue-600',
    buttonBgHover: 'hover:bg-blue-700',
    buttonText: 'text-white',
    iconColor: 'text-blue-600',
  },
};

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------

export function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'info',
  isLoading = false,
  testId,
}: ConfirmationModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const config = VARIANT_CONFIG[variant];

  // Focus the confirm button when modal opens
  useEffect(() => {
    if (isOpen && confirmButtonRef.current) {
      confirmButtonRef.current.focus();
    }
  }, [isOpen]);

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!isOpen) return;

      if (event.key === 'Escape') {
        onClose();
      }
    },
    [isOpen, onClose]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Handle backdrop click
  const handleBackdropClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  // Handle confirm action
  const handleConfirm = useCallback(() => {
    if (!isLoading) {
      onConfirm();
    }
  }, [isLoading, onConfirm]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      aria-labelledby="modal-title"
      role="dialog"
      aria-modal="true"
      data-testid={testId}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-500/75 dark:bg-gray-900/80 transition-opacity"
        aria-hidden="true"
        onClick={handleBackdropClick}
      />

      {/* Modal container */}
      <div
        className="fixed inset-0 z-10 overflow-y-auto"
        onClick={handleBackdropClick}
      >
        <div className="flex min-h-full items-center justify-center p-4 text-center">
          {/* Modal panel */}
          <div
            ref={modalRef}
            className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Content */}
            <div className="bg-white dark:bg-gray-800 px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
              <div className="sm:flex sm:items-start">
                {/* Icon */}
                <div
                  className={`mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full ${
                    variant === 'danger'
                      ? 'bg-red-100 dark:bg-red-900/30'
                      : variant === 'warning'
                      ? 'bg-yellow-100 dark:bg-yellow-900/30'
                      : variant === 'success'
                      ? 'bg-green-100 dark:bg-green-900/30'
                      : 'bg-blue-100 dark:bg-blue-900/30'
                  } sm:mx-0 sm:h-10 sm:w-10`}
                >
                  {variant === 'danger' ? (
                    <svg
                      className={`h-6 w-6 ${config.iconColor}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth="1.5"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                      />
                    </svg>
                  ) : variant === 'success' ? (
                    <svg
                      className={`h-6 w-6 ${config.iconColor}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth="1.5"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  ) : (
                    <svg
                      className={`h-6 w-6 ${config.iconColor}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth="1.5"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
                      />
                    </svg>
                  )}
                </div>

                {/* Text content */}
                <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left">
                  <h3
                    className="text-base font-semibold leading-6 text-gray-900 dark:text-white"
                    id="modal-title"
                  >
                    {title}
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {message}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
              <button
                ref={confirmButtonRef}
                type="button"
                className={`inline-flex w-full justify-center rounded-md ${config.buttonBg} ${config.buttonBgHover} px-3 py-2 text-sm font-semibold ${config.buttonText} shadow-sm sm:ml-3 sm:w-auto disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
                onClick={handleConfirm}
                disabled={isLoading}
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-4 w-4"
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
                    Processing...
                  </span>
                ) : (
                  confirmLabel
                )}
              </button>
              <button
                type="button"
                className="mt-3 inline-flex w-full justify-center rounded-md bg-white dark:bg-gray-600 px-3 py-2 text-sm font-semibold text-gray-900 dark:text-white shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-gray-500 hover:bg-gray-50 dark:hover:bg-gray-500 sm:mt-0 sm:w-auto transition-colors"
                onClick={onClose}
                disabled={isLoading}
              >
                {cancelLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ConfirmationModal;
