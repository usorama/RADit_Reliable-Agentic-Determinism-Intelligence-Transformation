import { test, expect } from '@playwright/test';

test.describe('Notion-Style Note App - Full Flow', () => {
  // Increase timeout for LLM responses
  test.setTimeout(120000);

  test('should generate tasks for a Notion-style note taking app', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Verify the app loads
    await expect(page.getByRole('heading', { name: 'DAW' })).toBeVisible();
    await expect(page.getByText('Dev Mode (Auth Bypassed)')).toBeVisible();

    // Find the input field
    const input = page.getByPlaceholder('Describe your project or ask a question...');
    await expect(input).toBeVisible();

    // Type the project request
    await input.fill('Build a Notion-style note taking app with rich text editing, nested pages, and real-time collaboration');

    // Find and click the send button
    const sendButton = page.getByRole('button', { name: 'Send message' });
    await expect(sendButton).toBeVisible();
    await sendButton.click();

    // Wait for the LLM response - look for message indicating tasks were generated
    // The actual response is: "I've analyzed your requirements and generated X tasks"
    await expect(page.getByText(/I've analyzed your requirements and generated \d+ tasks/i)).toBeVisible({
      timeout: 90000,
    });

    // Check that we get a response with task count
    const responseText = await page.locator('.prose, [class*="message"], [class*="response"]').first().textContent();
    console.log('LLM Response:', responseText?.substring(0, 200));

    // Verify we got a meaningful response (not an error)
    expect(responseText).toBeTruthy();
    expect(responseText?.toLowerCase()).not.toContain('error');
  });

  test('should display quick action buttons (placeholder - not functional yet)', async ({ page }) => {
    await page.goto('/');

    // Quick action buttons are visible but don't have onClick handlers yet
    const todoButton = page.getByRole('button', { name: 'Build a todo app' });
    await expect(todoButton).toBeVisible();

    const apiButton = page.getByRole('button', { name: 'Create an API' });
    await expect(apiButton).toBeVisible();

    const dbButton = page.getByRole('button', { name: 'Design a database' });
    await expect(dbButton).toBeVisible();

    console.log('Quick action buttons are visible (functionality to be added)');
  });
});
