/**
 * QuestionInput Component - Renders appropriate input for question types.
 *
 * Features:
 * - Text input for free-form responses
 * - Radio buttons for single choice (multi_choice)
 * - Checkboxes for multiple selection (checkbox)
 * - Accessibility with proper labels and ARIA attributes
 * - Keyboard navigation support
 * - Focus management
 * - Validation indicators
 */

'use client';

import React, { useCallback, useEffect, useRef, useState, KeyboardEvent } from 'react';
import type { Question, QuestionInputProps } from '@/types/interview';

// -----------------------------------------------------------------------------
// Text Input Component
// -----------------------------------------------------------------------------

interface TextInputProps {
  question: Question;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  inputId: string;
}

function TextInput({
  question,
  value,
  onChange,
  onSubmit,
  disabled,
  inputId,
}: TextInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [value]);

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, [question.id]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Submit on Ctrl+Enter or Cmd+Enter
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (!disabled && value.trim()) {
          onSubmit();
        }
      }
    },
    [disabled, value, onSubmit]
  );

  return (
    <div className="w-full">
      <label
        htmlFor={inputId}
        className="sr-only"
      >
        {question.text}
      </label>
      <textarea
        ref={textareaRef}
        id={inputId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Type your answer here..."
        rows={3}
        className={`
          w-full px-4 py-3 rounded-lg border-2 transition-colors resize-none
          ${
            disabled
              ? 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 cursor-not-allowed'
              : 'bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 dark:focus:ring-blue-800'
          }
          text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400
          focus:outline-none
        `}
        aria-required={question.required}
        aria-describedby={question.context ? `${inputId}-context` : undefined}
      />
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
        Press Ctrl+Enter (Cmd+Enter on Mac) to submit
      </p>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Multi Choice Input Component (Radio Buttons)
// -----------------------------------------------------------------------------

interface MultiChoiceInputProps {
  question: Question;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  inputId: string;
}

function MultiChoiceInput({
  question,
  value,
  onChange,
  onSubmit,
  disabled,
  inputId,
}: MultiChoiceInputProps) {
  const firstOptionRef = useRef<HTMLInputElement>(null);

  // Focus first option on mount
  useEffect(() => {
    firstOptionRef.current?.focus();
  }, [question.id]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      // Submit on Enter when an option is selected
      if (e.key === 'Enter' && value) {
        e.preventDefault();
        if (!disabled) {
          onSubmit();
        }
      }
    },
    [disabled, value, onSubmit]
  );

  if (!question.options || question.options.length === 0) {
    return (
      <p className="text-red-500 dark:text-red-400">
        No options available for this question.
      </p>
    );
  }

  return (
    <div
      role="radiogroup"
      aria-labelledby={inputId}
      onKeyDown={handleKeyDown}
      className="space-y-2"
    >
      {question.options.map((option, index) => {
        const optionId = `${inputId}-option-${index}`;
        const isSelected = value === option;

        return (
          <label
            key={optionId}
            htmlFor={optionId}
            className={`
              flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all
              ${
                disabled
                  ? 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 cursor-not-allowed'
                  : isSelected
                  ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-500'
                  : 'bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800'
              }
            `}
          >
            <input
              ref={index === 0 ? firstOptionRef : undefined}
              type="radio"
              id={optionId}
              name={inputId}
              value={option}
              checked={isSelected}
              onChange={(e) => onChange(e.target.value)}
              disabled={disabled}
              className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 focus:ring-2"
            />
            <span className="text-gray-900 dark:text-white">{option}</span>
          </label>
        );
      })}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Checkbox Input Component (Multiple Selection)
// -----------------------------------------------------------------------------

interface CheckboxInputProps {
  question: Question;
  value: string[];
  onChange: (value: string[]) => void;
  onSubmit: () => void;
  disabled: boolean;
  inputId: string;
}

function CheckboxInput({
  question,
  value,
  onChange,
  onSubmit,
  disabled,
  inputId,
}: CheckboxInputProps) {
  const firstCheckboxRef = useRef<HTMLInputElement>(null);

  // Focus first checkbox on mount
  useEffect(() => {
    firstCheckboxRef.current?.focus();
  }, [question.id]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      // Submit on Ctrl+Enter when at least one option is selected
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && value.length > 0) {
        e.preventDefault();
        if (!disabled) {
          onSubmit();
        }
      }
    },
    [disabled, value, onSubmit]
  );

  const handleCheckboxChange = useCallback(
    (option: string, checked: boolean) => {
      if (checked) {
        onChange([...value, option]);
      } else {
        onChange(value.filter((v) => v !== option));
      }
    },
    [value, onChange]
  );

  if (!question.options || question.options.length === 0) {
    return (
      <p className="text-red-500 dark:text-red-400">
        No options available for this question.
      </p>
    );
  }

  return (
    <div
      role="group"
      aria-labelledby={inputId}
      onKeyDown={handleKeyDown}
      className="space-y-2"
    >
      {question.options.map((option, index) => {
        const optionId = `${inputId}-option-${index}`;
        const isSelected = value.includes(option);

        return (
          <label
            key={optionId}
            htmlFor={optionId}
            className={`
              flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all
              ${
                disabled
                  ? 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 cursor-not-allowed'
                  : isSelected
                  ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-500'
                  : 'bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800'
              }
            `}
          >
            <input
              ref={index === 0 ? firstCheckboxRef : undefined}
              type="checkbox"
              id={optionId}
              name={inputId}
              value={option}
              checked={isSelected}
              onChange={(e) => handleCheckboxChange(option, e.target.checked)}
              disabled={disabled}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
            />
            <span className="text-gray-900 dark:text-white">{option}</span>
          </label>
        );
      })}
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
        Select all that apply. Press Ctrl+Enter (Cmd+Enter on Mac) to submit.
      </p>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main QuestionInput Component
// -----------------------------------------------------------------------------

export function QuestionInput({
  question,
  value,
  onChange,
  onSubmit,
  disabled = false,
  inputId = 'question-input',
}: QuestionInputProps) {
  // Ensure value is the correct type for the question type
  const [localValue, setLocalValue] = useState<string | string[]>(() => {
    if (question.type === 'checkbox') {
      return Array.isArray(value) ? value : [];
    }
    return typeof value === 'string' ? value : '';
  });

  // Update local value when question changes
  useEffect(() => {
    if (question.type === 'checkbox') {
      setLocalValue(Array.isArray(value) ? value : []);
    } else {
      setLocalValue(typeof value === 'string' ? value : '');
    }
  }, [question.id, question.type, value]);

  // Handle value changes
  const handleChange = useCallback(
    (newValue: string | string[]) => {
      setLocalValue(newValue);
      onChange(newValue);
    },
    [onChange]
  );

  // Check if answer is valid for submission
  const isAnswerValid = useCallback(() => {
    if (!question.required) return true;

    if (question.type === 'checkbox') {
      return Array.isArray(localValue) && localValue.length > 0;
    }
    return typeof localValue === 'string' && localValue.trim().length > 0;
  }, [question.required, question.type, localValue]);

  // Handle submit with validation
  const handleSubmit = useCallback(() => {
    if (isAnswerValid() && !disabled) {
      onSubmit();
    }
  }, [isAnswerValid, disabled, onSubmit]);

  return (
    <div className="w-full">
      {/* Question text */}
      <div className="mb-4">
        <h3
          id={inputId}
          className="text-lg font-medium text-gray-900 dark:text-white mb-1"
        >
          {question.text}
          {question.required && (
            <span className="text-red-500 ml-1" aria-hidden="true">
              *
            </span>
          )}
        </h3>
        {question.context && (
          <p
            id={`${inputId}-context`}
            className="text-sm text-gray-600 dark:text-gray-400"
          >
            {question.context}
          </p>
        )}
      </div>

      {/* Input based on question type */}
      {question.type === 'text' && (
        <TextInput
          question={question}
          value={typeof localValue === 'string' ? localValue : ''}
          onChange={(v) => handleChange(v)}
          onSubmit={handleSubmit}
          disabled={disabled}
          inputId={inputId}
        />
      )}

      {question.type === 'multi_choice' && (
        <MultiChoiceInput
          question={question}
          value={typeof localValue === 'string' ? localValue : ''}
          onChange={(v) => handleChange(v)}
          onSubmit={handleSubmit}
          disabled={disabled}
          inputId={inputId}
        />
      )}

      {question.type === 'checkbox' && (
        <CheckboxInput
          question={question}
          value={Array.isArray(localValue) ? localValue : []}
          onChange={(v) => handleChange(v)}
          onSubmit={handleSubmit}
          disabled={disabled}
          inputId={inputId}
        />
      )}

      {/* Required field indicator */}
      {question.required && (
        <p className="sr-only">This question is required.</p>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Exports
// -----------------------------------------------------------------------------

export default QuestionInput;
