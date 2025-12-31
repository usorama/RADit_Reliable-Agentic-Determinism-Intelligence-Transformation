'use client';

/**
 * ConnectionStatus component for displaying WebSocket connection state.
 *
 * Features:
 * - Visual indicator of connection state (connected/reconnecting/disconnected/error)
 * - Auto-refresh button
 * - Last sync timestamp display
 * - Retry attempt information when reconnecting
 * - Responsive design with dark mode support
 */

import React, { useMemo, useCallback } from 'react';
import type { ConnectionStatusProps } from '@/types/kanban';
import { ConnectionState, CONNECTION_STATE_COLORS } from '@/types/kanban';

// -----------------------------------------------------------------------------
// Icons
// -----------------------------------------------------------------------------

function RefreshIcon({ className }: { className?: string }) {
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
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

function WifiIcon({ className }: { className?: string }) {
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
        d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"
      />
    </svg>
  );
}

function WifiOffIcon({ className }: { className?: string }) {
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
        d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414"
      />
    </svg>
  );
}

function ExclamationCircleIcon({ className }: { className?: string }) {
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
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

/**
 * Get the icon for a connection state.
 */
function getStateIcon(state: ConnectionState): React.ReactNode {
  const iconClass = 'h-4 w-4';
  switch (state) {
    case ConnectionState.CONNECTED:
      return <WifiIcon className={iconClass} />;
    case ConnectionState.CONNECTING:
    case ConnectionState.RECONNECTING:
      return <RefreshIcon className={`${iconClass} animate-spin`} />;
    case ConnectionState.DISCONNECTED:
      return <WifiOffIcon className={iconClass} />;
    case ConnectionState.ERROR:
      return <ExclamationCircleIcon className={iconClass} />;
    default:
      return <WifiOffIcon className={iconClass} />;
  }
}

/**
 * Get the human-readable label for a connection state.
 */
function getStateLabel(state: ConnectionState): string {
  switch (state) {
    case ConnectionState.CONNECTED:
      return 'Connected';
    case ConnectionState.CONNECTING:
      return 'Connecting...';
    case ConnectionState.RECONNECTING:
      return 'Reconnecting...';
    case ConnectionState.DISCONNECTED:
      return 'Disconnected';
    case ConnectionState.ERROR:
      return 'Connection Error';
    default:
      return 'Unknown';
  }
}

/**
 * Format a timestamp for display.
 */
function formatLastSync(timestamp: string | null): string {
  if (!timestamp) {
    return 'Never';
  }

  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);

  if (diffSeconds < 60) {
    return 'Just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  } else {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
}

// -----------------------------------------------------------------------------
// ConnectionStatus Component
// -----------------------------------------------------------------------------

export function ConnectionStatus({
  state,
  lastSync,
  retryAttempt = 0,
  maxRetries = 5,
  onRefresh,
}: ConnectionStatusProps) {
  const colors = CONNECTION_STATE_COLORS[state];
  const isReconnecting = state === ConnectionState.RECONNECTING;
  const isError = state === ConnectionState.ERROR;
  const isDisconnected = state === ConnectionState.DISCONNECTED;
  const showRefresh = (isError || isDisconnected) && onRefresh;

  const formattedLastSync = useMemo(() => formatLastSync(lastSync), [lastSync]);

  const handleRefresh = useCallback(() => {
    if (onRefresh) {
      onRefresh();
    }
  }, [onRefresh]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if ((event.key === 'Enter' || event.key === ' ') && onRefresh) {
        event.preventDefault();
        onRefresh();
      }
    },
    [onRefresh]
  );

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${colors.bg} ${colors.text}`}
      role="status"
      aria-live="polite"
    >
      {/* Status dot */}
      <span className={`flex-shrink-0 h-2 w-2 rounded-full ${colors.dot}`} aria-hidden="true" />

      {/* Icon */}
      <span className="flex-shrink-0" aria-hidden="true">
        {getStateIcon(state)}
      </span>

      {/* Label */}
      <span className="text-sm font-medium">
        {getStateLabel(state)}
        {isReconnecting && retryAttempt > 0 && (
          <span className="ml-1 text-xs opacity-75">
            ({retryAttempt}/{maxRetries})
          </span>
        )}
      </span>

      {/* Last sync time */}
      {state === ConnectionState.CONNECTED && (
        <span className="text-xs opacity-75 border-l border-current/30 pl-2 ml-1">
          Synced: {formattedLastSync}
        </span>
      )}

      {/* Refresh button */}
      {showRefresh && (
        <button
          onClick={handleRefresh}
          onKeyDown={handleKeyDown}
          className="ml-2 p-1 rounded hover:bg-white/20 dark:hover:bg-black/20 transition-colors"
          aria-label="Retry connection"
          title="Retry connection"
        >
          <RefreshIcon className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export default ConnectionStatus;
