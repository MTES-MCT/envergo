import { test, expect } from '@playwright/test';

test('Display a result with the available regulations', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('simulateur_nav_btn').click();
  await page.dblclick('#map', { position: { x: 340, y: 230 } });
  await page.getByLabel('Nouveaux impacts').fill('500');
  await page.getByLabel('État final').fill('500');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — EnvErgo");
  await expect(page.getByRole('heading', { name: 'Loi sur l\'eau Non soumis' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Règlement de SAGE Non disponible' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Natura 2000 Non soumis' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Évaluation environnementale (rubrique 39) Non soumis' })).toBeVisible();
});

test('Display a result with the available regulations and additionnal questions', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('simulateur_nav_btn').click();
  await page.dblclick('#map', { position: { x: 340, y: 230 } });
  await page.getByLabel('Nouveaux impacts').fill('10000');
  await page.getByLabel('État final').fill('10000');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page.getByRole('heading', { name: 'Questions complémentaires' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Emprise au sol totale' }).click();
  await page.getByRole('textbox', { name: 'Emprise au sol totale' }).fill('10000');
  await page.getByText('Supérieure ou égale à 10 000').click();
  await page.getByRole('textbox', { name: 'Terrain d\'assiette du projet' }).click();
  await page.getByRole('textbox', { name: 'Terrain d\'assiette du projet' }).fill('45000');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — EnvErgo");
});
