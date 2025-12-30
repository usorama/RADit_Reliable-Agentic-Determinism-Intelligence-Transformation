/**
 * ChatInterface Component - Primary user entry point for Planner interaction.
 *
 * Features:
 * - Message input with send button
 * - Message history with proper scroll behavior
 * - File attachment with drag and drop
 * - Typing indicators during agent response
 * - Connection status display
 * - Keyboard shortcuts (Enter to send, Shift+Enter for newline)
 * - Responsive design
 * - Accessible (WCAG 2.1 AA)
 */

'use client';

import React, { useRef, useEffect, useState, useCallback, DragEvent } from 'react';
import { Message } from './chat/Message';
import { useChat } from '../hooks/useChat';
import { ConnectionStatus, FileAttachment } from '../types/chat';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface ChatInterfaceProps {
  /** Backend API base URL */
  apiUrl?: string;
  /** WebSocket URL */
  wsUrl?: string;
  /** Initial workflow ID to resume */
  initialWorkflowId?: string;
  /** Called when a new workflow is created */
  onWorkflowCreated?: (workflowId: string) => void;
  /** Custom class name */
  className?: string;
}

// -----------------------------------------------------------------------------
// Sub-Components
// -----------------------------------------------------------------------------

/**
 * Connection status indicator.
 */
function ConnectionStatusBadge({ status }: { status: ConnectionStatus }) {
  const statusConfig: Record<ConnectionStatus, { color: string; text: string }> = {
    [ConnectionStatus.CONNECTED]: { color: 'bg-green-500', text: 'Connected' },
    [ConnectionStatus.CONNECTING]: { color: 'bg-yellow-500', text: 'Connecting...' },
    [ConnectionStatus.DISCONNECTED]: { color: 'bg-gray-400', text: 'Disconnected' },
    [ConnectionStatus.RECONNECTING]: { color: 'bg-orange-500', text: 'Reconnecting...' },
    [ConnectionStatus.ERROR]: { color: 'bg-red-500', text: 'Error' },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
      <span className={`w-2 h-2 rounded-full ${config.color} animate-pulse`} />
      <span>{config.text}</span>
    </div>
  );
}

/**
 * File preview badge for pending attachments.
 */
function FilePreviewBadge({
  file,
  onRemove,
}: {
  file: FileAttachment;
  onRemove: () => void;
}) {
  const isImage = file.type.startsWith('image/');

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
      {isImage && file.previewUrl ? (
        <img
          src={file.previewUrl}
          alt={file.name}
          className="w-8 h-8 object-cover rounded"
        />
      ) : (
        <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      )}
      <span className="text-sm text-gray-700 dark:text-gray-300 truncate max-w-[150px]">
        {file.name}
      </span>
      <button
        onClick={onRemove}
        className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
        aria-label={`Remove ${file.name}`}
      >
        <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

/**
 * Empty state when no messages.
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="w-16 h-16 mb-4 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
        <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
        Start a conversation
      </h2>
      <p className="text-gray-600 dark:text-gray-400 max-w-md">
        Describe your project idea or ask a question. The Planner agent will help you break it down
        into actionable tasks.
      </p>
      <div className="mt-6 flex flex-wrap gap-2 justify-center">
        {[
          'Build a todo app',
          'Create an API',
          'Design a database',
        ].map((suggestion) => (
          <button
            key={suggestion}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full text-sm text-gray-700 dark:text-gray-300 transition-colors"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Typing indicator for assistant.
 */
function TypingIndicator() {
  return (
    <div className="flex items-center gap-3 py-4 px-4">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      </div>
      <div className="flex items-center gap-1 px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-tl-none">
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main ChatInterface Component
// -----------------------------------------------------------------------------

export function ChatInterface({
  apiUrl,
  wsUrl,
  initialWorkflowId,
  onWorkflowCreated,
  className = '',
}: ChatInterfaceProps) {
  // Chat hook
  const {
    state,
    sendMessage,
    clearMessages,
    retryLastMessage,
    cancelResponse,
    addFile,
    removeFile,
    clearPendingFiles,
  } = useChat({
    apiUrl,
    wsUrl,
    initialWorkflowId,
    onMessage: (message) => {
      if (message.workflowId && onWorkflowCreated) {
        onWorkflowCreated(message.workflowId);
      }
    },
  });

  // Local state
  const [inputValue, setInputValue] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages, state.isTyping]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [inputValue]);

  // Handle message send
  const handleSend = useCallback(async () => {
    if (inputValue.trim() || state.pendingFiles.length > 0) {
      const message = inputValue.trim();
      setInputValue('');
      await sendMessage(message);
    }
  }, [inputValue, state.pendingFiles.length, sendMessage]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Handle file selection
  const handleFileSelect = useCallback(
    async (files: FileList | null) => {
      if (!files) return;

      for (const file of Array.from(files)) {
        await addFile(file);
      }
    },
    [addFile]
  );

  // Handle drag and drop
  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    async (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);

      const files = e.dataTransfer.files;
      await handleFileSelect(files);
    },
    [handleFileSelect]
  );

  // Handle file input change
  const handleFileInputChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      await handleFileSelect(e.target.files);
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [handleFileSelect]
  );

  const hasMessages = state.messages.length > 0;

  return (
    <div
      className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
            Planner Chat
          </h1>
          {state.workflowId && (
            <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
              {state.workflowId.slice(0, 8)}...
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <ConnectionStatusBadge status={state.connectionStatus} />
          {hasMessages && (
            <button
              onClick={clearMessages}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          <EmptyState />
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {state.messages.map((message, index) => (
              <Message
                key={message.id}
                message={message}
                isLast={index === state.messages.length - 1}
              />
            ))}
            {state.isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Error display */}
      {state.error && (
        <div className="px-4 py-2 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800">
          <div className="flex items-center justify-between">
            <span className="text-sm text-red-700 dark:text-red-300">{state.error}</span>
            <button
              onClick={retryLastMessage}
              className="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200 font-medium"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Pending files */}
      {state.pendingFiles.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 flex flex-wrap gap-2">
          {state.pendingFiles.map((file) => (
            <FilePreviewBadge
              key={file.id}
              file={file}
              onRemove={() => removeFile(file.id)}
            />
          ))}
          <button
            onClick={clearPendingFiles}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <div
          className={`flex items-end gap-2 p-2 rounded-xl border-2 transition-colors ${
            isDragOver
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : 'border-gray-200 dark:border-gray-700 focus-within:border-blue-500'
          }`}
        >
          {/* File upload button */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileInputChange}
            className="hidden"
            aria-label="Upload files"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            aria-label="Attach file"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          </button>

          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your project or ask a question..."
            rows={1}
            className="flex-1 resize-none bg-transparent border-none outline-none text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400"
            aria-label="Message input"
            disabled={state.isLoading}
          />

          {/* Send/Cancel button */}
          {state.isLoading ? (
            <button
              onClick={cancelResponse}
              className="p-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors"
              aria-label="Cancel"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() && state.pendingFiles.length === 0}
              className="p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg transition-colors disabled:cursor-not-allowed"
              aria-label="Send message"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </button>
          )}
        </div>

        {/* Drag and drop hint */}
        {isDragOver && (
          <div className="mt-2 text-center text-sm text-blue-600 dark:text-blue-400">
            Drop files here to attach
          </div>
        )}

        {/* Keyboard hint */}
        <div className="mt-2 text-xs text-gray-400 text-center">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;
