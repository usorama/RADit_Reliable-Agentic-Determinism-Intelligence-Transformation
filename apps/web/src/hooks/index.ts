/**
 * Hooks barrel export
 * Re-exports all custom hooks for convenient importing
 */

export {
  useAuth,
  useAuthToken,
  useAuthenticatedFetch,
  useUser,
  useClerk,
  type AuthState,
  type GetTokenOptions,
} from './useAuth'

export { useTasks } from './useTasks'
export type {
  UseTasksState,
  UseTasksReturn,
} from '../types/tasks'

export {
  usePRD,
  default as usePRDDefault,
  type PRDState,
  type UsePRDOptions,
  type UsePRDReturn,
} from './usePRD'

export { useInterview } from './useInterview'
export type { UseInterviewOptions, UseInterviewReturn } from '../types/interview'

export { useAgentStream, type UseAgentStreamOptions } from './useAgentStream'

export { useKanban } from './useKanban'
