'use client';

/**
 * ComplexityBadge - Visual indicator for feature/task complexity levels.
 *
 * Displays a color-coded badge indicating complexity:
 * - Low: Green - Simple, straightforward tasks
 * - Medium: Yellow - Moderate complexity, some considerations
 * - High: Orange - Complex, requires careful planning
 * - Critical: Red - Highest complexity, architectural decisions
 *
 * @example
 * ```tsx
 * <ComplexityBadge complexity="high" />
 * <ComplexityBadge complexity="low" showLabel />
 * ```
 */

import React from 'react';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** Complexity level for features/tasks */
export type ComplexityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface ComplexityBadgeProps {
  /** The complexity level to display */
  complexity: ComplexityLevel;
  /** Whether to show the text label alongside the badge */
  showLabel?: boolean;
  /** Size variant of the badge */
  size?: 'sm' | 'md' | 'lg';
  /** Custom class name */
  className?: string;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

/**
 * Configuration for each complexity level.
 * Includes colors for light and dark modes, labels, and descriptions.
 */
const COMPLEXITY_CONFIG: Record<
  ComplexityLevel,
  {
    label: string;
    description: string;
    bgLight: string;
    bgDark: string;
    textLight: string;
    textDark: string;
    borderLight: string;
    borderDark: string;
    dotColor: string;
  }
> = {
  low: {
    label: 'Low',
    description: 'Simple, straightforward implementation',
    bgLight: 'bg-green-100',
    bgDark: 'dark:bg-green-900/30',
    textLight: 'text-green-800',
    textDark: 'dark:text-green-300',
    borderLight: 'border-green-200',
    borderDark: 'dark:border-green-800',
    dotColor: 'bg-green-500',
  },
  medium: {
    label: 'Medium',
    description: 'Moderate complexity, some considerations',
    bgLight: 'bg-yellow-100',
    bgDark: 'dark:bg-yellow-900/30',
    textLight: 'text-yellow-800',
    textDark: 'dark:text-yellow-300',
    borderLight: 'border-yellow-200',
    borderDark: 'dark:border-yellow-800',
    dotColor: 'bg-yellow-500',
  },
  high: {
    label: 'High',
    description: 'Complex, requires careful planning',
    bgLight: 'bg-orange-100',
    bgDark: 'dark:bg-orange-900/30',
    textLight: 'text-orange-800',
    textDark: 'dark:text-orange-300',
    borderLight: 'border-orange-200',
    borderDark: 'dark:border-orange-800',
    dotColor: 'bg-orange-500',
  },
  critical: {
    label: 'Critical',
    description: 'Highest complexity, architectural decisions',
    bgLight: 'bg-red-100',
    bgDark: 'dark:bg-red-900/30',
    textLight: 'text-red-800',
    textDark: 'dark:text-red-300',
    borderLight: 'border-red-200',
    borderDark: 'dark:border-red-800',
    dotColor: 'bg-red-500',
  },
};

/**
 * Size configurations for the badge.
 */
const SIZE_CONFIG: Record<
  'sm' | 'md' | 'lg',
  { padding: string; text: string; dot: string; gap: string }
> = {
  sm: { padding: 'px-1.5 py-0.5', text: 'text-xs', dot: 'w-1.5 h-1.5', gap: 'gap-1' },
  md: { padding: 'px-2 py-0.5', text: 'text-xs', dot: 'w-2 h-2', gap: 'gap-1.5' },
  lg: { padding: 'px-2.5 py-1', text: 'text-sm', dot: 'w-2.5 h-2.5', gap: 'gap-2' },
};

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------

export function ComplexityBadge({
  complexity,
  showLabel = true,
  size = 'md',
  className = '',
}: ComplexityBadgeProps) {
  const config = COMPLEXITY_CONFIG[complexity];
  const sizeConfig = SIZE_CONFIG[size];

  return (
    <span
      className={`
        inline-flex items-center ${sizeConfig.gap} ${sizeConfig.padding}
        ${config.bgLight} ${config.bgDark}
        ${config.textLight} ${config.textDark}
        border ${config.borderLight} ${config.borderDark}
        rounded-full font-medium
        ${className}
      `}
      role="status"
      aria-label={`Complexity: ${config.label}. ${config.description}`}
      title={config.description}
    >
      {/* Color indicator dot */}
      <span
        className={`${sizeConfig.dot} ${config.dotColor} rounded-full flex-shrink-0`}
        aria-hidden="true"
      />

      {/* Label text */}
      {showLabel && (
        <span className={sizeConfig.text}>
          {config.label}
        </span>
      )}
    </span>
  );
}

/**
 * Helper function to get complexity configuration for external use.
 */
export function getComplexityConfig(complexity: ComplexityLevel) {
  return COMPLEXITY_CONFIG[complexity];
}

export default ComplexityBadge;
