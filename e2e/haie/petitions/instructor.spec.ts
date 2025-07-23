import { test, expect } from '@playwright/test';

test('Instructor can instruct a project', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Administration' }).click();
  await page.getByRole('textbox', { name: 'Email address' }).fill('user@test.fr');
  await page.getByRole('textbox', { name: 'Password' }).fill('Sésame');
  await page.getByRole('textbox', { name: 'Password' }).press('Enter');
  await page.getByRole('link', { name: 'Dossier EGRAZY en détail' }).click();

  await expect(page.getByRole('heading', { name: 'Informations générales' })).toBeVisible();
  await expect(page.getByText('Éléments clés')).toBeVisible();
  await expect(page.getByText('Résultats de la simulation')).toBeVisible();
  await expect(page.getByText('La plantation envisagée est adéquate')).toBeVisible();

  await page.getByRole('button', { name: 'Réglementations' }).click();
  await page.getByRole('link', { name: 'Espèces protégées', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Espèces protégées', level: 2 })).toBeVisible();
  await expect(page.getByText('Données saisies pour la simulation')).toBeVisible();
  await expect(page.getByText('Formulaire détaillé et pièces jointes')).toBeVisible();
  await expect(page.getByText('Résultats de la simulation')).toBeVisible();
  await expect(page.getByText('Détails du résultat de la simulation')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Acceptabilité de la plantation', level: 3})).toBeVisible();
  await expect(page.getByText('Détails du calcul d\'acceptabilité de la plantation')).toBeVisible();

  await page.getByRole('link', { name: 'Dossier complet', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Dossier complet'})).toBeVisible();
  await expect(page.getByText('Formulaire détaillé et pièces jointes')).toBeVisible();
  await expect(page.getByText('Données saisies pour la simulation')).toBeVisible();

  await page.getByRole('button', { name: 'Inviter une personne à' }).click();
  await expect(page.getByRole('button', { name: 'Copier le message dans le' })).toBeVisible();
});
