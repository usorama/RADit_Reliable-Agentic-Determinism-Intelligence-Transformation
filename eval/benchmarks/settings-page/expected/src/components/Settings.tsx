import React, { useState, useEffect, useCallback } from 'react';

/**
 * Theme type - supports light and dark modes
 */
type Theme = 'light' | 'dark';

/**
 * Props for the Settings component
 */
interface SettingsProps {
  /** Callback fired when theme changes */
  onThemeChange?: (theme: Theme) => void;
  /** Initial theme value, defaults to 'light' */
  initialTheme?: Theme;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Settings page component with theme toggle functionality.
 *
 * @example
 * ```tsx
 * <Settings
 *   onThemeChange={(theme) => console.log('Theme:', theme)}
 *   initialTheme="dark"
 * />
 * ```
 */
export const Settings: React.FC<SettingsProps> = ({
  onThemeChange,
  initialTheme = 'light',
  className = '',
}) => {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [isSaved, setIsSaved] = useState<boolean>(false);

  // Load theme from localStorage on mount
  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem('daw-theme') as Theme | null;
      if (savedTheme === 'light' || savedTheme === 'dark') {
        setTheme(savedTheme);
      }
    } catch (error) {
      // Handle localStorage errors gracefully (e.g., private browsing)
      console.warn('Unable to access localStorage:', error);
    }
  }, []);

  // Save theme to localStorage when it changes
  useEffect(() => {
    try {
      localStorage.setItem('daw-theme', theme);
    } catch (error) {
      console.warn('Unable to save to localStorage:', error);
    }
  }, [theme]);

  /**
   * Toggle between light and dark theme
   */
  const toggleTheme = useCallback(() => {
    const newTheme: Theme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    onThemeChange?.(newTheme);

    // Show save confirmation
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  }, [theme, onThemeChange]);

  /**
   * Handle keyboard events for accessibility
   */
  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleTheme();
    }
  }, [toggleTheme]);

  return (
    <div
      className={`p-6 max-w-2xl mx-auto ${className}`}
      data-testid="settings-page"
    >
      {/* Page Header */}
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Settings
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Manage your application preferences
        </p>
      </header>

      {/* Theme Section */}
      <section
        className="mb-8 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
        aria-labelledby="theme-heading"
      >
        <h2
          id="theme-heading"
          className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200"
        >
          Appearance
        </h2>

        <div className="flex items-center justify-between">
          <div>
            <label
              htmlFor="theme-toggle"
              className="text-gray-700 dark:text-gray-300 font-medium"
            >
              Theme
            </label>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Current: {theme === 'light' ? 'Light Mode' : 'Dark Mode'}
            </p>
          </div>

          <button
            id="theme-toggle"
            onClick={toggleTheme}
            onKeyDown={handleKeyDown}
            className="px-4 py-2 rounded-md bg-blue-500 hover:bg-blue-600
                       text-white font-medium transition-colors duration-200
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            aria-pressed={theme === 'dark'}
            data-testid="theme-toggle-button"
          >
            {theme === 'light' ? 'Switch to Dark' : 'Switch to Light'}
          </button>
        </div>
      </section>

      {/* User Preferences Section */}
      <section
        className="mb-8 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
        aria-labelledby="preferences-heading"
      >
        <h2
          id="preferences-heading"
          className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200"
        >
          User Preferences
        </h2>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label
              htmlFor="notifications"
              className="text-gray-700 dark:text-gray-300"
            >
              Enable Notifications
            </label>
            <input
              type="checkbox"
              id="notifications"
              className="w-5 h-5 text-blue-500 rounded focus:ring-blue-500"
              aria-describedby="notifications-description"
              data-testid="notifications-checkbox"
            />
          </div>
          <p
            id="notifications-description"
            className="text-sm text-gray-500 dark:text-gray-400"
          >
            Receive updates about task completion and system events
          </p>
        </div>
      </section>

      {/* Save Confirmation */}
      {isSaved && (
        <div
          className="fixed bottom-4 right-4 px-4 py-2 bg-green-500 text-white
                     rounded-md shadow-lg animate-fade-in"
          role="status"
          aria-live="polite"
          data-testid="save-confirmation"
        >
          Settings saved successfully
        </div>
      )}
    </div>
  );
};

export default Settings;
