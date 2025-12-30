import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Settings } from '../src/components/Settings';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('Settings Component', () => {
  beforeEach(() => {
    localStorageMock.clear();
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the settings page', () => {
      render(<Settings />);

      expect(screen.getByTestId('settings-page')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    it('renders the page header with description', () => {
      render(<Settings />);

      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(
        screen.getByText('Manage your application preferences')
      ).toBeInTheDocument();
    });

    it('renders the appearance section', () => {
      render(<Settings />);

      expect(screen.getByText('Appearance')).toBeInTheDocument();
      expect(screen.getByText('Theme')).toBeInTheDocument();
    });

    it('renders the user preferences section', () => {
      render(<Settings />);

      expect(screen.getByText('User Preferences')).toBeInTheDocument();
      expect(screen.getByText('Enable Notifications')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<Settings className="custom-class" />);

      const settingsPage = screen.getByTestId('settings-page');
      expect(settingsPage).toHaveClass('custom-class');
    });
  });

  describe('Theme Toggle', () => {
    it('defaults to light theme', () => {
      render(<Settings />);

      expect(screen.getByText(/Current: Light Mode/)).toBeInTheDocument();
      expect(screen.getByText('Switch to Dark')).toBeInTheDocument();
    });

    it('respects initialTheme prop', () => {
      render(<Settings initialTheme="dark" />);

      expect(screen.getByText(/Current: Dark Mode/)).toBeInTheDocument();
      expect(screen.getByText('Switch to Light')).toBeInTheDocument();
    });

    it('toggles theme when button is clicked', async () => {
      const user = userEvent.setup();
      render(<Settings />);

      const toggleButton = screen.getByTestId('theme-toggle-button');

      // Initially light mode
      expect(screen.getByText(/Current: Light Mode/)).toBeInTheDocument();

      // Click to switch to dark
      await user.click(toggleButton);
      expect(screen.getByText(/Current: Dark Mode/)).toBeInTheDocument();
      expect(screen.getByText('Switch to Light')).toBeInTheDocument();

      // Click to switch back to light
      await user.click(toggleButton);
      expect(screen.getByText(/Current: Light Mode/)).toBeInTheDocument();
      expect(screen.getByText('Switch to Dark')).toBeInTheDocument();
    });

    it('calls onThemeChange callback when theme changes', async () => {
      const user = userEvent.setup();
      const onThemeChange = jest.fn();
      render(<Settings onThemeChange={onThemeChange} />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      await user.click(toggleButton);

      expect(onThemeChange).toHaveBeenCalledWith('dark');
      expect(onThemeChange).toHaveBeenCalledTimes(1);
    });

    it('shows save confirmation after theme change', async () => {
      const user = userEvent.setup();
      jest.useFakeTimers();

      render(<Settings />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      await user.click(toggleButton);

      // Confirmation should appear
      expect(screen.getByTestId('save-confirmation')).toBeInTheDocument();
      expect(screen.getByText('Settings saved successfully')).toBeInTheDocument();

      // Confirmation should disappear after 2 seconds
      jest.advanceTimersByTime(2000);
      await waitFor(() => {
        expect(screen.queryByTestId('save-confirmation')).not.toBeInTheDocument();
      });

      jest.useRealTimers();
    });
  });

  describe('localStorage Persistence', () => {
    it('saves theme to localStorage when changed', async () => {
      const user = userEvent.setup();
      render(<Settings />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      await user.click(toggleButton);

      expect(localStorageMock.setItem).toHaveBeenCalledWith('daw-theme', 'dark');
    });

    it('loads theme from localStorage on mount', () => {
      localStorageMock.getItem.mockReturnValueOnce('dark');

      render(<Settings />);

      expect(localStorageMock.getItem).toHaveBeenCalledWith('daw-theme');
      expect(screen.getByText(/Current: Dark Mode/)).toBeInTheDocument();
    });

    it('handles localStorage errors gracefully', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      localStorageMock.getItem.mockImplementationOnce(() => {
        throw new Error('Storage error');
      });

      // Should not throw
      expect(() => render(<Settings />)).not.toThrow();

      consoleWarnSpy.mockRestore();
    });
  });

  describe('Accessibility', () => {
    it('has accessible theme toggle button', () => {
      render(<Settings />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      expect(toggleButton).toHaveAttribute('aria-label');
      expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
    });

    it('updates aria-pressed when theme changes', async () => {
      const user = userEvent.setup();
      render(<Settings />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      expect(toggleButton).toHaveAttribute('aria-pressed', 'false');

      await user.click(toggleButton);
      expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('toggle button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onThemeChange = jest.fn();
      render(<Settings onThemeChange={onThemeChange} />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      toggleButton.focus();

      // Press Enter
      await user.keyboard('{Enter}');
      expect(onThemeChange).toHaveBeenCalledWith('dark');

      // Press Space
      await user.keyboard(' ');
      expect(onThemeChange).toHaveBeenCalledWith('light');
    });

    it('has proper heading hierarchy', () => {
      render(<Settings />);

      const h1 = screen.getByRole('heading', { level: 1 });
      expect(h1).toHaveTextContent('Settings');

      const h2Elements = screen.getAllByRole('heading', { level: 2 });
      expect(h2Elements).toHaveLength(2);
    });

    it('sections have proper aria labels', () => {
      render(<Settings />);

      expect(screen.getByLabelText('Enable Notifications')).toBeInTheDocument();
    });

    it('save confirmation has proper aria role', async () => {
      const user = userEvent.setup();
      render(<Settings />);

      const toggleButton = screen.getByTestId('theme-toggle-button');
      await user.click(toggleButton);

      const confirmation = screen.getByTestId('save-confirmation');
      expect(confirmation).toHaveAttribute('role', 'status');
      expect(confirmation).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('User Preferences Section', () => {
    it('renders notifications checkbox', () => {
      render(<Settings />);

      const checkbox = screen.getByTestId('notifications-checkbox');
      expect(checkbox).toBeInTheDocument();
      expect(checkbox).toHaveAttribute('type', 'checkbox');
    });

    it('checkbox is interactive', async () => {
      const user = userEvent.setup();
      render(<Settings />);

      const checkbox = screen.getByTestId('notifications-checkbox');
      expect(checkbox).not.toBeChecked();

      await user.click(checkbox);
      expect(checkbox).toBeChecked();
    });
  });
});
