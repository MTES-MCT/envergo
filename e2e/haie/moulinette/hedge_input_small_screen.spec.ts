import { test, expect, Page } from '@playwright/test';

// On small screens, the hedge input opens a modal warning that it is not suited
// to small devices. The modal must be opened once DSFR has started (otherwise
// dsfr(element) returns nothing) and once the Vue app is mounted (the mount
// rebuilds the page and would replace an opened modal by a closed one).

const HEDGE_INPUT_URL = '/haies/44/removal/';
const SMALL_SCREEN = { width: 375, height: 667 };
const LARGE_SCREEN = { width: 1280, height: 800 };
const DELAY_MS = 1500;

// Hold a static resource back to force a given loading order.
async function delayResource(page: Page, pattern: string) {
    await page.route(pattern, async (route) => {
        await new Promise((resolve) => setTimeout(resolve, DELAY_MS));
        await route.continue();
    });
}

// DSFR starts on the first animation frame following its script execution.
// Animation frames are not run while the page is not rendered (e.g. in an iframe
// that is not displayed yet), so the load event can be dispatched before DSFR
// has started. Running animation frame callbacks only after the load event
// reproduces this order.
async function holdAnimationFramesUntilLoad(page: Page) {
    await page.addInitScript(() => {
        const nativeRequestAnimationFrame = window.requestAnimationFrame.bind(window);
        const heldCallbacks: FrameRequestCallback[] = [];
        let isLoaded = false;

        window.requestAnimationFrame = (callback) => {
            if (isLoaded) {
                return nativeRequestAnimationFrame(callback);
            }
            heldCallbacks.push(callback);
            return 0;
        };

        window.addEventListener('load', () => {
            // Let the page's own load listeners run before releasing the frames
            setTimeout(() => {
                isLoaded = true;
                heldCallbacks.forEach((callback) => nativeRequestAnimationFrame(callback));
            }, 0);
        });
    });
}

function collectPageErrors(page: Page): Error[] {
    const errors: Error[] = [];
    page.on('pageerror', (error) => errors.push(error));
    return errors;
}

async function expectWarningOpenedOnceAppIsMounted(page: Page, errors: Error[]) {
    // The footer is rendered by the Vue app: once visible, the page is rebuilt
    await expect(page.locator('footer').getByRole('button', { name: 'Enregistrer', exact: true })).toBeVisible();
    await page.waitForLoadState('load');

    const warning = page.locator('#hedge-input-small-screen-warning');
    await expect(warning).toBeVisible();
    await expect(warning).toHaveClass(/fr-modal--opened/);
    expect(errors).toEqual([]);
}

test.describe('Hedge input small screen warning', () => {
    test.use({ viewport: SMALL_SCREEN });

    test('is opened on small screens', async ({ page }) => {
        const errors = collectPageErrors(page);
        await page.goto(HEDGE_INPUT_URL);
        await expectWarningOpenedOnceAppIsMounted(page, errors);
    });

    test('stays opened when the Vue app is mounted after DSFR has started', async ({ page }) => {
        const errors = collectPageErrors(page);
        await delayResource(page, '**/hedge_input/app.js');
        await page.goto(HEDGE_INPUT_URL);
        await expectWarningOpenedOnceAppIsMounted(page, errors);
    });

    test('is opened when DSFR starts after the page load event', async ({ page }) => {
        const errors = collectPageErrors(page);
        await holdAnimationFramesUntilLoad(page);
        await page.goto(HEDGE_INPUT_URL);
        await expectWarningOpenedOnceAppIsMounted(page, errors);
    });

    test('can be closed', async ({ page }) => {
        await page.goto(HEDGE_INPUT_URL);
        const warning = page.locator('#hedge-input-small-screen-warning');
        await expect(warning).toBeVisible();
        await warning.getByRole('button', { name: 'Fermer' }).click();
        await expect(warning).toBeHidden();
    });
});

test.describe('Hedge input on large screens', () => {
    test.use({ viewport: LARGE_SCREEN });

    test('does not open the small screen warning', async ({ page }) => {
        const errors = collectPageErrors(page);
        await page.goto(HEDGE_INPUT_URL);
        await expect(page.locator('footer').getByRole('button', { name: 'Enregistrer', exact: true })).toBeVisible();
        await page.waitForLoadState('load');

        await expect(page.locator('#hedge-input-small-screen-warning')).toBeHidden();
        expect(errors).toEqual([]);
    });
});
