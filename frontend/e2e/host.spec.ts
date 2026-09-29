import { expect, test } from "@playwright/test";

import { MAP_NAME } from "./game";
import { loginAsHost } from "./host";

/**
 * The host half of the two auth systems: a real `auth.User` with a Django
 * session, as opposed to the player's two signed cookies.
 *
 * This is the spec that fails first when the e2e account is missing, and it
 * keeps `loginAsHost` honest — every later spec builds on that helper, so a
 * silent change to the login form must break here rather than everywhere.
 */

test("the host signs in and lands on their own page", async ({ page }) => {
  await loginAsHost(page);

  // `LOGIN_REDIRECT_URL` defaults to `/accounts/profile/`, and since S13 that
  // is a redirect into the SPA — so signing in is a two-hop chain now, and
  // where it ends is worth pinning. `loginAsHost` waits for exactly this, so a
  // change here breaks one helper rather than every spec that uses it.
  expect(new URL(page.url()).pathname).toBe("/app/host");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

/**
 * S2's calibration and S13's derivation, as the host actually meets them.
 *
 * Two things at once, and they belong together: the pair is the calibrated one
 * (the shipped default was 1000 people per Gruppe against a 500 kg budget,
 * which ended every game in round one and nothing went red over it for months),
 * **and it follows the class size**. Changing the Platzzahl used to leave both
 * numbers where the page load had put them — H-13 — which is why this screen
 * was ported to React at all.
 *
 * It does not create a game: that would leave a row on whatever database the
 * run points at. What a created game then does is the backend suite's job.
 */
test("the create form offers the calibrated pair, and it follows the class size", async ({
  page,
}) => {
  await loginAsHost(page);

  const response = await page.goto("/game/create/");

  // The old URL is a doorway now. Status first — a content check alone goes
  // green against a 404, which has no German on it either.
  expect(response?.status()).toBe(200);
  await page.waitForURL(/\/app\/game\/create\/?$/);

  await page.locator("#game_map").selectOption({ label: MAP_NAME });
  await expect(page.locator("#max_players")).toHaveValue("16");
  await expect(page.locator("#max_rounds")).toHaveValue("6");
  await expect(page.locator("#people_per_agent")).toHaveValue("100");
  await expect(page.locator("#max_CO2_level")).toHaveValue("48000");

  // Half the class, twice the people behind each Gruppe — the district's
  // commuter population is what stays put, not the scale.
  await page.locator("#max_players").fill("8");
  await expect(page.locator("#people_per_agent")).toHaveValue("200");

  // The budget is per round and carries no Gruppe term, so it did not move.
  await expect(page.locator("#max_CO2_level")).toHaveValue("48000");
  await page.locator("#max_rounds").fill("3");
  await expect(page.locator("#max_CO2_level")).toHaveValue("24000");
});

/**
 * The offer is an offer. A host who types their own number keeps it, and the
 * screen says so rather than silently putting the suggestion back the next time
 * anything else changes.
 */
test("a host can type over a derived number and keep it", async ({ page }) => {
  await loginAsHost(page);
  await page.goto("/game/create/");
  await page.waitForURL(/\/app\/game\/create\/?$/);
  await page.locator("#game_map").selectOption({ label: MAP_NAME });

  await page.locator("#people_per_agent").fill("500");
  await page.locator("#max_players").fill("8");
  await expect(page.locator("#people_per_agent")).toHaveValue("500");

  await page.getByRole("button", { name: "Vorschlag übernehmen" }).click();
  await expect(page.locator("#people_per_agent")).toHaveValue("200");
});
