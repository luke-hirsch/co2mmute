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
    page.waitForURL((url) => !url.pathname.startsWith("/accounts/login")),
    page.locator('form button[type="submit"], form input[type="submit"]').click(),
  ]);
}
