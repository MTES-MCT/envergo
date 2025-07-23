import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle("Le point d'accès unique à la réglementation et aux démarches administratives sur les haies — Guichet unique de la haie");
});
