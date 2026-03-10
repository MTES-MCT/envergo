import { test, expect } from '@playwright/test';

test('A petitioner can submit a project', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Simuler un projet' }).click();
    await page.getByRole('link', { name: 'Loire-Atlantique (44)' }).click();
    await page.getByText('Haies ou alignements d’arbres').click();
    await page.getByText('Toute intervention supprimant définitivement la végétation').click();
    await page.getByRole('button', { name: 'Valider' }).click();
    await page.getByText('Création d’un accès à la').click();
    await page.locator('label').filter({ hasText: 'Oui, en plantant une haie à' }).click();
    await page.getByText('Oui, au moins une des haies').click();
    await page.getByRole('button', { name: 'Localiser les haies' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('combobox', { name: 'Rechercher une commune ou une' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('combobox', { name: 'Rechercher une commune ou une' }).fill('coueron');
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('option', { name: 'Couëron 44, Loire-Atlantique, Pays de la Loire', exact: true }).click();
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('button', { name: 'Tracer une haie à détruire' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').click({ position: { x: 300, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').dblclick({ position: { x: 310, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('dialog', { name: 'Description de la haie D1' }).getByText("Alignement d'arbres").check();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie D1').getByText('Bord de route, voie ou chemin').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie D1').getByText('Située sur une parcelle PAC').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie D1').getByRole('button', { name: 'Enregistrer' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('button', { name: 'Tracer une haie à détruire' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').click({ position: { x: 400, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').dblclick({ position: { x: 410, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('dialog', { name: 'Description de la haie D2' }).getByText('Haie mixte').check();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie D2').getByText('Mare à moins de 200 m').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie D2').getByText('Située sur une parcelle PAC').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie D2').getByRole('button', { name: 'Enregistrer' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().locator('footer').getByRole('button', { name: 'Enregistrer', exact: true }).click();

    await page.getByRole('button', { name: 'Valider' }).click();
    await page.getByRole('textbox', { name: 'Linéaire total de haies sur l' }).click();
    await page.getByRole('textbox', { name: 'Linéaire total de haies sur l' }).fill('5000');
    await page.getByRole('button', { name: 'Valider' }).click();
    await page.getByText('Autorisation', { exact: true }).click();
    await expect(await page.getByRole('heading', { name: 'Alignements d\'arbres (L350-3' })).toContainText('Autorisation');
    await expect(await page.getByRole('heading', { name: 'Espèces protégées' })).toContainText('Dérogation allégée');
    await expect(await page.getByRole('heading', { name: 'Conditionnalité PAC' })).toContainText('Dispense');
    await expect(await page.getByRole('heading', { name: 'Natura 2000 Haie' })).toContainText('Non soumis');

    await page.locator('#project-result').getByRole('button', { name: 'Localiser les haies à planter' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('button', { name: 'Tracer une haie à planter' }).click();
    await page.frameLocator('#hedge-input-iframe')
        .locator('#tooltip')
        .evaluate(el => el.style.display = 'none');
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').click({ position: { x: 400, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').click({ position: { x: 440, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').click({ position: { x: 440, y: 275 } });
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').dblclick({ position: { x: 400, y: 275 } });
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('dialog', { name: 'Description de la haie P1' }).getByText("Alignement d'arbres").check();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie P1').getByText('Bord de route, voie ou chemin').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie P1').getByText('Située sur une parcelle PAC').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie P1').getByRole('button', { name: 'Enregistrer' }).click();

    const condition = page.locator('#hedge-input-iframe').contentFrame().locator('div.condition-content', {
        hasText: 'Alignements d’arbres (L350-3)',
    });
    await expect(condition.locator('p.fr-badge--success.fr-badge')).toBeVisible();
    await expect(page.locator('#hedge-input-iframe').contentFrame().getByText('Plantation insuffisante')).toBeVisible();


    await page.locator('#hedge-input-iframe').contentFrame().getByRole('button', { name: 'Tracer une haie à planter' }).click();
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').click({ position: { x: 400, y: 215 } });
    await page.locator('#hedge-input-iframe').contentFrame().locator('#map').dblclick({ position: { x: 440, y: 275 } });
    await page.locator('#hedge-input-iframe').contentFrame().getByRole('dialog', { name: 'Description de la haie P2' }).getByText('Haie mixte').check();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie P2').getByText('Située sur une parcelle PAC').click();
    await page.locator('#hedge-input-iframe').contentFrame().getByLabel('Description de la haie P2').getByRole('button', { name: 'Enregistrer' }).click();
    await expect(page.locator('#hedge-input-iframe').contentFrame().getByText('Plantation adéquate')).toBeVisible();

    await page.locator('#hedge-input-iframe').contentFrame().locator('footer').getByRole('button', { name: 'Enregistrer', exact: true }).click();


    await expect(page.getByText('La demande d’autorisation est prête à être complétée')).toBeVisible();
    await expect(page.getByText('La plantation envisagée est adéquate')).toBeVisible();
    const buttons = page.getByText("Déposer une demande d'autorisation");
    await expect(buttons.nth(0)).toBeVisible();
    await expect(buttons.nth(1)).toBeVisible();

});
