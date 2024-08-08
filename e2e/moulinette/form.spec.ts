import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Simulateur' }).click();
  await page.getByLabel('Saisissez l\'adresse ou la').fill('Vue');
  await page.getByRole('option', { name: 'Vue 44, Loire-Atlantique,' }).click();
  await page.getByLabel('Nouveaux impacts Surface au').fill('500');
  await page.getByLabel('État final – facultatif').fill('500');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await page.getByText('Oui').click();
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — EnvErgo");
});
