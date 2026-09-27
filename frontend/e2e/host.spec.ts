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

/**
 * S2's calibration, as the host actually meets it.
 *
 * The Django test asserts the same two values off the rendered HTML; this one
 * is here because the create form is the host's screen and because the pair is
 * the kind of thing that goes quietly wrong — the shipped default was 1000
 * people per Fahrgast against a 500 kg budget, which ended every game in round
 * one, and nothing went red over it for months.
 *
 * It does not create a game: that would leave a row on whatever database the
 * run points at. What a created game then does is the backend suite's job.
 */
test("the create form offers the calibrated pair", async ({ page }) => {
  await loginAsHost(page);

  const response = await page.goto("/game/create/");

  expect(response?.status()).toBe(200);
  await expect(page.locator('input[name="max_players"]')).toHaveValue("16");
  await expect(page.locator('input[name="max_rounds"]')).toHaveValue("6");
  await expect(page.locator('input[name="people_per_agent"]')).toHaveValue(
    "100",
  );
  await expect(page.locator('input[name="max_CO2_level"]')).toHaveValue(
    "48000",
  );
});
