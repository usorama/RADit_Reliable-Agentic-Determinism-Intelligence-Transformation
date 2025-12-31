'use client';

/**
 * PersonaFeedbackCard - Displays feedback from roundtable personas.
 *
 * Shows critique from expert personas (CTO, UX Lead, Security Expert) including:
 * - Persona avatar/icon with role indicator
 * - Main feedback summary
 * - List of concerns (collapsible)
 * - List of recommendations (collapsible)
 *
 * Features:
 * - Role-specific color coding
 * - Expandable concerns/recommendations sections
 * - Accessible card structure
 * - Dark mode compatible
 *
 * @example
 * ```tsx
 * <PersonaFeedbackCard
 *   persona="CTO"
 *   feedback="Architecture looks solid but consider scaling implications."
 *   concerns={["Database may become a bottleneck at scale"]}
 *   recommendations={["Consider sharding strategy early"]}
 * />
 * ```
 */

import React, { useState, useCallback } from 'react';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** Available persona roles */
export type PersonaRole = 'CTO' | 'UX Lead' | 'Security Expert';

export interface PersonaFeedbackProps {
  /** The persona providing feedback */
  persona: PersonaRole;
  /** Main feedback text */
  feedback: string;
  /** List of concerns raised */
  concerns: string[];
  /** List of recommendations */
  recommendations: string[];
  /** Custom class name */
  className?: string;
  /** Whether the card starts with details expanded */
  defaultExpanded?: boolean;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

/**
 * Configuration for each persona role.
 */
const PERSONA_CONFIG: Record<
  PersonaRole,
  {
    title: string;
    description: string;
    bgColor: string;
    textColor: string;
    borderColor: string;
    iconBgColor: string;
    icon: React.ReactNode;
  }
> = {
  CTO: {
    title: 'Chief Technology Officer',
    description: 'Technical architecture and scalability',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    textColor: 'text-blue-700 dark:text-blue-300',
    borderColor: 'border-blue-200 dark:border-blue-800',
    iconBgColor: 'bg-blue-600 dark:bg-blue-500',
    icon: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
        />
      </svg>
    ),
  },
  'UX Lead': {
    title: 'User Experience Lead',
    description: 'User interface and experience design',
    bgColor: 'bg-purple-50 dark:bg-purple-900/20',
    textColor: 'text-purple-700 dark:text-purple-300',
    borderColor: 'border-purple-200 dark:border-purple-800',
    iconBgColor: 'bg-purple-600 dark:bg-purple-500',
    icon: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"
        />
      </svg>
    ),
  },
  'Security Expert': {
    title: 'Security Expert',
    description: 'Security and compliance review',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    textColor: 'text-red-700 dark:text-red-300',
    borderColor: 'border-red-200 dark:border-red-800',
    iconBgColor: 'bg-red-600 dark:bg-red-500',
    icon: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
        />
      </svg>
    ),
  },
};

// -----------------------------------------------------------------------------
// Sub-Components
// -----------------------------------------------------------------------------

/**
 * Expandable list section for concerns or recommendations.
 */
function DetailsList({
  title,
  items,
  type,
  isExpanded,
  onToggle,
}: {
  title: string;
  items: string[];
  type: 'concerns' | 'recommendations';
  isExpanded: boolean;
  onToggle: () => void;
}) {
  if (items.length === 0) return null;

  const iconColor = type === 'concerns'
    ? 'text-amber-500 dark:text-amber-400'
    : 'text-green-500 dark:text-green-400';

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
        aria-expanded={isExpanded}
      >
        <svg
          className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {title}
        <span className="text-gray-500 dark:text-gray-400">({items.length})</span>
      </button>

      {isExpanded && (
        <ul className="mt-2 ml-6 space-y-2" role="list">
          {items.map((item, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
              <span className={`mt-0.5 flex-shrink-0 ${iconColor}`} aria-hidden="true">
                {type === 'concerns' ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                  </svg>
                )}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export function PersonaFeedbackCard({
  persona,
  feedback,
  concerns,
  recommendations,
  className = '',
  defaultExpanded = false,
}: PersonaFeedbackProps) {
  const [isConcernsExpanded, setIsConcernsExpanded] = useState(defaultExpanded);
  const [isRecommendationsExpanded, setIsRecommendationsExpanded] = useState(defaultExpanded);

  const config = PERSONA_CONFIG[persona];

  const toggleConcerns = useCallback(() => {
    setIsConcernsExpanded((prev) => !prev);
  }, []);

  const toggleRecommendations = useCallback(() => {
    setIsRecommendationsExpanded((prev) => !prev);
  }, []);

  return (
    <article
      className={`
        p-4 rounded-lg border
        ${config.bgColor} ${config.borderColor}
        ${className}
      `}
      aria-labelledby={`persona-${persona.replace(/\s+/g, '-').toLowerCase()}`}
    >
      {/* Header with avatar and role */}
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div
          className={`
            flex-shrink-0 w-10 h-10 rounded-full
            ${config.iconBgColor}
            flex items-center justify-center
          `}
          aria-hidden="true"
        >
          {config.icon}
        </div>

        {/* Persona Info */}
        <div className="flex-1 min-w-0">
          <h4
            id={`persona-${persona.replace(/\s+/g, '-').toLowerCase()}`}
            className={`font-semibold ${config.textColor}`}
          >
            {persona}
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {config.description}
          </p>
        </div>
      </div>

      {/* Main Feedback */}
      <div className="mt-3">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          {feedback}
        </p>
      </div>

      {/* Concerns Section */}
      <DetailsList
        title="Concerns"
        items={concerns}
        type="concerns"
        isExpanded={isConcernsExpanded}
        onToggle={toggleConcerns}
      />

      {/* Recommendations Section */}
      <DetailsList
        title="Recommendations"
        items={recommendations}
        type="recommendations"
        isExpanded={isRecommendationsExpanded}
        onToggle={toggleRecommendations}
      />
    </article>
  );
}

export default PersonaFeedbackCard;
