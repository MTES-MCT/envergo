import { test, expect } from '@playwright/test';

test('User can request an evaluation', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Menu principal').getByRole('link', { name: 'Demander un avis réglementaire' }).click();
  await page.locator('p').filter({ hasText: 'Commencer la demande Durée : 1 min' }).getByRole('link').first().click();
  await page.getByLabel('Address of the project').click();
  await page.getByLabel('Address of the project').fill('44640 Vue');
  await page.getByPlaceholder('PC0123456789012').click();
  await page.getByPlaceholder('PC0123456789012').fill('PA1234567981011');
  await page.getByLabel('Project description, comments').click();
  await page.getByLabel('Project description, comments').fill('Assainissement de marécage pour faire une belle dalle béton bien propre');
  await page.getByRole('button', { name: 'Poursuivre votre demande d\'' }).click();
  await page.getByLabel('Adresse(s) e-mail', { exact: true }).click();
  await page.getByLabel('Adresse(s) e-mail', { exact: true }).fill('test@test.fr');
  await page.getByLabel('Adresse(s) e-mail', { exact: true }).press('Tab');
  await page.getByLabel('Urbanism department phone').fill('0601900917');
  await page.getByLabel('Urbanism department phone').press('Tab');
  await page.getByLabel('Urbanism department phone').click();
  await page.getByLabel('Urbanism department phone').fill('0601900918');
  await page.getByLabel('Adresse(s) e-mail Pé').click();
  await page.getByLabel('Adresse(s) e-mail Pé').fill('test@porteur.fr');
  await page.getByRole('button', { name: 'Poursuivre votre demande d\'' }).click();
  await page.getByRole('button', { name: 'Envoyer votre demande d\'avis' }).click();
  await expect(page).toHaveTitle("Votre demande d'avis réglementaire a été enregistrée — Envergo");
  await expect(page.getByText('Nous avons bien reçu votre demande d\'avis réglementaire.')).toBeVisible();

});
