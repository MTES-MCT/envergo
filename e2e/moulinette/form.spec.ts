import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('simulateur_nav_btn').click();
  await page.getByLabel('Saisissez l\'adresse ou la commune la plus proche du projet ').fill('Vue');
  await page.getByRole('option', { name: 'Vue 44, Loire-Atlantique,' }).click();
  await page.getByLabel('Nouveaux impacts').fill('500');
  await page.getByLabel('État final').fill('500');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — EnvErgo");
});
