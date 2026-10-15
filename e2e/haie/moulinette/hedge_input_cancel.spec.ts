import { test, expect } from '@playwright/test';

// Leaving the hedge input with drawn hedges asks for a confirmation,
// and nothing is saved when the user quits.
test('Quitting the hedge input without saving asks for confirmation', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Déposer un dossier' }).click();
    await page.getByRole('link', { name: 'Loire-Atlantique (44)' }).click();
    await page.getByText('Haies ou alignements d’arbres').click();
    await page.getByText('Toute intervention supprimant définitivement la végétation').click();
    await page.getByText('Uniquement les travaux sur la végétation').click();
    await page.getByRole('button', { name: 'Valider' }).click();
    await page.getByText('Création ou élargissement d\'un accès à la parcelle').click();
    await page.locator('label').filter({ hasText: 'Oui, en plantant une haie à' }).click();
    await page.getByText('Non, aucune des haies').click();

    await page.getByRole('button', { name: 'Localiser les haies' }).click();
    const frame = page.locator('#hedge-input-iframe').contentFrame();
    await frame.getByRole('combobox', { name: 'Rechercher une commune ou une' }).click();
    await frame.getByRole('combobox', { name: 'Rechercher une commune ou une' }).fill('coueron');
    await frame.getByRole('option', { name: 'Couëron 44, Loire-Atlantique, Pays de la Loire', exact: true }).click();
    await frame.getByRole('button', { name: 'Tracer une haie à détruire' }).click();
    await frame.locator('#map').click({ position: { x: 300, y: 215 } });
    await frame.locator('#map').dblclick({ position: { x: 310, y: 215 } });
    await frame.getByRole('dialog', { name: 'Description de la haie D1' }).getByText('Haie mixte').check();
    await frame.getByRole('dialog', { name: 'Description de la haie D1' }).getByRole('button', { name: 'Enregistrer' }).click();

    // "Rester sur la carte" dismisses the confirmation and keeps the hedge
    const cancelModal = frame.locator('#cancel-modal');
    await frame.locator('footer').getByRole('button', { name: 'Quitter sans enregistrer' }).click();
    await expect(cancelModal).toBeVisible();
    await cancelModal.getByRole('button', { name: 'Rester sur la carte' }).click();
    await expect(cancelModal).toBeHidden();
    await expect(frame.locator('.hedge-list.to-remove .hedge-row')).toHaveCount(1);

    // "Quitter sans enregistrer" closes the hedge input
    await frame.locator('footer').getByRole('button', { name: 'Quitter sans enregistrer' }).click();
    await expect(cancelModal).toBeVisible();
    await cancelModal.getByRole('button', { name: 'Quitter sans enregistrer' }).click();
    await expect(page.locator('#hedge-input-modal')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Localiser les haies' })).toBeVisible();
    await expect(page.locator('#statistics-container').getByText('Aucune haie renseignée')).toBeVisible();
});
