/**
 * Message Component - Renders individual chat messages.
 *
 * Features:
 * - User and assistant message styling
 * - Markdown rendering with syntax highlighting
 * - Code block copy buttons
 * - Timestamp display
 * - Avatar/icon for message source
 * - Loading/streaming indicators
 * - Error display
 * - File attachment previews
 */

'use client';

import React, { useState, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ChatMessage, MessageRole, FileAttachment } from '../../types/chat';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface MessageProps {
  message: ChatMessage;
  /** Whether this is the last message in the list */
  isLast?: boolean;
}

interface CodeBlockProps {
  language: string;
  code: string;
  filename?: string;
}

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Format timestamp for display.
 */
function formatTimestamp(date: Date): string {
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  if (isToday) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  return date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format file size for display.
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// -----------------------------------------------------------------------------
// Sub-Components
// -----------------------------------------------------------------------------

/**
 * Avatar component for message sender.
 */
function Avatar({ role }: { role: MessageRole }) {
  if (role === MessageRole.USER) {
    return (
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
        U
      </div>
    );
  }

  if (role === MessageRole.ASSISTANT) {
    return (
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white">
        <svg
          className="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      </div>
    );
  }

  return (
    <div className="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center text-white text-sm font-medium">
      S
    </div>
  );
}

/**
 * Code block with copy button and syntax highlighting.
 */
function CodeBlock({ language, code, filename }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  }, [code]);

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 uppercase">{language || 'text'}</span>
          {filename && (
            <span className="text-xs text-gray-500">- {filename}</span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-white bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          aria-label={copied ? 'Copied!' : 'Copy code'}
        >
          {copied ? (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>

      {/* Code content */}
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: '1rem',
          fontSize: '0.875rem',
        }}
        showLineNumbers
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

/**
 * File attachment preview.
 */
function FileAttachmentPreview({ file }: { file: FileAttachment }) {
  const isImage = file.type.startsWith('image/');

  return (
    <div className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded-lg max-w-xs">
      {isImage && file.previewUrl ? (
        <img
          src={file.previewUrl}
          alt={file.name}
          className="w-12 h-12 object-cover rounded"
        />
      ) : (
        <div className="w-12 h-12 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded">
          <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
          {file.name}
        </p>
        <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
      </div>
    </div>
  );
}

/**
 * Typing indicator animation.
 */
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-3 py-2">
      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  );
}

/**
 * Phase badge for workflow phase display.
 */
function PhaseBadge({ phase }: { phase: string }) {
  const phaseColors: Record<string, string> = {
    interview: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    roundtable: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
    generate_prd: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    decompose_tasks: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
  };

  const colorClass = phaseColors[phase] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {phase.replace(/_/g, ' ')}
    </span>
  );
}

// -----------------------------------------------------------------------------
// Main Message Component
// -----------------------------------------------------------------------------

export function Message({ message, isLast }: MessageProps) {
  const isUser = message.role === MessageRole.USER;
  const isAssistant = message.role === MessageRole.ASSISTANT;
  const isSystem = message.role === MessageRole.SYSTEM;

  // Memoized markdown components for performance
  const markdownComponents = useMemo(
    () => ({
      code({
        inline,
        className,
        children,
        ...props
      }: {
        inline?: boolean;
        className?: string;
        children?: React.ReactNode;
      }) {
        const match = /language-(\w+)/.exec(className || '');
        const language = match ? match[1] : '';
        const code = String(children).replace(/\n$/, '');

        if (!inline && code.includes('\n')) {
          return <CodeBlock language={language} code={code} />;
        }

        return (
          <code
            className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-sm font-mono text-pink-600 dark:text-pink-400"
            {...props}
          >
            {children}
          </code>
        );
      },
      pre({ children }: { children?: React.ReactNode }) {
        return <>{children}</>;
      },
      p({ children }: { children?: React.ReactNode }) {
        return <p className="mb-3 last:mb-0">{children}</p>;
      },
      ul({ children }: { children?: React.ReactNode }) {
        return <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>;
      },
      ol({ children }: { children?: React.ReactNode }) {
        return <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>;
      },
      h1({ children }: { children?: React.ReactNode }) {
        return <h1 className="text-2xl font-bold mb-3 mt-4 first:mt-0">{children}</h1>;
      },
      h2({ children }: { children?: React.ReactNode }) {
        return <h2 className="text-xl font-bold mb-2 mt-3 first:mt-0">{children}</h2>;
      },
      h3({ children }: { children?: React.ReactNode }) {
        return <h3 className="text-lg font-semibold mb-2 mt-3 first:mt-0">{children}</h3>;
      },
      blockquote({ children }: { children?: React.ReactNode }) {
        return (
          <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic text-gray-600 dark:text-gray-400 mb-3">
            {children}
          </blockquote>
        );
      },
      a({ href, children }: { href?: string; children?: React.ReactNode }) {
        return (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            {children}
          </a>
        );
      },
      table({ children }: { children?: React.ReactNode }) {
        return (
          <div className="overflow-x-auto mb-3">
            <table className="min-w-full border border-gray-300 dark:border-gray-600">
              {children}
            </table>
          </div>
        );
      },
      th({ children }: { children?: React.ReactNode }) {
        return (
          <th className="px-3 py-2 border-b border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-800 text-left font-semibold">
            {children}
          </th>
        );
      },
      td({ children }: { children?: React.ReactNode }) {
        return (
          <td className="px-3 py-2 border-b border-gray-200 dark:border-gray-700">
            {children}
          </td>
        );
      },
    }),
    []
  );

  return (
    <div
      className={`flex gap-3 py-4 px-4 ${
        isUser ? 'flex-row-reverse' : 'flex-row'
      } ${isSystem ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''}`}
    >
      {/* Avatar */}
      <div className="flex-shrink-0">
        <Avatar role={message.role} />
      </div>

      {/* Message content */}
      <div
        className={`flex-1 min-w-0 ${
          isUser ? 'flex flex-col items-end' : 'flex flex-col items-start'
        }`}
      >
        {/* Header with timestamp and phase */}
        <div className={`flex items-center gap-2 mb-1 ${isUser ? 'flex-row-reverse' : ''}`}>
          <span className="text-xs text-gray-500">
            {formatTimestamp(message.timestamp)}
          </span>
          {message.phase && <PhaseBadge phase={message.phase} />}
        </div>

        {/* Message bubble */}
        <div
          className={`rounded-2xl px-4 py-3 max-w-[85%] ${
            isUser
              ? 'bg-blue-600 text-white rounded-tr-none'
              : isAssistant
              ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-tl-none'
              : 'bg-yellow-100 dark:bg-yellow-900 text-yellow-900 dark:text-yellow-100'
          }`}
        >
          {/* File attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {message.attachments.map((file) => (
                <FileAttachmentPreview key={file.id} file={file} />
              ))}
            </div>
          )}

          {/* Message content */}
          {message.isStreaming && !message.content ? (
            <TypingIndicator />
          ) : (
            <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : 'dark:prose-invert'}`}>
              <ReactMarkdown components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {/* Streaming indicator */}
          {message.isStreaming && message.content && (
            <span className="inline-block w-2 h-4 bg-current animate-pulse ml-1" />
          )}

          {/* Error display */}
          {message.error && (
            <div className="mt-2 p-2 bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded text-sm">
              <span className="font-medium">Error:</span> {message.error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Message;
