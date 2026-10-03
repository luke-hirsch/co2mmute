import { expect, test, type Page } from "@playwright/test";

import { createGame, endAndDelete, pickMode } from "./game";
import { loginAsHost } from "./host";

/**
 * A whole game at the Leitstelle (F15): one machine, two seats, two rounds.
 *
 * The classroom without phones. The host makes the game, adds two seats played
 * at this machine, and the keyboard goes round: each turn behind the curtain,
 * round 1 through Celery, the stats read once for every seat here, the
 * discussion closed by the host, the vote seat by seat by keyboard, round 2 on
 * the version that won, and the summary when the last round has run.
 *
 * Every other spec stops somewhere along that line — `replay` and `numbers` after
 * one round, `f3-zwischen-den-runden` with a phone at the vote — so this is the
 * only one that runs the round loop through Celery twice and reaches the end of
 * a game by the rule rather than by the host's button.
 *
 * **The winner is checked where it is recorded, not where it flashes by.** The
 * round header's "„…“ ist angenommen." lives only in the client's state, and a
 * socket reconnecting across `vote.result` misses it — the one known flake in
 * this suite. What the class voted for is asserted through the game's
 * `active_map_version` and the summary's vote list, which the server writes
 * once, at the moment it happens.
 */

test.use({ actionTimeout: 20_000 });

/** Two rounds, each simulated on a Celery worker, both ways. */
test.setTimeout(900_000);

const SEATS = ["Ana", "Ben"];

/** One Gruppe each, a different mode per seat, swapped for round 2. */
const MODES: Record<number, string[]> = {
  1: ["Auto", "Bus & Bahn"],
  2: ["Bus & Bahn", "Auto"],
};

/** The game as the API has it — the host's own session reads it. */
async function readGame(page: Page, gameId: string) {
  const response = await page.request.get(`/api/game/${gameId}/`);
  expect(response.ok()).toBe(true);
  return (await response.json()) as {
    active_map_version: number | null;
    is_active: boolean;
  };
}

/**
 * Why the game ended, from the host's own list (`GET api/game/`) — the detail
 * endpoint does not carry `end_reason`, the list the host page reads does.
 */
async function readEnding(page: Page, gameId: string) {
  const response = await page.request.get("/api/game/");
  expect(response.ok()).toBe(true);
  const games = (await response.json()) as {
    game_id: string;
    end_reason: string | null;
    round_count: number;
  }[];
  const game = games.find((row) => row.game_id === gameId);
  expect(game).toBeTruthy();
  return game!;
}

/**
 * Play every seat at the desk once, through the curtain.
 *
 * The curtain is the point (H-04): the machine is on a projector, so between two
 * seats nothing of the turn may be on screen — no map, no submit. A seat that
 * submits drops back to the desk by itself, and "Nächster Platz" opens the next.
 */
async function playTheDesk(page: Page, round: number) {
  await expect(
    page.getByRole("heading", { name: `Runde ${round} von 2` }),
  ).toBeVisible({ timeout: 60_000 });

  for (const [seat, name] of SEATS.entries()) {
    await page.getByRole("button", { name: "Nächster Platz" }).click();

    await expect(page.getByRole("heading", { name: `${name} ist dran` })).toBeVisible();
    await expect(page.getByRole("button", { name: "Losfahren" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Karte" })).toHaveCount(0);
    await page.getByRole("button", { name: "Los", exact: true }).click();

    await pickMode(page, 0, MODES[round][seat]);
    const submit = page.getByRole("button", { name: "Losfahren" });
    await expect(submit).toBeEnabled();
    await submit.click();
  }
}

test("a whole game at the Leitstelle: two seats, two rounds, a vote by keyboard, the summary", async ({
  page,
  baseURL,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Leitstelle",
    maxPlayers: 2,
    agentPerPlayer: 1,
    maxRounds: 2,
    // Below what the screen derives (3200 here): a lighter round, so two of
    // them fit an e2e run, and still enough traffic for the numbers to be real.
    peoplePerAgent: 800,
  });

  try {
    // ── the lobby: two seats at this machine ──
    for (const name of SEATS) {
      await page.getByRole("button", { name: "Platz anlegen" }).click();
      await page.getByLabel("Name").fill(name);
      await page.getByRole("button", { name: "Anlegen", exact: true }).click();
      await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
    }

    await page.getByRole("button", { name: "Spiel starten" }).click();

    // ── round 1 ──
    await expect(page.getByRole("heading", { name: "Runde 1 von 2" })).toBeVisible({
      timeout: 60_000,
    });
    // Starting is what puts the game on its map's base version.
    const base = (await readGame(page, gameId)).active_map_version;
    expect(base).not.toBeNull();

    await playTheDesk(page, 1);

    // The first Celery round. The stats are the class's, on the projector.
    await expect(page.getByText("Runde 1 ist gefahren")).toBeVisible({
      timeout: 300_000,
    });
    await page.getByRole("button", { name: "Überspringen" }).click();
    await expect(page.getByText("Runde gesamt")).toBeVisible();
    // One "Weiter" for every seat here: there is nothing per seat about having
    // read a table (`phases.ack_host_seats`).
    await page.getByRole("button", { name: "Weiter für alle hier" }).click();

    // ── the discussion is the host's to close ──
    await page
      .getByRole("button", { name: "Abstimmung öffnen" })
      .click({ timeout: 60_000 });

    // ── the vote goes round the desk, seat by seat, by keyboard ──
    // Over the queue, because somebody here plays (Z-27).
    await expect(
      page.getByText(
        "Jeder Platz an diesem Rechner stimmt einmal ab. Gib den Rechner reihum weiter.",
      ),
    ).toBeVisible({ timeout: 60_000 });

    let winner = "";
    for (const name of SEATS) {
      const queue = page.locator("li").filter({ hasText: name });
      await queue.getByRole("button", { name: "Abstimmen" }).click();

      // The curtain again: the next voter must not see the last one's ballot.
      await expect(page.getByRole("heading", { name: `${name} ist dran` })).toBeVisible();
      await expect(page.getByRole("button", { name: /Dafür stimmen/ })).toHaveCount(0);
      await page.getByRole("button", { name: "Los", exact: true }).click();

      const pick = page.getByRole("button", { name: /Dafür stimmen/ });
      await expect(pick.first()).toBeVisible();
      await expect(page.getByText(`Platz von ${name}`)).toBeVisible();
      // The first card's name: both seats press 1, so this is what wins.
      const first = (await page.locator("h3").first().innerText()).trim();
      expect(first).not.toBe("");
      if (winner) expect(first).toBe(winner);
      winner = first;

      // A key, not a click: a mouse crossing a projector tells the room the vote.
      await page.keyboard.press("1");
      await expect(pick).toHaveCount(0);

      // Back at the queue after the first seat, with the count (Z-05). After
      // the second the vote closes and round 2 replaces this screen at once.
      if (name === SEATS[0]) {
        await expect(page.getByText("1 von 2 haben abgestimmt")).toBeVisible();
      }
    }

    // ── round 2, on the version that won ──
    await expect(page.getByRole("heading", { name: "Runde 2 von 2" })).toBeVisible({
      timeout: 60_000,
    });
    const afterVote = (await readGame(page, gameId)).active_map_version;
    expect(afterVote).not.toBeNull();
    expect(afterVote).not.toBe(base);

    await playTheDesk(page, 2);

    // ── the second Celery round ends the game by the rule, straight to the summary ──
    // No stats phase: an ending round has none (the socket refuses an ended game).
    await expect(page.getByRole("heading", { name: "Spiel zu Ende" })).toBeVisible({
      timeout: 300_000,
    });
    await expect(page.getByText("2 Runden gefahren")).toBeVisible();
    await expect(page.getByText("Runde 1", { exact: true }).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("Runde 2", { exact: true }).first()).toBeVisible();

    // The vote list names what the class chose, with both votes behind it.
    await expect(page.getByText("Nach Runde 1")).toBeVisible();
    await expect(page.getByText(`„${winner}" ist angenommen.`)).toBeVisible();
    await expect(page.getByText("2 Stimmen")).toBeVisible();

    const ended = await readGame(page, gameId);
    expect(ended.is_active).toBe(false);
    expect(ended.active_map_version).toBe(afterVote);
    const ending = await readEnding(page, gameId);
    expect(ending.end_reason).toBe("max_rounds");
    expect(ending.round_count).toBe(2);

    expect(errors).toEqual([]);
  } finally {
    await endAndDelete(page, gameId, baseURL!);
  }
});
