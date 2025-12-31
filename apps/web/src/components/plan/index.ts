/**
 * Plan Components barrel export
 * Re-exports all plan-related components for convenient importing
 */

// PRD Presentation components
export { PlanPresentation, default as PlanPresentationDefault } from './PlanPresentation';
export type {
  PlanPresentationProps,
  PRD,
  UserStory,
  TechSpec,
  PersonaFeedback,
} from './PlanPresentation';

export { ExpandableSection, default as ExpandableSectionDefault } from './ExpandableSection';
export type { ExpandableSectionProps } from './ExpandableSection';

export {
  ComplexityBadge,
  getComplexityConfig,
  default as ComplexityBadgeDefault,
} from './ComplexityBadge';
export type { ComplexityBadgeProps, ComplexityLevel } from './ComplexityBadge';

export { PersonaFeedbackCard, default as PersonaFeedbackCardDefault } from './PersonaFeedbackCard';
export type { PersonaFeedbackProps, PersonaRole } from './PersonaFeedbackCard';

// Clarification flow components
export { ClarificationFlow } from './ClarificationFlow';
export { ProgressIndicator, StepIndicator } from './ProgressIndicator';
export { QuestionInput } from './QuestionInput';

// Re-export types for convenience
export type {
  ClarificationFlowProps,
  ProgressIndicatorProps,
  QuestionInputProps,
  SkipConfirmationModalProps,
} from '@/types/interview';
