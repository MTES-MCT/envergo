import { test, expect } from '@playwright/test';

test('Display result if department not available', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('simulateur_nav_btn').click();
  await page.dblclick('#map', { position: { x: 300, y: 215 } });
  await page.getByLabel('Nouveaux impacts').fill('500');
  await page.getByLabel('État final').fill('500');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — Envergo");
  await expect(page.getByText("Le simulateur Envergo n'est pas encore déployé dans votre département.")).toBeVisible();
});

test('Display a result with the available regulations', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('simulateur_nav_btn').click();
  await page.dblclick('#map', { position: { x: 270, y: 185 } });
  await page.getByLabel('Nouveaux impacts').fill('500');
  await page.getByLabel('État final').fill('500');
  await page.getByRole('button', { name: 'Démarrer la simulation' }).click();
  await expect(page).toHaveTitle("Simulation réglementaire du projet — Envergo");
  await expect(page.getByText('Le projet n’est pas soumis à la Loi sur l’eau pour ce qui concerne les impacts')).toBeVisible();
  await expect(page.getByText('Le projet n\'est pas soumis à Natura 2000')).toBeVisible();
  await expect(page.getByText('Le projet n’est pas soumis à Évaluation Environnementale')).toBeVisible();
  await expect(page.getByText('Les règlements de SAGE (Schéma d’Aménagement et de Gestion des Eaux) seront prochainement pris en compte dans ce département.')).toBeVisible();
});
