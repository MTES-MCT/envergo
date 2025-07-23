import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle("EnvErgo : évaluez à quelles réglementations environnementales est soumis un projet de construction — EnvErgo");
});
