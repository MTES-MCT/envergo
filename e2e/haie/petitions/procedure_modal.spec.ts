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
    await expect(page.locator('#form-group-refusal_deadline')).toBeHidden();

    // Closing is immediate: those fields disappear.
    await stage.selectOption('closed');
    await expect(page.locator('#form-group-due_date')).toBeHidden();
    await expect(page.locator('#form-group-refusal_deadline')).toBeHidden();
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

  test('switching to authorization asks for the refusal deadline and prefills the message', async ({ page }) => {
    const refusalDeadline = page.locator('#id_refusal_deadline');
    const message = page.locator('#id_applicant_message');
    const hint = page.locator('#form-group-applicant_message .fr-hint-text');

    await page.locator('#id_stage').selectOption('instruction_a');

    await expect(refusalDeadline).toBeVisible();
    await expect(refusalDeadline).toHaveValue('');
    await expect(page.locator('#form-group-refusal_deadline > label')).toContainText(
      'Date limite au-delà de laquelle le silence vaut refus'
    );
    // The server sets the stage due date from the refusal deadline.
    await expect(page.locator('#form-group-due_date')).toBeHidden();
    await expect(message).toBeVisible();
    await expect(message).toHaveValue(/Requalification de votre projet/);
    await expect(message).toHaveValue(/\[DATE LIMITE – NE PAS MODIFIER/);
    await expect(hint).toContainText('automatiquement insérée');

    // The message follows the deadline it states, and comes before the decision.
    await expect(page.locator('#form-group-refusal_deadline + *')).toHaveId('form-group-applicant_message');
    await expect(page.locator('#form-group-applicant_message + *')).toHaveId('form-group-decision');
  });

  test('closing and switching each bring their own message and hint', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const message = page.locator('#id_applicant_message');
    const hint = page.locator('#form-group-applicant_message .fr-hint-text');

    await stage.selectOption('closed');
    await page.locator('#id_decision').selectOption('dropped');
    await expect(message).toHaveValue(/classé sans suite/i);

    await stage.selectOption('instruction_a');
    await expect(message).toHaveValue(/Requalification de votre projet/);
    await expect(hint).toContainText('automatiquement insérée');

    await stage.selectOption('closed');
    await expect(message).toHaveValue(/classé sans suite/i);
    await expect(hint).toContainText('Précisez les motifs de la décision');
  });

  test('a switch message edited by the instructor survives a stage change', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const message = page.locator('#id_applicant_message');
    const typed = 'Motif de la bascule rédigé par l’instructeur.';

    await stage.selectOption('instruction_a');
    await message.fill(typed);

    // Leaving the switch restores the stage due date and the server order.
    await stage.selectOption('preparing_decision');
    await expect(page.locator('#form-group-due_date')).toBeVisible();
    await expect(page.locator('#form-group-refusal_deadline')).toBeHidden();
    await expect(page.locator('#form-group-due_date + *')).toHaveId('form-group-refusal_deadline');
    await expect(page.locator('#form-group-refusal_deadline + *')).toHaveId('form-group-decision');
    await expect(page.locator('#form-group-applicant_message + button[type="submit"]')).toHaveCount(1);

    await stage.selectOption('instruction_a');
    await expect(message).toHaveValue(typed);
  });

  test('a switch message survives a detour through closing', async ({ page }) => {
    const stage = page.locator('#id_stage');
    const message = page.locator('#id_applicant_message');
    const typed = 'Motif de la bascule rédigé par l’instructeur.';

    await stage.selectOption('instruction_a');
    await message.fill(typed);

    // The closing template takes over, then the switch draft comes back.
    await stage.selectOption('closed');
    await page.locator('#id_decision').selectOption('dropped');
    await expect(message).toHaveValue(/classé sans suite/i);

    await stage.selectOption('instruction_a');
    await expect(message).toHaveValue(typed);
  });
});
