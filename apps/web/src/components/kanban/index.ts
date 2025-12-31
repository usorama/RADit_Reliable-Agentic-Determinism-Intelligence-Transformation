/**
 * Kanban board components barrel export.
 *
 * This module exports all Kanban board components for easy importing:
 *
 * @example
 * ```tsx
 * import { KanbanBoard, TaskCard, ColumnHeader } from '@/components/kanban';
 *
 * function WorkflowPage({ workflowId }: { workflowId: string }) {
 *   return <KanbanBoard workflowId={workflowId} />;
 * }
 * ```
 */

export { KanbanBoard, default as KanbanBoardDefault } from './KanbanBoard';
export { TaskCard, default as TaskCardDefault } from './TaskCard';
export { ColumnHeader, default as ColumnHeaderDefault } from './ColumnHeader';
export { TaskDetailPanel, default as TaskDetailPanelDefault } from './TaskDetailPanel';
export { ActivityTimeline, default as ActivityTimelineDefault } from './ActivityTimeline';
export { ConnectionStatus, default as ConnectionStatusDefault } from './ConnectionStatus';

// Re-export types for convenience
export type {
  KanbanBoardProps,
  TaskCardProps,
  ColumnHeaderProps,
  TaskDetailPanelProps,
  ActivityTimelineProps,
  ConnectionStatusProps,
  KanbanTask,
  KanbanColumn,
  ColumnInfo,
  KanbanStats,
  TaskPriority,
  DependencyStatus,
  TaskActivity,
  TaskActivityType,
  ConnectionState,
} from '@/types/kanban';
