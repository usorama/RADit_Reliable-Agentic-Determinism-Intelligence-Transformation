/**
 * ProgressIndicator Component - Displays interview progress.
 *
 * Features:
 * - Visual progress bar with percentage fill
 * - Text indicator showing "Question X of Y"
 * - Accessible with ARIA attributes
 * - Smooth transition animations
 * - Responsive design
 */

'use client';

import React, { useMemo } from 'react';
import type { ProgressIndicatorProps } from '@/types/interview';

// -----------------------------------------------------------------------------
// ProgressIndicator Component
// -----------------------------------------------------------------------------

export function ProgressIndicator({
  current,
  total,
  className = '',
}: ProgressIndicatorProps) {
  // Calculate progress percentage
  const percentage = useMemo(() => {
    if (total <= 0) return 0;
    // Use (current - 1) to show progress of completed questions
    // current question is the one being answered
    const completed = Math.max(0, current - 1);
    return Math.min(100, Math.round((completed / total) * 100));
  }, [current, total]);

  // Generate unique ID for accessibility
  const progressId = useMemo(
    () => `progress-${Math.random().toString(36).substring(2, 9)}`,
    []
  );

  if (total <= 0) {
    return null;
  }

  return (
    <div className={`w-full ${className}`}>
      {/* Text indicator */}
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-sm font-medium text-gray-700 dark:text-gray-300"
          id={`${progressId}-label`}
        >
          Question {current} of {total}
        </span>
        <span
          className="text-sm text-gray-500 dark:text-gray-400"
          aria-hidden="true"
        >
          {percentage}% complete
        </span>
      </div>

      {/* Progress bar */}
      <div
        className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-labelledby={`${progressId}-label`}
        aria-describedby={`${progressId}-desc`}
      >
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Screen reader description */}
      <span id={`${progressId}-desc`} className="sr-only">
        You have completed {current - 1} of {total} questions.
        {current <= total && ` Currently answering question ${current}.`}
      </span>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Step Indicator Variant
// -----------------------------------------------------------------------------

interface StepIndicatorProps {
  /** Current step (1-based) */
  current: number;
  /** Total number of steps */
  total: number;
  /** Custom class name for styling */
  className?: string;
}

/**
 * StepIndicator - Alternative visual representation using dots/circles.
 */
export function StepIndicator({
  current,
  total,
  className = '',
}: StepIndicatorProps) {
  if (total <= 0) {
    return null;
  }

  // Limit to max 10 visible dots for UX
  const maxDots = 10;
  const showDots = total <= maxDots;

  return (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      {showDots ? (
        // Show individual dots
        Array.from({ length: total }, (_, index) => {
          const stepNum = index + 1;
          const isCompleted = stepNum < current;
          const isCurrent = stepNum === current;

          return (
            <div
              key={stepNum}
              className={`
                w-2.5 h-2.5 rounded-full transition-all duration-300
                ${
                  isCompleted
                    ? 'bg-green-500 scale-100'
                    : isCurrent
                    ? 'bg-blue-600 scale-125 ring-2 ring-blue-300 dark:ring-blue-800'
                    : 'bg-gray-300 dark:bg-gray-600'
                }
              `}
              aria-hidden="true"
            />
          );
        })
      ) : (
        // Show compact indicator for many steps
        <div className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-400">
          <span className="font-semibold text-blue-600 dark:text-blue-400">
            {current}
          </span>
          <span>/</span>
          <span>{total}</span>
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Exports
// -----------------------------------------------------------------------------

export default ProgressIndicator;
