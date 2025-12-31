import { test, expect } from '@playwright/test';

test.describe('Debug UI Flow', () => {
  test.setTimeout(120000);

  test('debug chat interaction and take screenshot', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Wait for page to load
    await expect(page.getByRole('heading', { name: 'DAW' })).toBeVisible();

    // Take initial screenshot
    await page.screenshot({ path: 'test-results/01-initial-state.png', fullPage: true });
    console.log('Screenshot 1: Initial state');

    // Type in the input
    const input = page.getByPlaceholder('Describe your project or ask a question...');
    await input.fill('Build a simple calculator app');
    await page.screenshot({ path: 'test-results/02-typed-input.png', fullPage: true });
    console.log('Screenshot 2: After typing');

    // Click send
    const sendButton = page.getByRole('button', { name: 'Send message' });
    await sendButton.click();
    console.log('Clicked send button');

    // Wait a bit and take screenshot
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'test-results/03-after-send.png', fullPage: true });
    console.log('Screenshot 3: 3 seconds after send');

    // Wait longer for LLM response
    await page.waitForTimeout(30000);
    await page.screenshot({ path: 'test-results/04-after-30s.png', fullPage: true });
    console.log('Screenshot 4: 30 seconds after send');

    // Print page content for debugging
    const bodyText = await page.locator('body').textContent();
    console.log('Page content preview:', bodyText?.substring(0, 500));

    // Look for any messages in the chat
    const messages = await page.locator('[class*="message"], [class*="chat"], .prose').all();
    console.log('Found message-like elements:', messages.length);
    for (let i = 0; i < Math.min(messages.length, 5); i++) {
      const text = await messages[i].textContent();
      console.log(`Message ${i}:`, text?.substring(0, 100));
    }
  });
});
