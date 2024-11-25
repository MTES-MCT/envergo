import { test, expect } from '@playwright/test';

test('Display a result with the available regulations', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('simulateur_nav_btn').click();
  await page.getByLabel('Search for the address to center the map').fill('Vue');
  await page.getByRole('option', { name: 'Vue 44, Loire-Atlantique,' }).click();
  await page.getByLabel('Nouveaux impacts').fill('500');
  await page.getByLabel('État final').fill('500');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — EnvErgo");
  await expect(page.getByRole('heading', { name: 'Loi sur l\'eau Non soumis' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Règlement de SAGE Non disponible' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Natura 2000 Non soumis' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Évaluation environnementale (rubrique 39) Non soumis' })).toBeVisible();
});
