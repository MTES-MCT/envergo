import { test, expect, Page } from '@playwright/test';

/**
 * Dynamic behaviour of the "Modifier l'état du dossier" modal
 * (static/js/libs/procedure_modal.js).
 *
 * Covers the client-side rules only — which fields show per (stage, decision),
 * the applicant-message template prefill, and the Démarches Simplifiées
 * state-change notice. The form is never submitted, so these tests are
 * idempotent and do not touch the DS API.
 *
 * Relies on the seeded dossier EGRAZY (e2e/fixtures/db_seed.json), open in
 * state "en construction" and editable by the superuser user@test.fr.
 */

async function loginAndOpenModal(page: Page) {
  await page.goto('/');
  await page.getByRole('link', { name: 'Espace instruction' }).click();
  await page.getByRole('textbox', { name: 'Email address' }).fill('user@test.fr');
  await page.getByRole('textbox', { name: 'Password' }).fill('Sésame');
  await page.getByRole('textbox', { name: 'Password' }).press('Enter');

  await page.goto('/projet/EGRAZY/instruction/procedure/');
  await page.getByRole('button', { name: "Modifier l'état du dossier" }).click();
}

test.describe('Procedure modal — dynamic form', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndOpenModal(page);
  });

  test('closing hides the date and internal comment fields', async ({ page }) => {
    const stage = page.locator('#id_stage');

    // While not closing, the date / comment fields are available.
    await stage.selectOption('preparing_decision');
    await expect(page.locator('#form-group-due_date')).toBeVisible();
    await expect(page.locator('#form-group-status_date')).toBeVisible();
    await expect(page.locator('#form-group-update_comment')).toBeVisible();

    // Closing is immediate: those fields disappear.
    await stage.selectOption('closed');
    await expect(page.locator('#form-group-due_date')).toBeHidden();
    await expect(page.locator('#form-group-status_date')).toBeHidden();
    await expect(page.locator('#form-group-update_comment')).toBeHidden();
  });

  test('closing fields follow the decision', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const decision = page.locator('#id_decision');
    const simulationCheck = page.locator('#form-group-simulation_check');
    const prefecturalOrder = page.locator('#form-group-prefectural_order');
    const applicantMessage = page.locator('#form-group-applicant_message');

    await stage.selectOption('closed');

    // "Classé sans suite": only the applicant message.
    await decision.selectOption('dropped');
    await expect(simulationCheck).toBeHidden();
    await expect(prefecturalOrder).toBeHidden();
    await expect(applicantMessage).toBeVisible();

    // "Accord tacite": simulation check + message, no order.
    await decision.selectOption('tacit_agreement');
    await expect(simulationCheck).toBeVisible();
    await expect(prefecturalOrder).toBeHidden();
    await expect(applicantMessage).toBeVisible();

    // The simulation check is a full content block, with a checklist and a
    // link to the simulations page opening in a new tab.
    await expect(simulationCheck.getByText('Avant de poursuivre')).toBeVisible();
    const simulationsLink = simulationCheck.getByRole('link', {
      name: 'Ouvrir la page des simulations',
    });
    await expect(simulationsLink).toHaveAttribute('target', '_blank');
    await expect(simulationsLink).toHaveAttribute('href', /\/alternatives\/$/);

    // "Accord exprès": all three.
    await decision.selectOption('express_agreement');
    await expect(simulationCheck).toBeVisible();
    await expect(prefecturalOrder).toBeVisible();
    await expect(applicantMessage).toBeVisible();

    // "Opposition": all three.
    await decision.selectOption('opposition');
    await expect(simulationCheck).toBeVisible();
    await expect(prefecturalOrder).toBeVisible();
    await expect(applicantMessage).toBeVisible();
  });

  test('applicant message is prefilled and swapped when the decision changes', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const decision = page.locator('#id_decision');
    const message = page.locator('#id_applicant_message');

    await stage.selectOption('closed');

    await decision.selectOption('express_agreement');
    await expect(message).toHaveValue(/accord exprès/i);

    // Picking another decision replaces the template.
    await decision.selectOption('opposition');
    await expect(message).toHaveValue(/opposition/i);

    await decision.selectOption('dropped');
    await expect(message).toHaveValue(/classé sans suite/i);
  });

  test('a message typed by the instructor survives a stage change', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const decision = page.locator('#id_decision');
    const message = page.locator('#id_applicant_message');
    const typed = 'Message personnalisé rédigé par l’instructeur.';

    await stage.selectOption('closed');
    await decision.selectOption('dropped');
    await message.fill(typed);

    // Leaving and re-entering the closing flow must not clobber the message.
    await stage.selectOption('preparing_decision');
    await stage.selectOption('closed');
    await expect(message).toHaveValue(typed);
  });

  test('a Démarches Simplifiées state change is announced', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const notice = page.locator('#procedure-state-change-message');

    // en_construction → en_instruction: the applicant loses edit rights.
    await stage.selectOption('instruction_d');
    await expect(notice).toBeVisible();
    await expect(notice).toContainText('Démarche Numérique');
    await expect(notice).toContainText('ne sera donc plus modifiable par le demandeur');
  });
});
