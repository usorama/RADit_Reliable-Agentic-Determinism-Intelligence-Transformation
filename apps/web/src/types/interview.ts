/**
 * TypeScript types for Interview/Clarification Flow.
 *
 * This module defines the data types for:
 * - Question: Interview question structure
 * - Answer: User's answer to a question
 * - InterviewState: Overall interview state
 * - WebSocket events for real-time question updates
 */

// -----------------------------------------------------------------------------
// Question Types
// -----------------------------------------------------------------------------

/**
 * Types of questions that can be asked during the interview.
 */
export type QuestionType = 'text' | 'multi_choice' | 'checkbox';

/**
 * A single interview question from the Planner agent.
 */
export interface Question {
  /** Unique identifier for the question */
  id: string;
  /** Type of input expected */
  type: QuestionType;
  /** The question text to display */
  text: string;
  /** Available options for multi_choice and checkbox types */
  options?: string[];
  /** Whether the question must be answered */
  required: boolean;
  /** Optional help text or context for the question */
  context?: string;
}

/**
 * A user's answer to an interview question.
 */
export interface Answer {
  /** Question ID this answer is for */
  questionId: string;
  /** The answer value - string for text, string for multi_choice, string[] for checkbox */
  value: string | string[];
  /** When the answer was submitted */
  timestamp: Date;
}

// -----------------------------------------------------------------------------
// Interview State
// -----------------------------------------------------------------------------

/**
 * Status of the interview flow.
 */
export enum InterviewStatus {
  /** Interview not yet started */
  NOT_STARTED = 'not_started',
  /** Interview is in progress */
  IN_PROGRESS = 'in_progress',
  /** Interview completed successfully */
  COMPLETED = 'completed',
  /** Interview was skipped by user */
  SKIPPED = 'skipped',
  /** An error occurred during the interview */
  ERROR = 'error',
}

/**
 * Overall interview state managed by useInterview hook.
 */
export interface InterviewState {
  /** Current question being displayed */
  currentQuestion: Question | null;
  /** Index of current question (0-based) */
  currentIndex: number;
  /** Total number of questions */
  totalQuestions: number;
  /** All answers collected so far */
  answers: Answer[];
  /** Current interview status */
  status: InterviewStatus;
  /** Whether an operation is in progress */
  isLoading: boolean;
  /** Current error if any */
  error: string | null;
  /** Whether the interview is complete */
  isComplete: boolean;
}

// -----------------------------------------------------------------------------
// WebSocket Event Types
// -----------------------------------------------------------------------------

/**
 * Types of interview-related WebSocket events.
 */
export enum InterviewEventType {
  /** A new question is ready */
  QUESTION = 'INTERVIEW_QUESTION',
  /** Answer was acknowledged */
  ANSWER_ACKNOWLEDGED = 'INTERVIEW_ANSWER_ACKNOWLEDGED',
  /** Interview completed */
  COMPLETE = 'INTERVIEW_COMPLETE',
  /** Interview error */
  ERROR = 'INTERVIEW_ERROR',
  /** Interview progress update */
  PROGRESS = 'INTERVIEW_PROGRESS',
}

/**
 * Base interview event from WebSocket.
 */
export interface InterviewEvent {
  event_type: InterviewEventType;
  workflow_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}

/**
 * Question event with new question data.
 */
export interface QuestionEvent extends InterviewEvent {
  event_type: InterviewEventType.QUESTION;
  data: {
    question: Question;
    currentIndex: number;
    totalQuestions: number;
  };
}

/**
 * Answer acknowledged event.
 */
export interface AnswerAcknowledgedEvent extends InterviewEvent {
  event_type: InterviewEventType.ANSWER_ACKNOWLEDGED;
  data: {
    questionId: string;
    hasNextQuestion: boolean;
  };
}

/**
 * Interview complete event.
 */
export interface InterviewCompleteEvent extends InterviewEvent {
  event_type: InterviewEventType.COMPLETE;
  data: {
    totalAnswered: number;
    skipped: boolean;
  };
}

/**
 * Interview error event.
 */
export interface InterviewErrorEvent extends InterviewEvent {
  event_type: InterviewEventType.ERROR;
  data: {
    error_message: string;
    recoverable: boolean;
  };
}

// -----------------------------------------------------------------------------
// API Types
// -----------------------------------------------------------------------------

/**
 * Request body for POST /api/workflow/{id}/interview-answer.
 */
export interface SubmitAnswerRequest {
  question_id: string;
  answer: string | string[];
}

/**
 * Response from POST /api/workflow/{id}/interview-answer.
 */
export interface SubmitAnswerResponse {
  success: boolean;
  next_question?: Question;
  current_index?: number;
  total_questions?: number;
  is_complete?: boolean;
  error?: string;
}

/**
 * Request body for POST /api/workflow/{id}/interview-skip.
 */
export interface SkipInterviewRequest {
  reason?: string;
}

/**
 * Response from POST /api/workflow/{id}/interview-skip.
 */
export interface SkipInterviewResponse {
  success: boolean;
  message: string;
}

/**
 * Response from GET /api/workflow/{id}/interview-status.
 */
export interface InterviewStatusResponse {
  status: InterviewStatus;
  current_question?: Question;
  current_index?: number;
  total_questions?: number;
  is_complete?: boolean;
}

// -----------------------------------------------------------------------------
// Hook Types
// -----------------------------------------------------------------------------

/**
 * Options for the useInterview hook.
 */
export interface UseInterviewOptions {
  /** Backend API base URL */
  apiUrl?: string;
  /** WebSocket URL */
  wsUrl?: string;
  /** Called when interview completes */
  onComplete?: () => void;
  /** Called when interview is skipped */
  onSkip?: () => void;
  /** Called when an error occurs */
  onError?: (error: string) => void;
  /** Called when a question is received */
  onQuestion?: (question: Question) => void;
}

/**
 * Return type for the useInterview hook.
 */
export interface UseInterviewReturn {
  /** Current question being displayed */
  currentQuestion: Question | null;
  /** Current question index (1-based for display) */
  currentQuestionNumber: number;
  /** Total number of questions */
  totalQuestions: number;
  /** Whether an operation is in progress */
  isLoading: boolean;
  /** Whether the interview is complete */
  isComplete: boolean;
  /** Current error if any */
  error: string | null;
  /** Submit an answer for the current question */
  submitAnswer: (answer: string | string[]) => Promise<void>;
  /** Skip remaining questions */
  skipRemaining: () => Promise<void>;
  /** Retry after an error */
  retry: () => Promise<void>;
}

// -----------------------------------------------------------------------------
// Component Props Types
// -----------------------------------------------------------------------------

/**
 * Props for ClarificationFlow component.
 */
export interface ClarificationFlowProps {
  /** Workflow ID for the interview */
  workflowId: string;
  /** Called when interview completes successfully */
  onComplete: () => void;
  /** Called when interview is skipped */
  onSkip?: () => void;
  /** Custom class name for styling */
  className?: string;
}

/**
 * Props for QuestionInput component.
 */
export interface QuestionInputProps {
  /** The question to display */
  question: Question;
  /** Current value of the input */
  value: string | string[];
  /** Called when the value changes */
  onChange: (value: string | string[]) => void;
  /** Called when user submits the answer */
  onSubmit: () => void;
  /** Whether the input is disabled */
  disabled?: boolean;
  /** ID for accessibility */
  inputId?: string;
}

/**
 * Props for ProgressIndicator component.
 */
export interface ProgressIndicatorProps {
  /** Current question number (1-based) */
  current: number;
  /** Total number of questions */
  total: number;
  /** Custom class name for styling */
  className?: string;
}

/**
 * Props for SkipConfirmationModal component.
 */
export interface SkipConfirmationModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Called when modal is closed */
  onClose: () => void;
  /** Called when skip is confirmed */
  onConfirm: () => void;
  /** Number of remaining questions */
  remainingQuestions: number;
}
