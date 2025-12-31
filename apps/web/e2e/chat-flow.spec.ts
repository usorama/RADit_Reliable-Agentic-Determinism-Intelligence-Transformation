import { test, expect } from '@playwright/test';

test.describe('Chat Flow', () => {
  test('should load the chat interface', async ({ page }) => {
    await page.goto('/');

    // Check page title
    await expect(page).toHaveTitle(/DAW/);

    // Check header is visible
    await expect(page.getByRole('heading', { name: 'DAW' })).toBeVisible();

    // Check dev mode indicator
    await expect(page.getByText('Dev Mode (Auth Bypassed)')).toBeVisible();

    // Check chat interface elements
    await expect(page.getByText('Planner Chat')).toBeVisible();
    await expect(page.getByText('Start a conversation')).toBeVisible();

    // Check quick action buttons
    await expect(page.getByRole('button', { name: 'Build a todo app' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create an API' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Design a database' })).toBeVisible();

    // Check input area
    await expect(page.getByPlaceholder('Describe your project or ask a question...')).toBeVisible();
  });

  test('should have working message input', async ({ page }) => {
    await page.goto('/');

    const input = page.getByPlaceholder('Describe your project or ask a question...');
    await expect(input).toBeVisible();

    // Type a message
    await input.fill('Build a simple calculator app');

    // Verify the input value
    await expect(input).toHaveValue('Build a simple calculator app');

    // Send button should be visible (though may be disabled without backend)
    const sendButton = page.getByRole('button', { name: 'Send message' });
    await expect(sendButton).toBeVisible();
  });

  test('should click quick action button', async ({ page }) => {
    await page.goto('/');

    const todoButton = page.getByRole('button', { name: 'Build a todo app' });
    await expect(todoButton).toBeVisible();

    // Click should work without errors
    await todoButton.click();
  });
});

test.describe('Navigation', () => {
  test('should display connection status', async ({ page }) => {
    await page.goto('/');

    // Connection status should be visible (initially disconnected)
    await expect(page.getByText(/Connected|Disconnected|Connecting/)).toBeVisible();
  });
});
