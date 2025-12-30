'use client';

/**
 * AgentTrace component for visualizing LangGraph state streams.
 *
 * Features:
 * - Live visualization of agent state transitions via WebSocket
 * - "Thought bubble" showing agent reasoning in real-time
 * - Expandable/collapsible trace sections
 * - Color-coded status indicators:
 *   - Planning: blue
 *   - Coding: yellow
 *   - Validating: green
 *   - Error: red
 * - Timestamp for each state transition
 * - Auto-scroll to latest entry with option to lock
 * - Support for trace replay from persisted data
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { AgentTraceProps, TraceNode as TraceNodeType } from '@/types/trace';
import { ConnectionState, TraceStatus } from '@/types/trace';
import { useAgentStream } from '@/hooks/useAgentStream';
import { TraceNode } from '@/components/trace/TraceNode';

/**
 * Connection status indicator component.
 */
function ConnectionIndicator({ state }: { state: ConnectionState }) {
  const stateConfig: Record<ConnectionState, { color: string; label: string; pulse: boolean }> = {
    [ConnectionState.CONNECTED]: { color: 'bg-green-500', label: 'Connected', pulse: false },
    [ConnectionState.CONNECTING]: { color: 'bg-yellow-500', label: 'Connecting...', pulse: true },
    [ConnectionState.RECONNECTING]: { color: 'bg-yellow-500', label: 'Reconnecting...', pulse: true },
    [ConnectionState.DISCONNECTED]: { color: 'bg-gray-400', label: 'Disconnected', pulse: false },
    [ConnectionState.ERROR]: { color: 'bg-red-500', label: 'Error', pulse: false },
  };

  const config = stateConfig[state];

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="relative flex h-3 w-3">
        {config.pulse && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.color} opacity-75`} />
        )}
        <span className={`relative inline-flex rounded-full h-3 w-3 ${config.color}`} />
      </span>
      <span className="text-gray-600 dark:text-gray-400">{config.label}</span>
    </div>
  );
}

/**
 * Empty state component for when there are no traces.
 */
function EmptyState({ isReplay }: { isReplay?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-500 dark:text-gray-400">
      <svg
        className="h-16 w-16 mb-4 text-gray-300 dark:text-gray-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <p className="text-lg font-medium">No trace data available</p>
      <p className="text-sm mt-1">
        {isReplay
          ? 'Load persisted trace data to view the trace history.'
          : 'Waiting for agent activity...'}
      </p>
    </div>
  );
}

/**
 * Header component with controls.
 */
function TraceHeader({
  workflowId,
  connectionState,
  traceCount,
  autoScroll,
  onToggleAutoScroll,
  onClear,
  isReplay,
}: {
  workflowId: string;
  connectionState: ConnectionState;
  traceCount: number;
  autoScroll: boolean;
  onToggleAutoScroll: () => void;
  onClear: () => void;
  isReplay?: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Agent Trace
        </h2>
        {!isReplay && <ConnectionIndicator state={connectionState} />}
        {isReplay && (
          <span className="px-2 py-0.5 bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200 text-xs font-medium rounded">
            Replay Mode
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {traceCount} {traceCount === 1 ? 'event' : 'events'}
        </span>

        <span className="text-gray-300 dark:text-gray-600">|</span>

        <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
          {workflowId.slice(0, 8)}...
        </span>

        {!isReplay && (
          <>
            <button
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                autoScroll
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
              }`}
              onClick={onToggleAutoScroll}
              aria-pressed={autoScroll}
              title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
            >
              {autoScroll ? 'Auto-scroll: On' : 'Auto-scroll: Off'}
            </button>

            <button
              className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-400 rounded-md transition-colors"
              onClick={onClear}
              title="Clear trace history"
            >
              Clear
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * "Thought bubble" component showing current agent reasoning.
 */
function ThoughtBubble({ node }: { node: TraceNodeType | null }) {
  if (!node) return null;

  const isActive =
    node.status === TraceStatus.PLANNING ||
    node.status === TraceStatus.CODING ||
    node.status === TraceStatus.VALIDATING;

  if (!isActive) return null;

  return (
    <div className="mx-4 mb-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800 rounded-lg shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <div className="relative">
            <div className="h-10 w-10 rounded-full bg-blue-500 flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {node.agentName.charAt(0).toUpperCase()}
              </span>
            </div>
            <span className="absolute bottom-0 right-0 block h-3 w-3 rounded-full bg-green-400 ring-2 ring-white dark:ring-gray-800 animate-pulse" />
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {node.agentName} is {node.status.toLowerCase()}...
          </p>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            {node.content}
          </p>
          {node.details?.toolName && (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-500">
              Using tool: <span className="font-mono">{node.details.toolName}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Main AgentTrace component for live visualization of agent state transitions.
 */
export function AgentTrace({
  workflowId,
  token,
  autoScroll: initialAutoScroll = true,
  persistedData,
  className = '',
  isReplay = false,
}: AgentTraceProps) {
  // State for UI controls
  const [autoScroll, setAutoScroll] = useState(initialAutoScroll);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Refs for auto-scroll functionality
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const endOfTraceRef = useRef<HTMLDivElement>(null);

  // Connect to WebSocket stream (or use persisted data for replay)
  const { state, actions } = useAgentStream({
    autoReconnect: !isReplay,
    onTraceEvent: (event) => {
      console.debug('Trace event received:', event);
    },
  });

  // Connect on mount (for live mode)
  useEffect(() => {
    if (!isReplay && workflowId) {
      actions.connect(workflowId, token);
      return () => {
        actions.disconnect();
      };
    }
    return undefined;
  }, [workflowId, token, isReplay, actions]);

  // Load persisted data for replay mode
  useEffect(() => {
    if (isReplay && persistedData) {
      actions.loadPersistedTrace(persistedData);
    }
  }, [isReplay, persistedData, actions]);

  // Auto-scroll to bottom when new traces arrive
  useEffect(() => {
    if (autoScroll && endOfTraceRef.current) {
      endOfTraceRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.traceNodes.length, autoScroll]);

  // Detect manual scroll to disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current || !autoScroll) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

    if (!isAtBottom) {
      setAutoScroll(false);
    }
  }, [autoScroll]);

  // Toggle node expansion
  const handleToggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []);

  // Handle copy action
  const handleCopy = useCallback((content: string) => {
    console.debug('Copied trace content:', content.slice(0, 100) + '...');
  }, []);

  // Toggle auto-scroll
  const handleToggleAutoScroll = useCallback(() => {
    setAutoScroll((prev) => !prev);
    if (!autoScroll && endOfTraceRef.current) {
      endOfTraceRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [autoScroll]);

  // Clear trace
  const handleClear = useCallback(() => {
    actions.clearTrace();
    setExpandedNodes(new Set());
  }, [actions]);

  // Get the most recent active node for thought bubble
  const activeNode = state.traceNodes
    .slice()
    .reverse()
    .find(
      (node) =>
        node.status === TraceStatus.PLANNING ||
        node.status === TraceStatus.CODING ||
        node.status === TraceStatus.VALIDATING
    ) ?? null;

  const traceNodes = state.traceNodes;

  return (
    <div
      className={`flex flex-col h-full bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden ${className}`}
      role="region"
      aria-label="Agent trace visualization"
    >
      {/* Header */}
      <TraceHeader
        workflowId={workflowId}
        connectionState={state.connectionState}
        traceCount={traceNodes.length}
        autoScroll={autoScroll}
        onToggleAutoScroll={handleToggleAutoScroll}
        onClear={handleClear}
        isReplay={isReplay}
      />

      {/* Thought bubble */}
      {!isReplay && activeNode && (
        <div className="flex-shrink-0 pt-4">
          <ThoughtBubble node={activeNode} />
        </div>
      )}

      {/* Error display */}
      {state.error && (
        <div className="mx-4 mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-700 dark:text-red-300">
            <span className="font-medium">Connection Error:</span> {state.error}
          </p>
          {state.retryAttempt > 0 && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              Retry attempt {state.retryAttempt} of 5
            </p>
          )}
        </div>
      )}

      {/* Trace list */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4"
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="Trace entries"
      >
        {traceNodes.length === 0 ? (
          <EmptyState isReplay={isReplay} />
        ) : (
          <>
            {traceNodes.map((node) => (
              <TraceNode
                key={node.id}
                node={node}
                isExpanded={expandedNodes.has(node.id)}
                onToggleExpand={handleToggleExpand}
                onCopy={handleCopy}
                nestingLevel={node.parentId ? 1 : 0}
              />
            ))}
            {/* Scroll anchor */}
            <div ref={endOfTraceRef} aria-hidden="true" />
          </>
        )}
      </div>

      {/* Footer with scroll-to-bottom button */}
      {!autoScroll && traceNodes.length > 0 && (
        <div className="flex-shrink-0 p-2 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
          <button
            className="w-full py-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium"
            onClick={handleToggleAutoScroll}
          >
            Jump to latest and enable auto-scroll
          </button>
        </div>
      )}
    </div>
  );
}

export default AgentTrace;
