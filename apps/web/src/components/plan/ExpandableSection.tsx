'use client';

/**
 * ExpandableSection - Reusable accordion component for collapsible content.
 *
 * Features:
 * - Smooth expand/collapse animation
 * - Keyboard accessible (Enter/Space to toggle)
 * - Screen reader friendly with proper ARIA attributes
 * - Dark mode compatible
 * - Optional badge count display
 *
 * @example
 * ```tsx
 * <ExpandableSection
 *   title="User Stories"
 *   badge={5}
 *   defaultExpanded={true}
 * >
 *   <ul>...</ul>
 * </ExpandableSection>
 * ```
 */

import React, { useState, useCallback, useId, ReactNode } from 'react';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export interface ExpandableSectionProps {
  /** Title displayed in the header */
  title: string;
  /** Content to show when expanded */
  children: ReactNode;
  /** Whether the section starts expanded */
  defaultExpanded?: boolean;
  /** Optional badge count to display next to title */
  badge?: number;
  /** Optional icon to display before title */
  icon?: ReactNode;
  /** Custom class name for the container */
  className?: string;
  /** Callback fired when expansion state changes */
  onToggle?: (isExpanded: boolean) => void;
  /** Test ID for testing purposes */
  testId?: string;
}

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------

export function ExpandableSection({
  title,
  children,
  defaultExpanded = false,
  badge,
  icon,
  className = '',
  onToggle,
  testId,
}: ExpandableSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const contentId = useId();
  const headerId = useId();

  const handleToggle = useCallback(() => {
    const newState = !isExpanded;
    setIsExpanded(newState);
    onToggle?.(newState);
  }, [isExpanded, onToggle]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleToggle();
      }
    },
    [handleToggle]
  );

  return (
    <div
      className={`border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden ${className}`}
      data-testid={testId}
    >
      {/* Header Button */}
      <button
        id={headerId}
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
        aria-expanded={isExpanded}
        aria-controls={contentId}
      >
        <div className="flex items-center gap-3">
          {/* Optional Icon */}
          {icon && (
            <span className="text-gray-500 dark:text-gray-400" aria-hidden="true">
              {icon}
            </span>
          )}

          {/* Title */}
          <span className="text-base font-medium text-gray-900 dark:text-white">
            {title}
          </span>

          {/* Badge */}
          {badge !== undefined && badge > 0 && (
            <span
              className="inline-flex items-center justify-center px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded-full"
              aria-label={`${badge} items`}
            >
              {badge}
            </span>
          )}
        </div>

        {/* Chevron Icon */}
        <svg
          className={`w-5 h-5 text-gray-500 dark:text-gray-400 transition-transform duration-200 ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Expandable Content */}
      <div
        id={contentId}
        role="region"
        aria-labelledby={headerId}
        hidden={!isExpanded}
        className={`transition-all duration-200 ease-in-out ${
          isExpanded ? 'opacity-100' : 'opacity-0'
        }`}
      >
        <div className="p-4 bg-white dark:bg-gray-900">
          {children}
        </div>
      </div>
    </div>
  );
}

export default ExpandableSection;
