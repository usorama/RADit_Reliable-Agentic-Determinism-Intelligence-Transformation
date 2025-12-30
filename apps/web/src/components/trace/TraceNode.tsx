'use client';

/**
 * TraceNode component for displaying individual trace entries.
 *
 * Features:
 * - Expandable/collapsible details section
 * - Copy button for trace content
 * - Agent name and status badge
 * - Color-coded status indicators
 * - Timestamp display
 * - Nested trace support with indentation
 */

import { useCallback, useState } from 'react';
import type { TraceNodeProps } from '@/types/trace';
import { STATUS_COLORS, TraceStatus } from '@/types/trace';

/**
 * Icons for expand/collapse buttons.
 */
function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 9l-7 7-7-7"
      />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5l7 7-7 7"
      />
    </svg>
  );
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 13l4 4L19 7"
      />
    </svg>
  );
}

/**
 * Loading spinner for in-progress states.
 */
function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className || ''}`}
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/**
 * Format a timestamp for display.
 */
function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Format duration in milliseconds to human-readable string.
 */
function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const minutes = seconds / 60;
  return `${minutes.toFixed(1)}m`;
}

/**
 * Status badge component.
 */
function StatusBadge({ status }: { status: TraceStatus }) {
  const colors = STATUS_COLORS[status];
  const isLoading = status === TraceStatus.PLANNING ||
    status === TraceStatus.CODING ||
    status === TraceStatus.VALIDATING;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
      role="status"
      aria-label={`Status: ${status}`}
    >
      {isLoading && <LoadingSpinner className="h-3 w-3" />}
      {status}
    </span>
  );
}

/**
 * TraceNode component for displaying individual trace entries.
 */
export function TraceNode({
  node,
  isExpanded,
  onToggleExpand,
  onCopy,
  nestingLevel = 0,
}: TraceNodeProps) {
  const [copied, setCopied] = useState(false);
  const colors = STATUS_COLORS[node.status];
  const hasDetails = node.details !== null;
  const indentPx = nestingLevel * 24;

  const handleCopy = useCallback(async () => {
    const contentToCopy = node.details
      ? JSON.stringify(node.details, null, 2)
      : node.content;

    try {
      await navigator.clipboard.writeText(contentToCopy);
      setCopied(true);
      onCopy(contentToCopy);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [node.details, node.content, onCopy]);

  const handleToggle = useCallback(() => {
    onToggleExpand(node.id);
  }, [node.id, onToggleExpand]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleToggle();
    }
  }, [handleToggle]);

  return (
    <div
      className={`border-l-4 ${colors.border} bg-white dark:bg-gray-800 rounded-r-lg shadow-sm mb-2 transition-all duration-200`}
      style={{ marginLeft: `${indentPx}px` }}
      role="article"
      aria-label={`Trace entry: ${node.title}`}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 rounded-tr-lg"
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        aria-controls={`trace-details-${node.id}`}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Expand/collapse icon */}
          {hasDetails && (
            <button
              className="flex-shrink-0 p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
              aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
              tabIndex={-1}
            >
              {isExpanded ? (
                <ChevronDownIcon className="h-4 w-4 text-gray-500" />
              ) : (
                <ChevronRightIcon className="h-4 w-4 text-gray-500" />
              )}
            </button>
          )}
          {!hasDetails && <div className="w-6" />}

          {/* Agent badge */}
          <span className="flex-shrink-0 px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs font-medium rounded">
            {node.agentName}
          </span>

          {/* Title */}
          <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">
            {node.title}
          </h3>

          {/* Status badge */}
          <StatusBadge status={node.status} />
        </div>

        <div className="flex items-center gap-2 flex-shrink-0 ml-3">
          {/* Duration */}
          {node.duration !== null && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {formatDuration(node.duration)}
            </span>
          )}

          {/* Timestamp */}
          <time
            className="text-xs text-gray-500 dark:text-gray-400"
            dateTime={node.timestamp.toISOString()}
          >
            {formatTimestamp(node.timestamp)}
          </time>

          {/* Copy button */}
          <button
            className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              handleCopy();
            }}
            aria-label={copied ? 'Copied!' : 'Copy trace content'}
            title={copied ? 'Copied!' : 'Copy to clipboard'}
          >
            {copied ? (
              <CheckIcon className="h-4 w-4 text-green-500" />
            ) : (
              <CopyIcon className="h-4 w-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="px-3 pb-2 pl-10">
        <p className="text-sm text-gray-600 dark:text-gray-300">{node.content}</p>
      </div>

      {/* Expandable details */}
      {hasDetails && isExpanded && (
        <div
          id={`trace-details-${node.id}`}
          className="border-t border-gray-100 dark:border-gray-700 px-3 py-3 bg-gray-50 dark:bg-gray-750 rounded-br-lg"
          role="region"
          aria-label="Trace details"
        >
          {node.details?.toolName && (
            <DetailRow label="Tool" value={node.details.toolName} />
          )}
          {node.details?.model && (
            <DetailRow label="Model" value={node.details.model} />
          )}
          {node.details?.tokenCount !== undefined && (
            <DetailRow label="Tokens" value={String(node.details.tokenCount)} />
          )}
          {node.details?.errorMessage && (
            <div className="mt-2">
              <DetailLabel>Error</DetailLabel>
              <pre className="mt-1 p-2 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-xs rounded overflow-x-auto">
                {node.details.errorMessage}
              </pre>
            </div>
          )}
          {node.details?.toolInput && (
            <div className="mt-2">
              <DetailLabel>Input</DetailLabel>
              <pre className="mt-1 p-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded overflow-x-auto">
                {JSON.stringify(node.details.toolInput, null, 2)}
              </pre>
            </div>
          )}
          {node.details?.toolOutput && (
            <div className="mt-2">
              <DetailLabel>Output</DetailLabel>
              <pre className="mt-1 p-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded overflow-x-auto max-h-48 overflow-y-auto">
                {node.details.toolOutput}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Helper component for detail rows.
 */
function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 text-sm">
      <span className="font-medium text-gray-500 dark:text-gray-400">{label}:</span>
      <span className="text-gray-700 dark:text-gray-300">{value}</span>
    </div>
  );
}

/**
 * Helper component for detail labels.
 */
function DetailLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
      {children}
    </span>
  );
}

export default TraceNode;
