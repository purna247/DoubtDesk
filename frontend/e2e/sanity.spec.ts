import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.setContent('<h1>Hello Playwright</h1>');
  await expect(page.locator('h1')).toHaveText('Hello Playwright');
});
