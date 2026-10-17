import { expect, test, type Page } from "@playwright/test";

import { createGame, endAndDelete, joinAsPlayer, pickMode } from "./game";
import { loginAsHost } from "./host";

/**
 * A game made with its CO₂ hidden: no kilogram and no budget on any screen —
 * the phone, the Leitstelle — until the summary, which then shows both and says
 * the budget is not what ended it.
 *
 * Set `E2E_SHOTS` to a folder and every screen is also saved there, at the
 * phone's width for the player.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(600_000);

/** What a hidden game never shows before the end. */
const CO2 = /kg|CO₂/;

const shots = process.env.E2E_SHOTS;

async function shot(page: Page, name: string) {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}

async function noCo2(page: Page) {
  await expect(page.locator("body")).not.toContainText(CO2);
}

test("a hidden game shows no CO₂ until the summary", async ({
  browser,
  page,
  baseURL,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E verdeckt",
    maxRounds: 2,
    peoplePerAgent: 800,
    hideCo2: true,
  });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 375, height: 812 },
  });
  const player = await context.newPage();
  const errors: string[] = [];
  player.on("pageerror", (error) => errors.push(error.message));

  try {
    await joinAsPlayer(player, gameId, "Ana");
    await noCo2(page);
    await shot(page, "leitstelle-lobby");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    // ── round 1 ──
    await expect(player.getByRole("heading", { name: "Runde 1 von 2" })).toBeVisible({
      timeout: 60_000,
    });
    await pickMode(player, 0, "Auto");
    await noCo2(player);
    await shot(player, "spieler-runde");
    await shot(page, "leitstelle-runde");
    await noCo2(page);
    await player.getByRole("button", { name: "Losfahren" }).click();

    await expect(player.getByText(/ist gefahren/)).toBeVisible({ timeout: 300_000 });
    await player.getByRole("button", { name: "Überspringen" }).click().catch(() => {});
    await expect(player.getByText("Runde gesamt")).toBeVisible();
    await noCo2(player);
    await shot(player, "spieler-tabelle");
    await shot(page, "leitstelle-tabelle");
    await noCo2(page);

    await player.getByRole("button", { name: "Die Simulation erklärt" }).click();
    await expect(player.getByRole("dialog")).toBeVisible();
    await expect(player.getByRole("dialog")).not.toContainText(CO2);
    await shot(player, "spieler-erklaerung");
    await player.keyboard.press("Escape");

    await player.getByRole("button", { name: "Weiter", exact: true }).click();
    await page.getByRole("button", { name: "Abstimmung öffnen" }).click({
      timeout: 60_000,
    });
    await player.getByRole("button", { name: /So lassen/ }).click({ timeout: 60_000 });

    // ── round 2, which ends the game on the round limit ──
    await expect(player.getByRole("heading", { name: "Runde 2 von 2" })).toBeVisible({
      timeout: 60_000,
    });
    await noCo2(player);
    await pickMode(player, 0, "Auto");
    await player.getByRole("button", { name: "Losfahren" }).click();

    await expect(player.getByRole("heading", { name: "Spiel zu Ende" })).toBeVisible({
      timeout: 300_000,
    });
    // Only now: the figures, and the budget as the plain number it always was.
    await expect(player.locator("body")).toContainText(/kg/);
    await shot(player, "spieler-auswertung");
    await shot(page, "leitstelle-auswertung");

    expect(errors).toEqual([]);
  } finally {
    await context.close();
    await endAndDelete(page, gameId, baseURL!);
  }
});
