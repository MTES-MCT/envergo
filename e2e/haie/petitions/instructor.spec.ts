import { test, expect } from '@playwright/test';

test('Instructor can instruct a project', async ({ page }) => {
  await page.goto('/');
});
