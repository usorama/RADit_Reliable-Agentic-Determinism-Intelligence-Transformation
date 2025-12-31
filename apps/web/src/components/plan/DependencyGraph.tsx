'use client';

/**
 * DependencyGraph - Visual representation of task dependencies.
 *
 * Features:
 * - SVG-based directed graph visualization
 * - Task nodes with type and complexity indicators
 * - Dependency arrows between tasks
 * - Interactive task selection
 * - Responsive layout with automatic positioning
 *
 * @example
 * ```tsx
 * <DependencyGraph
 *   tasks={tasks}
 *   dependencies={dependencies}
 *   selectedTaskId={selectedId}
 *   onTaskSelect={handleSelect}
 * />
 * ```
 */

import React, { useCallback, useMemo, useRef, useEffect, useState } from 'react';
import { ComplexityBadge, ComplexityLevel } from './ComplexityBadge';
import {
  Task,
  Dependency,
  DependencyGraphProps,
  TASK_TYPE_CONFIG,
  TaskComplexity,
} from '../../types/tasks';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface NodePosition {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface LayoutNode {
  task: Task;
  level: number;
  index: number;
  position: NodePosition;
}

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

const NODE_WIDTH = 200;
const NODE_HEIGHT = 60;
const HORIZONTAL_GAP = 80;
const VERTICAL_GAP = 40;
const PADDING = 40;
const ARROW_SIZE = 8;

// Color mapping for task types
const TYPE_COLORS: Record<Task['type'], string> = {
  setup: '#9333ea', // purple
  code: '#3b82f6', // blue
  test: '#22c55e', // green
  docs: '#eab308', // yellow
};

// -----------------------------------------------------------------------------
// Layout Algorithm
// -----------------------------------------------------------------------------

/**
 * Calculate the level (depth) of each task based on dependencies.
 */
function calculateLevels(
  tasks: Task[],
  dependencies: Dependency[]
): Map<string, number> {
  const levels = new Map<string, number>();
  const dependencyMap = new Map<string, string[]>();

  // Build dependency map (task -> tasks it depends on)
  for (const dep of dependencies) {
    const deps = dependencyMap.get(dep.targetId) || [];
    deps.push(dep.sourceId);
    dependencyMap.set(dep.targetId, deps);
  }

  // Calculate levels using BFS
  const calculateLevel = (taskId: string): number => {
    if (levels.has(taskId)) {
      return levels.get(taskId)!;
    }

    const deps = dependencyMap.get(taskId) || [];
    if (deps.length === 0) {
      levels.set(taskId, 0);
      return 0;
    }

    const maxDepLevel = Math.max(...deps.map(calculateLevel));
    const level = maxDepLevel + 1;
    levels.set(taskId, level);
    return level;
  };

  for (const task of tasks) {
    calculateLevel(task.id);
  }

  return levels;
}

/**
 * Layout tasks in a hierarchical graph structure.
 */
function layoutGraph(tasks: Task[], dependencies: Dependency[]): LayoutNode[] {
  const levels = calculateLevels(tasks, dependencies);
  const taskMap = new Map(tasks.map((t) => [t.id, t]));

  // Group tasks by level
  const levelGroups = new Map<number, Task[]>();
  for (const task of tasks) {
    const level = levels.get(task.id) || 0;
    const group = levelGroups.get(level) || [];
    group.push(task);
    levelGroups.set(level, group);
  }

  // Create layout nodes
  const layoutNodes: LayoutNode[] = [];
  const maxLevel = Math.max(...levels.values(), 0);

  for (let level = 0; level <= maxLevel; level++) {
    const tasksInLevel = levelGroups.get(level) || [];
    const levelHeight = tasksInLevel.length * (NODE_HEIGHT + VERTICAL_GAP) - VERTICAL_GAP;

    for (let index = 0; index < tasksInLevel.length; index++) {
      const task = tasksInLevel[index];
      const x = PADDING + level * (NODE_WIDTH + HORIZONTAL_GAP);
      const y =
        PADDING +
        index * (NODE_HEIGHT + VERTICAL_GAP) +
        (maxLevel > 0 ? 0 : (600 - levelHeight) / 2);

      layoutNodes.push({
        task,
        level,
        index,
        position: {
          x,
          y,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
        },
      });
    }
  }

  return layoutNodes;
}

// -----------------------------------------------------------------------------
// Task Node Component
// -----------------------------------------------------------------------------

interface TaskNodeProps {
  node: LayoutNode;
  isSelected: boolean;
  onSelect: (taskId: string) => void;
}

function TaskNode({ node, isSelected, onSelect }: TaskNodeProps) {
  const { task, position } = node;
  const typeConfig = TASK_TYPE_CONFIG[task.type];
  const borderColor = TYPE_COLORS[task.type];

  const handleClick = useCallback(() => {
    onSelect(task.id);
  }, [task.id, onSelect]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onSelect(task.id);
      }
    },
    [task.id, onSelect]
  );

  return (
    <g
      transform={`translate(${position.x}, ${position.y})`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`Task: ${task.description}`}
      style={{ cursor: 'pointer' }}
    >
      {/* Background */}
      <rect
        width={position.width}
        height={position.height}
        rx={8}
        ry={8}
        fill={isSelected ? '#eff6ff' : '#ffffff'}
        stroke={isSelected ? '#3b82f6' : borderColor}
        strokeWidth={isSelected ? 2 : 1.5}
        className="transition-all duration-150"
      />

      {/* Type indicator bar */}
      <rect
        x={0}
        y={0}
        width={4}
        height={position.height}
        rx={8}
        ry={0}
        fill={borderColor}
        clipPath="url(#left-clip)"
      />
      <defs>
        <clipPath id="left-clip">
          <rect x={0} y={0} width={8} height={position.height} rx={8} ry={8} />
        </clipPath>
      </defs>

      {/* Task Type Icon */}
      <text
        x={16}
        y={position.height / 2 - 8}
        fontSize={14}
        dominantBaseline="middle"
        aria-hidden="true"
      >
        {typeConfig.icon}
      </text>

      {/* Task Type Label */}
      <text
        x={36}
        y={position.height / 2 - 8}
        fontSize={10}
        fill="#6b7280"
        fontWeight={500}
        dominantBaseline="middle"
      >
        {typeConfig.label.toUpperCase()}
      </text>

      {/* Task Description (truncated) */}
      <text
        x={16}
        y={position.height / 2 + 10}
        fontSize={12}
        fill="#111827"
        fontWeight={500}
        dominantBaseline="middle"
      >
        {task.description.length > 25
          ? `${task.description.substring(0, 22)}...`
          : task.description}
      </text>

      {/* Complexity indicator */}
      <circle
        cx={position.width - 20}
        cy={position.height / 2}
        r={6}
        fill={
          task.complexity === 'high'
            ? '#f97316'
            : task.complexity === 'medium'
            ? '#eab308'
            : '#22c55e'
        }
      />
    </g>
  );
}

// -----------------------------------------------------------------------------
// Arrow Component
// -----------------------------------------------------------------------------

interface ArrowProps {
  from: NodePosition;
  to: NodePosition;
  isHighlighted: boolean;
}

function Arrow({ from, to, isHighlighted }: ArrowProps) {
  // Calculate start and end points
  const startX = from.x + from.width;
  const startY = from.y + from.height / 2;
  const endX = to.x;
  const endY = to.y + to.height / 2;

  // Calculate control points for curved line
  const midX = (startX + endX) / 2;

  // Path for curved arrow
  const path = `
    M ${startX} ${startY}
    C ${midX} ${startY}, ${midX} ${endY}, ${endX - ARROW_SIZE} ${endY}
  `;

  // Arrow head path
  const arrowHead = `
    M ${endX - ARROW_SIZE} ${endY - ARROW_SIZE / 2}
    L ${endX} ${endY}
    L ${endX - ARROW_SIZE} ${endY + ARROW_SIZE / 2}
  `;

  return (
    <g>
      <path
        d={path}
        fill="none"
        stroke={isHighlighted ? '#3b82f6' : '#d1d5db'}
        strokeWidth={isHighlighted ? 2 : 1.5}
        strokeDasharray={isHighlighted ? undefined : undefined}
        className="transition-all duration-150"
      />
      <path
        d={arrowHead}
        fill="none"
        stroke={isHighlighted ? '#3b82f6' : '#d1d5db'}
        strokeWidth={isHighlighted ? 2 : 1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </g>
  );
}

// -----------------------------------------------------------------------------
// Legend Component
// -----------------------------------------------------------------------------

function Legend() {
  return (
    <div className="absolute bottom-4 left-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 border border-gray-200 dark:border-gray-700">
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
        Task Types
      </div>
      <div className="space-y-1">
        {(Object.keys(TASK_TYPE_CONFIG) as Task['type'][]).map((type) => {
          const config = TASK_TYPE_CONFIG[type];
          return (
            <div key={type} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-sm"
                style={{ backgroundColor: TYPE_COLORS[type] }}
              />
              <span className="text-xs text-gray-600 dark:text-gray-300">
                {config.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mt-3 mb-2">
        Complexity
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-xs text-gray-600 dark:text-gray-300">Low</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <span className="text-xs text-gray-600 dark:text-gray-300">Medium</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-orange-500" />
          <span className="text-xs text-gray-600 dark:text-gray-300">High</span>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// DependencyGraph Component
// -----------------------------------------------------------------------------

export function DependencyGraph({
  tasks,
  dependencies,
  selectedTaskId,
  onTaskSelect,
  className = '',
}: DependencyGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 400 });

  // Calculate layout
  const layoutNodes = useMemo(
    () => layoutGraph(tasks, dependencies),
    [tasks, dependencies]
  );

  // Create position map for arrows
  const positionMap = useMemo(() => {
    const map = new Map<string, NodePosition>();
    for (const node of layoutNodes) {
      map.set(node.task.id, node.position);
    }
    return map;
  }, [layoutNodes]);

  // Calculate SVG dimensions
  useEffect(() => {
    if (layoutNodes.length === 0) return;

    const maxX = Math.max(...layoutNodes.map((n) => n.position.x + n.position.width));
    const maxY = Math.max(...layoutNodes.map((n) => n.position.y + n.position.height));

    setDimensions({
      width: maxX + PADDING,
      height: maxY + PADDING,
    });
  }, [layoutNodes]);

  // Handle task selection
  const handleTaskSelect = useCallback(
    (taskId: string) => {
      onTaskSelect?.(taskId);
    },
    [onTaskSelect]
  );

  // Empty state
  if (tasks.length === 0) {
    return (
      <div
        className={`flex items-center justify-center h-64 bg-gray-50 dark:bg-gray-800 rounded-lg ${className}`}
      >
        <p className="text-gray-500 dark:text-gray-400">No tasks to display</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative overflow-auto bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 ${className}`}
    >
      <svg
        width={dimensions.width}
        height={dimensions.height}
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        className="min-w-full"
      >
        {/* Arrows (render first so they're behind nodes) */}
        <g className="arrows">
          {dependencies.map((dep, index) => {
            const fromPos = positionMap.get(dep.sourceId);
            const toPos = positionMap.get(dep.targetId);

            if (!fromPos || !toPos) return null;

            const isHighlighted =
              selectedTaskId === dep.sourceId || selectedTaskId === dep.targetId;

            return (
              <Arrow
                key={`${dep.sourceId}-${dep.targetId}-${index}`}
                from={fromPos}
                to={toPos}
                isHighlighted={isHighlighted}
              />
            );
          })}
        </g>

        {/* Nodes */}
        <g className="nodes">
          {layoutNodes.map((node) => (
            <TaskNode
              key={node.task.id}
              node={node}
              isSelected={selectedTaskId === node.task.id}
              onSelect={handleTaskSelect}
            />
          ))}
        </g>
      </svg>

      {/* Legend */}
      <Legend />
    </div>
  );
}

export default DependencyGraph;
