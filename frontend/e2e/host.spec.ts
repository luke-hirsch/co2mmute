import { expect, test } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * The host half of the two auth systems: a real `auth.User` with a Django
 * session, as opposed to the player's two signed cookies.
 *
 * This is the spec that fails first when the e2e account is missing, and it
 * keeps `loginAsHost` honest — every later spec builds on that helper, so a
 * silent change to the login form must break here rather than everywhere.
 */

test("the host signs in and reaches the profile", async ({ page }) => {
  await loginAsHost(page);

  const response = await page.goto("/accounts/profile/");

  // Status first: the page's content proves nothing against the redirect an
  // unauthenticated request would get instead.
  expect(response?.status()).toBe(200);
  expect(new URL(page.url()).pathname).toBe("/accounts/profile/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});
