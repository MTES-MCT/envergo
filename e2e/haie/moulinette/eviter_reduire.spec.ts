import { test, expect } from '@playwright/test';

// The « Éviter / réduire » block appears once the form is valid and the
// project removes RU or HRU hedges. When the motif changes, it swaps its
// message and unchecks the box; the submission is gated behind a
// "J'ai compris" checkbox.
test('The éviter / réduire block gates the simulation submission', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Simuler un projet' }).click();
    await page.getByRole('link', { name: 'Loire-Atlantique (44)' }).click();
    await page.getByText('Haies ou alignements d’arbres').click();
    await page.getByText('Toute intervention supprimant définitivement la végétation').click();
    await page.getByText('Uniquement les travaux sur la végétation').click();
    await page.getByRole('button', { name: 'Valider' }).click();

    // Fill the main form. "Non" to PAC so no additional question interferes.
    await page.getByText('Création ou élargissement d\'un accès à la parcelle').click();
    await page.locator('label').filter({ hasText: 'Oui, en plantant une haie à' }).click();
    await page.getByText('Non, aucune des haies').click();

    // Draw a single "haie mixte" hedge: intrinsic category RU
    await page.getByRole('button', { name: 'Localiser les haies' }).click();
    const frame = page.locator('#hedge-input-iframe').contentFrame();
    await frame.getByRole('combobox', { name: 'Rechercher une commune ou une' }).click();
    await frame.getByRole('combobox', { name: 'Rechercher une commune ou une' }).fill('coueron');
    await frame.getByRole('option', { name: 'Couëron 44, Loire-Atlantique, Pays de la Loire', exact: true }).click();
    await frame.getByRole('button', { name: 'Tracer une haie à détruire' }).click();
    await frame.locator('#map').click({ position: { x: 300, y: 215 } });
    await frame.locator('#map').dblclick({ position: { x: 310, y: 215 } });
    await frame.getByRole('dialog', { name: 'Description de la haie D1' }).getByText('Haie mixte').check();
    await frame.getByLabel('Description de la haie D1').getByRole('button', { name: 'Enregistrer' }).click();
    await frame.locator('footer').getByRole('button', { name: 'Enregistrer', exact: true }).click();

    // First submission: the block appears, unchecked, without error
    await page.getByRole('button', { name: 'Valider' }).click();
    const block = page.locator('#eviter-reduire');
    await expect(block.getByText('Évitement et réduction des impacts')).toBeVisible();
    await expect(block.getByRole('checkbox', { name: "J'ai compris" })).not.toBeChecked();
    await expect(page.getByText('Vous devez confirmer avoir pris connaissance')).not.toBeVisible();

    // The message matches the selected motif
    await expect(block.locator('[data-motif="chemin_acces"]')).toBeVisible();
    await expect(block.locator('[data-motif="securite"]')).toBeHidden();

    // Submitting without checking shows the validation error
    await page.getByRole('button', { name: 'Valider' }).click();
    await expect(page.getByText('Vous devez confirmer avoir pris connaissance de cette information.')).toBeVisible();

    // Changing the motif swaps the message and unchecks the box
    await block.getByRole('checkbox', { name: "J'ai compris" }).check();
    await page.getByText('Mise en sécurité, risque sanitaire').click();
    await expect(block.locator('[data-motif="securite"]')).toBeVisible();
    await expect(block.locator('[data-motif="chemin_acces"]')).toBeHidden();
    await expect(block.getByRole('checkbox', { name: "J'ai compris" })).not.toBeChecked();

    // Acknowledging lets the submission through to the result page
    await block.getByRole('checkbox', { name: "J'ai compris" }).check();
    await page.getByRole('button', { name: 'Valider' }).click();
    await expect(page).toHaveURL(/resultat/);
    // The acknowledgment never leaks into the simulation url
    await expect(page).not.toHaveURL(/eviter_reduire/);
});
