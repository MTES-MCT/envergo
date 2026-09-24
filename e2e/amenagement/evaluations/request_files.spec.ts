import { test, expect } from '@playwright/test';

/**
 * Covers the dropzone on step 3 of the "demande d'avis" wizard.
 *
 * Dropzone removes the `.fallback` input from the dom and uploads through
 * its own `input.dz-hidden-input`, so that is what the test drives.
 */

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64'
);

/**
 * Walk the wizard up to step 3, where the dropzone lives.
 *
 * Mirrors `request.spec.ts` step for step, including the `Tab` presses: they
 * blur each field so client side validation runs *before* the submit click.
 * Without them the validation messages appear on click, the button shifts, and
 * playwright never sees a stable element to click.
 */
async function gotoStep3(page) {
  await page.goto('/');
  await page.getByLabel('Menu principal').getByRole('link', { name: 'Demander un avis réglementaire' }).click();
  await page.locator('p').filter({ hasText: 'Commencer la demande Durée : 1 min' }).getByRole('link').first().click();

  await page.getByLabel('Address of the project').click();
  await page.getByLabel('Address of the project').fill('44640 Vue');
  await page.getByPlaceholder('PC0123456789012').click();
  await page.getByPlaceholder('PC0123456789012').fill('PA1234567981011');
  await page.getByLabel('Project description, comments').click();
  await page.getByLabel('Project description, comments').fill('Test upload de fichiers');
  await page.getByRole('button', { name: 'Poursuivre votre demande d\'' }).click();

  await page.getByLabel('Adresse(s) e-mail', { exact: true }).click();
  await page.getByLabel('Adresse(s) e-mail', { exact: true }).fill('test@test.fr');
  await page.getByLabel('Adresse(s) e-mail', { exact: true }).press('Tab');
  await page.getByLabel('Urbanism department phone').fill('0601900917');
  await page.getByLabel('Urbanism department phone').press('Tab');
  await page.getByLabel('Adresse(s) e-mail Pé').click();
  await page.getByLabel('Adresse(s) e-mail Pé').fill('test@porteur.fr');
  await page.getByLabel('Adresse(s) e-mail Pé').press('Tab');
  await page.getByRole('button', { name: 'Poursuivre votre demande d\'' }).click();

  await page.waitForURL(/etape-3/);
  // The dropzone replaces the fallback input once it has initialised
  await expect(page.locator('input.dz-hidden-input')).toBeAttached();
}

test('User can upload a file on step 3', async ({ page }) => {
  await gotoStep3(page);

  const upload = page.waitForResponse(
    (res) => res.url().includes('/fichiers/') && res.request().method() === 'POST'
  );
  await page.locator('input.dz-hidden-input').setInputFiles({
    name: 'plan-du-projet.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  const response = await upload;

  expect(response.status()).toBe(200);
  await expect(page.locator('.dz-preview')).toHaveCount(1);
  await expect(page.locator('.dz-preview .dz-filename')).toContainText('plan-du-projet.png');
  await expect(page.locator('.dz-preview.dz-error')).toHaveCount(0);
  await expect(page.locator('form#request-evaluation-form')).not.toHaveClass(/has-errors/);
});

test('User can remove an uploaded file', async ({ page }) => {
  await gotoStep3(page);

  const upload = page.waitForResponse(
    (res) => res.url().includes('/fichiers/') && res.request().method() === 'POST'
  );
  await page.locator('input.dz-hidden-input').setInputFiles({
    name: 'a-supprimer.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  await upload;
  await expect(page.locator('.dz-preview')).toHaveCount(1);

  // The delete url must carry file_id alongside the existing ?clef= param
  const deletion = page.waitForResponse(
    (res) => res.request().method() === 'DELETE' && res.url().includes('file_id=')
  );
  await page.getByRole('link', { name: 'Supprimer' }).click();
  const response = await deletion;

  expect(response.status()).toBe(200);
  expect(response.url()).toContain('clef=');
  await expect(page.locator('.dz-preview')).toHaveCount(0);
});

test('Submit button is locked while uploading, then released', async ({ page }) => {
  await gotoStep3(page);

  // Locate the button by its position in the form, not by its accessible name:
  // the lock rewrites the label, so a name based locator would stop matching
  // precisely when the assertion matters.
  const submitBtn = page.locator('#request-evaluation-form button[type=submit]');
  await expect(submitBtn).toBeEnabled();

  // Hold the upload open until we release it, so the locked state is
  // observable. On a local stack the request would otherwise complete before
  // any assertion could run.
  let releaseUpload;
  const uploadHeld = new Promise((resolve) => { releaseUpload = resolve; });
  let intercepted = false;

  await page.route(
    (url) => url.pathname.endsWith('/fichiers/'),
    async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      intercepted = true;
      await uploadHeld;
      await route.continue();
    }
  );

  await page.locator('input.dz-hidden-input').setInputFiles({
    name: 'plan.png',
    mimeType: 'image/png',
    buffer: PNG,
  });

  // Fails here => the route never matched, so nothing below can be trusted
  await expect.poll(() => intercepted, { timeout: 10000 }).toBe(true);

  // Fails here => the submit lock is genuinely not wired up
  await expect(submitBtn).toBeDisabled();

  releaseUpload();

  await expect(submitBtn).toBeEnabled();
  await expect(page.locator('.dz-preview')).toHaveCount(1);

  await page.unroute((url) => url.pathname.endsWith('/fichiers/'));
  await submitBtn.click();
  await expect(page).toHaveTitle("Votre demande d'avis réglementaire a été enregistrée — Envergo");
});
