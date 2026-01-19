import { test, expect } from '@playwright/test';

test('Instructor can instruct a project', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Administration' }).click();
    await page.getByRole('textbox', { name: 'Email address' }).fill('user@test.fr');
    await page.getByRole('textbox', { name: 'Password' }).fill('Sésame');
    await page.getByRole('textbox', { name: 'Password' }).press('Enter');
    await page.getByRole('link', { name: '123456' }).click();

    await expect(page.getByRole('heading', { name: 'Résumé du dossier' })).toBeVisible();
    await expect(page.getByText('Informations saisies par le demandeur')).toBeVisible();
    await expect(page.getByText('Réponse du simulateur').first()).toBeVisible();
    await expect(page.getByText('La plantation envisagée est adéquate')).toBeVisible();

    await page.getByRole('button', { name: 'Réglementations' }).click();
    await page.getByRole('link', { name: 'Espèces protégées', exact: true }).click();

    await expect(page.getByRole('heading', { name: 'Espèces protégées', level: 1 })).toBeVisible();
    await expect(page.getByText('Informations saisies par le demandeur').first()).toBeVisible();
    await expect(page.getByText('Formulaire complet et pièces jointes')).toBeVisible();
    await expect(page.getByText('Réponse du simulateur').first()).toBeVisible();
    await expect(page.getByText('Détails du résultat de la simulation')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Acceptabilité de la plantation', level: 3 })).toBeVisible();
    await expect(page.getByText('Précisions sur le calcul d\'acceptabilité de la plantation')).toBeVisible();

    await page.getByRole('link', { name: 'Dossier complet', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Dossier complet' })).toBeVisible();
    await expect(page.getByText('Formulaire détaillé et pièces jointes')).toBeVisible();
    await expect(page.getByText('Informations saisies par le demandeur')).toBeVisible();
});
