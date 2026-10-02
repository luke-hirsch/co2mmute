import { expect, test, type Page } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * Between two rounds (F3): the map the class talks and votes over carries the
 * round it has just played, on the phone and on the projector; the projector
 * says how to vote; and a seat that has gone can be removed while the class
 * votes, as the screen has always told the host to.
 */

test.use({ actionTimeout: 20_000 });

/** The line under a map that draws last round's traffic, and only then. */
const JAM_HINT = /desto langsamer war sie in der letzten Runde/;

/** Send one Gruppe off by car. */
async function driveByCar(player: Page) {
  const row = player.locator("li").filter({ hasText: "Gruppe 1" });
  await row.getByRole("radio", { name: "Auto", exact: true }).click();
  await expect(row.getByText("ändern")).toBeVisible({ timeout: 60_000 });
  await player.getByRole("button", { name: "Losfahren" }).click();
}

/** Read the round's stats to the end and say so. */
async function finishStats(player: Page) {
  await expect(player.getByText(/ist gefahren/)).toBeVisible({ timeout: 300_000 });
  await player.getByRole("button", { name: "Überspringen" }).click().catch(() => {});
  await player.getByRole("button", { name: "Weiter", exact: true }).click();
}

/** Play one car round as the only seat, up to the discussion. */
async function playOneRound(host: Page, player: Page) {
  await driveByCar(player);
  await finishStats(player);
  await expect(
    host.getByRole("button", { name: "Abstimmung öffnen" }),
  ).toBeVisible({ timeout: 60_000 });
}

test("the discussion and the vote show the round that was just played", async ({
  browser,
  page,
}) => {
  test.setTimeout(420_000);
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Stau in der Wahl",
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
    await playOneRound(page, player);

    // The discussion has the map too, with the jams on it, on both screens.
    const playerMap = player.getByRole("region", { name: "Karte der letzten Runde" });
    const hostMap = page.getByRole("region", { name: "Karte der letzten Runde" });
    await expect(playerMap.getByText(JAM_HINT)).toBeVisible({ timeout: 15_000 });
    await expect(hostMap.getByText(JAM_HINT)).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Abstimmung öffnen" }).click();
    // The projector says how to vote, not how the desk takes turns: nobody
    // plays at this one.
    await expect(page.getByText(/Tippe oder klicke auf deine Wahl/)).toBeVisible();
    await expect(page.getByText(/Gib den Rechner reihum weiter/)).toHaveCount(0);

    await expect(
      player.getByRole("button", { name: /Dafür stimmen/ }).first(),
    ).toBeVisible({ timeout: 60_000 });

    await expect(playerMap.getByText(JAM_HINT)).toBeVisible({ timeout: 15_000 });
    await expect(hostMap.getByText(JAM_HINT)).toBeVisible({ timeout: 15_000 });

    // And the next round routes on the same picture.
    await player.getByRole("button", { name: /So lassen/ }).click();
    await expect(player.getByRole("button", { name: "Losfahren" })).toBeVisible({
      timeout: 60_000,
    });
    await expect(player.getByText(JAM_HINT)).toBeVisible({ timeout: 15_000 });

    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});

test("a seat that has gone can be removed during the vote, and the vote closes without it", async ({
  browser,
  page,
}) => {
  test.setTimeout(480_000);
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Platz weg in der Wahl",
    maxPlayers: 2,
    maxRounds: 3,
    peoplePerAgent: 100,
  });

  const contexts = await Promise.all(
    [0, 1].map(() =>
      browser.newContext({
        ignoreHTTPSErrors: true,
        viewport: { width: 1200, height: 900 },
      }),
    ),
  );
  const [ana, ben] = await Promise.all(contexts.map((c) => c.newPage()));

  try {
    await joinAsPlayer(ana, gameId, "Ana");
    await joinAsPlayer(ben, gameId, "Ben");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    await driveByCar(ana);
    await driveByCar(ben);
    await finishStats(ana);
    await finishStats(ben);

    await page.getByRole("button", { name: "Abstimmung öffnen" }).click({
      timeout: 60_000,
    });
    await ana.getByRole("button", { name: /Dafür stimmen/ }).first().click({
      timeout: 60_000,
    });
    await expect(page.getByText("1 von 2 haben abgestimmt")).toBeVisible({
      timeout: 15_000,
    });

    // Ben has gone home. The projector has the list, behind its disclosure.
    await page.getByText("Plätze anzeigen").click();
    const benRow = page.locator("li").filter({ hasText: "Ben" });
    await benRow.getByRole("button", { name: "Entfernen" }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Entfernen" })
      .click();

    // The vote closes on Ana's ballot and the next round carries it.
    await expect(ana.getByText(/ist angenommen\./)).toBeVisible({ timeout: 60_000 });
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});
