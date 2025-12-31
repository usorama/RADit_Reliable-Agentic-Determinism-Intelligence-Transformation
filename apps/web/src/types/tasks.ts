/**
 * TypeScript types for Task List Review component.
 *
 * These types correspond to the backend schemas defined in
 * apps/server/src/daw_server/api/schemas.py
 */

// -----------------------------------------------------------------------------
// Enums
// -----------------------------------------------------------------------------

/**
 * Task type classification.
 */
export type TaskType = 'setup' | 'code' | 'test' | 'docs';

/**
 * Task complexity level.
 */
export type TaskComplexity = 'low' | 'medium' | 'high';

/**
 * Story priority level.
 */
export type StoryPriority = 'P0' | 'P1' | 'P2';

/**
 * Task review action.
 */
export type TaskReviewAction = 'approve' | 'reject';

// -----------------------------------------------------------------------------
// Core Types
// -----------------------------------------------------------------------------

/**
 * A single atomic task in the workflow.
 */
export interface Task {
  /** Unique identifier for the task */
  id: string;
  /** Description of what the task accomplishes */
  description: string;
  /** Task type classification */
  type: TaskType;
  /** Complexity level */
  complexity: TaskComplexity;
  /** List of task IDs this task depends on */
  dependencies: string[];
  /** Optional estimated hours to complete */
  estimatedHours?: number;
}

/**
 * A user story containing multiple tasks.
 */
export interface Story {
  /** Unique identifier for the story */
  id: string;
  /** Story title */
  title: string;
  /** Priority level */
  priority: StoryPriority;
  /** List of tasks belonging to this story */
  tasks: Task[];
}

/**
 * A development phase containing multiple stories.
 */
export interface Phase {
  /** Unique identifier for the phase */
  id: string;
  /** Phase name */
  name: string;
  /** Phase description */
  description: string;
  /** List of stories in this phase */
  stories: Story[];
}

/**
 * A dependency relationship between tasks.
 */
export interface Dependency {
  /** ID of the source task */
  sourceId: string;
  /** ID of the target task (depends on source) */
  targetId: string;
}

// -----------------------------------------------------------------------------
// API Response Types
// -----------------------------------------------------------------------------

/**
 * Response from GET /api/workflow/{id}/tasks endpoint.
 */
export interface TasksListResponse {
  /** List of development phases */
  phases: Phase[];
  /** Flat list of all stories */
  stories: Story[];
  /** Flat list of all tasks */
  tasks: Task[];
  /** List of task dependencies */
  dependencies: Dependency[];
}

/**
 * Request for POST /api/workflow/{id}/tasks-review endpoint.
 */
export interface TaskReviewRequest {
  /** The review action (approve or reject) */
  action: TaskReviewAction;
  /** Optional feedback comment (required for reject) */
  feedback?: string;
}

/**
 * Response from POST /api/workflow/{id}/tasks-review endpoint.
 */
export interface TaskReviewResponse {
  /** Whether the action was successful */
  success: boolean;
  /** The workflow ID */
  workflow_id: string;
  /** The new workflow status after the action */
  status: string;
  /** Description of what happened */
  message: string;
}

// -----------------------------------------------------------------------------
// Component Props
// -----------------------------------------------------------------------------

/**
 * Props for the TaskList component.
 */
export interface TaskListProps {
  /** Workflow ID to fetch tasks for */
  workflowId: string;
  /** Callback when tasks are approved */
  onApprove: () => void;
  /** Callback when tasks are rejected with feedback */
  onReject: (feedback: string) => void;
}

/**
 * Props for the TaskTreeNode component.
 */
export interface TaskTreeNodeProps {
  /** The task to display */
  task: Task;
  /** Whether this task is expanded */
  isExpanded: boolean;
  /** Callback to toggle expansion */
  onToggle: (taskId: string) => void;
  /** Nesting level for indentation */
  level?: number;
  /** IDs of tasks that this task depends on */
  dependsOn?: string[];
  /** Whether to show dependency indicators */
  showDependencies?: boolean;
}

/**
 * Props for the DependencyGraph component.
 */
export interface DependencyGraphProps {
  /** List of all tasks */
  tasks: Task[];
  /** List of dependencies */
  dependencies: Dependency[];
  /** Optional selected task ID */
  selectedTaskId?: string;
  /** Callback when a task is selected */
  onTaskSelect?: (taskId: string) => void;
  /** Custom class name */
  className?: string;
}

// -----------------------------------------------------------------------------
// Hook Types
// -----------------------------------------------------------------------------

/**
 * State for the useTasks hook.
 */
export interface UseTasksState {
  /** Whether tasks are loading */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** Tasks data */
  data: TasksListResponse | null;
  /** Whether a review action is in progress */
  isReviewing: boolean;
}

/**
 * Return type for the useTasks hook.
 */
export interface UseTasksReturn {
  /** Current state */
  state: UseTasksState;
  /** Fetch tasks for a workflow */
  fetchTasks: () => Promise<void>;
  /** Approve tasks */
  approveTasks: () => Promise<boolean>;
  /** Reject tasks with feedback */
  rejectTasks: (feedback: string) => Promise<boolean>;
  /** Clear error */
  clearError: () => void;
}

// -----------------------------------------------------------------------------
// Utility Types
// -----------------------------------------------------------------------------

/**
 * Map of task type to display configuration.
 */
export const TASK_TYPE_CONFIG: Record<
  TaskType,
  {
    label: string;
    icon: string;
    color: string;
  }
> = {
  setup: {
    label: 'Setup',
    icon: '🔧',
    color: 'text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-300',
  },
  code: {
    label: 'Code',
    icon: '💻',
    color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-300',
  },
  test: {
    label: 'Test',
    icon: '🧪',
    color: 'text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-300',
  },
  docs: {
    label: 'Docs',
    icon: '📝',
    color: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-300',
  },
};

/**
 * Map of priority to display configuration.
 */
export const PRIORITY_CONFIG: Record<
  StoryPriority,
  {
    label: string;
    color: string;
  }
> = {
  P0: {
    label: 'Critical',
    color: 'text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-300',
  },
  P1: {
    label: 'High',
    color: 'text-orange-600 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-300',
  },
  P2: {
    label: 'Medium',
    color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-300',
  },
};
