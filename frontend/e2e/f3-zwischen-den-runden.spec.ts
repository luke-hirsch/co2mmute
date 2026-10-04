import { expect, test, type Page } from "@playwright/test";

import { createGame, joinAsPlayer, pickMode } from "./game";
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
  // A real jam, not a busy street: the map only draws a street that lost more
  // than 5 % of its speed, and a hundred cars sometimes slow none that much — so
  // the hint was there or not by where the seat happened to live.
  const gameId = await createGame(page, {
    name: "E2E Stau in der Wahl",
    maxRounds: 3,
    peoplePerAgent: 2000,
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

    // The vote closes without Ben, and round 2 waits for Ana alone. Not "ist
    // angenommen": that line lives only in the client's state, and once in a
    // full run under load it was missing although the round had moved on — a
    // socket that reconnects across `vote.result` gets a snapshot without it.
    await expect(ana.getByRole("heading", { name: "Runde 2 von 3" })).toBeVisible({
      timeout: 60_000,
    });
    await expect(ana.getByText("0 von 1 abgeschickt")).toBeVisible();
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});

test("a seat taken over after the desk has read the stats gets its own Weiter", async ({
  browser,
  page,
}) => {
  test.setTimeout(420_000);
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Übernahme nach Weiter",
    maxPlayers: 2,
    maxRounds: 3,
    peoplePerAgent: 100,
  });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1200, height: 900 },
  });
  const ana = await context.newPage();

  try {
    // Ben at the desk, Ana on her phone.
    await page.getByRole("button", { name: "Platz anlegen" }).click();
    await page.getByLabel("Name").fill("Ben");
    await page.getByRole("button", { name: "Anlegen", exact: true }).click();
    await expect(page.getByText("Ben", { exact: true }).first()).toBeVisible();
    await joinAsPlayer(ana, gameId, "Ana");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    await page.getByRole("button", { name: "Nächster Platz" }).click({ timeout: 60_000 });
    await page.getByRole("button", { name: "Los", exact: true }).click();
    await pickMode(page, 0, "Auto");
    await page.getByRole("button", { name: "Losfahren" }).click();
    await driveByCar(ana);

    // The desk reads for Ben. Ana's phone never does.
    await expect(page.getByText("Runde 1 ist gefahren")).toBeVisible({
      timeout: 300_000,
    });
    await page.getByRole("button", { name: "Überspringen" }).click();
    await page.getByRole("button", { name: "Weiter für alle hier" }).click();
    await expect(page.getByText("Für die Plätze hier ist gelesen.")).toBeVisible();

    // Ana's phone has gone quiet, so the desk takes her seat over.
    await page.getByText("Plätze anzeigen").click();
    const seats = page.locator("details").filter({ hasText: "Plätze anzeigen" });
    await seats
      .locator("li")
      .filter({ hasText: "Ana" })
      .getByRole("button", { name: "Übernehmen" })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Übernehmen" })
      .click();

    // Her seat is at the desk now and has read nothing — the earlier press was
    // for Ben alone. Until 2026-10-04 the desk kept saying it had read, and the
    // phase waited for an ack nobody could send short of a reload.
    await page
      .getByRole("button", { name: "Weiter für alle hier" })
      .click({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: "Abstimmung öffnen" }),
    ).toBeVisible({ timeout: 60_000 });
  } finally {
    await context.close();
  }
});
