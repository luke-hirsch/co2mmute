import { expect, test } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * The rest of S24: the seat limit warns before the field, and the router's
 * search is drawn when a route appears.
 *
 * Voting by keyboard needs a round simulated first and is held by the unit
 * tests of `vote-keys` and by the click-through; the pieces below need only a
 * lobby and a started game.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(120_000);

test("a full game says so before it asks for a name", async ({ page }) => {
  await loginAsHost(page);
  await createGame(page, { name: "E2E Platzgrenze", maxPlayers: 1 });

  // Room left: the mask is there.
  await page.getByRole("button", { name: "Platz anlegen" }).click();
  await expect(page.getByLabel("Name")).toBeVisible();
  await page.getByLabel("Name").fill("Ana");
  await page.getByRole("button", { name: "Anlegen", exact: true }).click();
  await expect(page.getByText("Ana", { exact: true }).first()).toBeVisible();

  // The only seat is taken: the dialog gives the refusal and no field to type in.
  await page.getByRole("button", { name: "Platz anlegen" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Alle Plätze sind belegt")).toBeVisible();
  await expect(dialog.getByLabel("Name")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: "Anlegen" })).toHaveCount(0);
});

test("the search the router made is drawn, then gone, and the route stays", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Suche" });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1000, height: 900 },
  });
  const player = await context.newPage();
  const errors: string[] = [];
  player.on("pageerror", (error) => errors.push(error.message));

  try {
    await joinAsPlayer(player, gameId, "Ana");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    const map = player.getByRole("region", { name: "Karte" });
    await expect(map).toBeVisible({ timeout: 30_000 });

    // Everything the search layer draws is in the accent, and nothing else on
    // the map is.
    const search = map.locator('g[stroke="var(--color-brandaccent)"]');
    const row = player.locator("li").filter({ hasText: "Gruppe 1" });
    await row.getByRole("radio", { name: "Auto", exact: true }).click();

    await expect(search.locator("line").first()).toBeAttached({ timeout: 10_000 });
    await expect(row.getByText("ändern")).toBeVisible({ timeout: 60_000 });
    await expect(search).toHaveCount(0, { timeout: 10_000 });

    // The route is still there once the search has let go.
    await expect(map.locator("line[stroke-width]").first()).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});

test("the vote can be cast from the keyboard, and the keys are printed", async ({
  browser,
  page,
}) => {
  test.setTimeout(420_000);
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Tasten",
    maxRounds: 3,
    peoplePerAgent: 100,
  });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1200, height: 900 },
  });
  const player = await context.newPage();
  const errors: string[] = [];
  player.on("pageerror", (error) => errors.push(error.message));

  try {
    await joinAsPlayer(player, gameId, "Ana");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    const row = player.locator("li").filter({ hasText: "Gruppe 1" });
    await row.getByRole("radio", { name: "Auto", exact: true }).click();
    await expect(row.getByText("ändern")).toBeVisible({ timeout: 60_000 });
    await player.getByRole("button", { name: "Losfahren" }).click();

    // Stats: one "Weiter" for a single player.
    await expect(player.getByText(/ist gefahren/)).toBeVisible({ timeout: 300_000 });
    await player.getByRole("button", { name: "Überspringen" }).click().catch(() => {});
    await player.getByRole("button", { name: "Weiter", exact: true }).click();
    // The discussion is the host's to close.
    await page.getByRole("button", { name: "Abstimmung öffnen" }).click();

    // The ballot: two options on the seeded map, so the keys are 1, 2 and 0.
    const pick = player.getByRole("button", { name: /Dafür stimmen/ });
    await expect(pick.first()).toBeVisible({ timeout: 60_000 });
    await expect(pick.first()).toContainText("1");
    await expect(pick.nth(1)).toContainText("2");
    await expect(player.getByRole("button", { name: /So lassen/ })).toContainText("0");

    // A digit typed into the chat is a message, not a vote.
    // (The dock is closed by default; the unit tests hold the field rule.)
    await player.keyboard.press("1");
    // The result, not "Deine Stimme ist da.": with one seat the vote closes at
    // once and round 2 replaces that line almost before it is drawn, so
    // waiting for it failed under load.
    await expect(player.getByText(/ist angenommen\./)).toBeVisible({
      timeout: 60_000,
    });
    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});
