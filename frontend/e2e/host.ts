import type { Page } from "@playwright/test";

/**
 * Signing in as the host, which every spec that touches a host screen needs.
 *
 * The account is the one `e2e/seed.mjs` expects — a staff user, because
 * uploading a map needs `is_staff`. Create it with the command seed.mjs prints
 * if the login fails.
 *
 * Deliberately done through the real form rather than by injecting a session
 * cookie: the login page is part of the funnel, and Django refuses a
 * CSRF-protected POST over HTTPS without a matching Referer anyway, which a
 * hand-built request gets wrong exactly once per person.
 */

export const HOST_USER = process.env.E2E_USER ?? "e2e";
export const HOST_PASSWORD = process.env.E2E_PASSWORD ?? "e2e-local-only";

export async function loginAsHost(page: Page): Promise<void> {
  await page.goto("/accounts/login/");
  await page.locator('input[name="username"]').fill(HOST_USER);
  await page.locator('input[name="password"]').fill(HOST_PASSWORD);
  await Promise.all([
    // Wait for where a host actually ends up, not for "off the login page".
    // Until S22 that was a two-hop chain — `LOGIN_REDIRECT_URL` defaulted to
    // `/accounts/profile/`, itself a redirect into the SPA — and "not on
    // /accounts/login any more" was true while the browser was still moving,
    // so the next `page.goto` collided with it ("interrupted by another
    // navigation"). It is one hop now; waiting for the destination still says
    // what that place is.
    page.waitForURL(/\/app\/host\/?$/),
    page.locator('form button[type="submit"], form input[type="submit"]').click(),
  ]);
  // And then for the screen to be there. `waitForURL` resolves when the URL
  // changes, which for the last hop of a redirect chain is before the document
  // has finished loading — a `page.goto` issued at that moment is cancelled by
  // the load still in flight, which Playwright reports as "interrupted by
  // another navigation" from inside whatever the spec did next.
  await page.getByRole("heading", { level: 1 }).waitFor();
}
