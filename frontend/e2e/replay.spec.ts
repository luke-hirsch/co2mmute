import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * The animation: watch the round happen, then read what it cost.
 *
 * It plays a whole round to get there, because a recording is the only thing
 * this screen reads and only a finished round has one. That makes this the first
 * spec in the tree that creates a game — so it also deletes it again at the end,
 * rather than leaving a row on whatever database the run points at.
 *
 * The seats are played at the host machine, which is the classroom scenario and
 * the only one a single browser can drive: the desk takes each seat in turn
 * behind the curtain, exactly as a teacher passing the keyboard round would.
 *
 * Two things here are easy to get wrong and cost an afternoon each:
 *
 * - **The mode picker is a radiogroup**, not four buttons — it is one choice out
 *   of four and arrow keys have to work. `getByRole("button", …)` matches
 *   nothing and waits for ever.
 * - **`click()` has no default timeout.** Everything here runs under a
 *   `test.use` action timeout so a selector that will never match fails with a
 *   name instead of hanging until the suite's own deadline.
 */

test.use({ actionTimeout: 20_000 });

/** The whole round-trip: create, seat, start, play, simulate. */
test.setTimeout(420_000);

const MODES = ["Auto", "Bus & Bahn", "Auto", "Fahrrad"];

test("the round is watched before it is read", async ({ page, baseURL }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await loginAsHost(page);
  const gameId = await createGame(page);

  try {
    for (const name of ["Ana", "Ben"]) {
      await page.getByRole("button", { name: "Platz anlegen" }).click();
      await page.getByLabel("Name").fill(name);
      await page.getByRole("button", { name: "Anlegen", exact: true }).click();
      await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
    }

    await page.getByRole("button", { name: "Spiel starten" }).click();

    // Both seats, one after the other, through the curtain.
    for (let seat = 0; seat < 2; seat++) {
      await page.getByRole("button", { name: "Nächster Platz" }).click();
      await page.getByRole("button", { name: "Los", exact: true }).click();

      for (let agent = 0; agent < 2; agent++) {
        await pickMode(page, agent, MODES[seat * 2 + agent]);
      }

      const submit = page.getByRole("button", { name: "Losfahren" });
      await expect(submit).toBeEnabled();
      await submit.click();
    }

    // The simulation runs on a Celery worker, so this is the long wait.
    await expect(page.getByText(/ist gefahren/)).toBeVisible({
      timeout: 300_000,
    });

    // A-01: the animation comes first, and the numbers are not out yet.
    const map = page.getByRole("img", { name: /Karte mit den Fahrten/ });
    await expect(map).toBeVisible();
    await expect(page.getByText("Runde gesamt")).toHaveCount(0);
    await expect(page.getByText(/Ein Punkt steht für/)).toBeVisible();

    // A-05: the clock reads simulated time and runs forward.
    const clock = page.locator("section p.font-mono").first();
    const first = await clock.innerText();
    await expect(clock).not.toHaveText(first, { timeout: 15_000 });

    // A-04: pause holds it, and it starts again.
    await page.getByRole("button", { name: "Anhalten" }).click();
    const held = await clock.innerText();
    await page.waitForTimeout(2500);
    expect(await clock.innerText()).toBe(held);
    await page.getByRole("button", { name: "Abspielen" }).click();

    // A-02: skipping hands the numbers over, and the ack with them.
    await page.getByRole("button", { name: "Überspringen" }).click();
    await expect(page.getByText("Runde gesamt")).toBeVisible();
    await expect(page.getByRole("button", { name: /Weiter/ })).toBeVisible();

    // A-03: and it is still replayable afterwards — the class argues over the
    // map while the table sits under it.
    await page.getByRole("button", { name: "Nochmal ansehen" }).click();
    await expect(map).toBeVisible();
    await expect(page.getByText("Runde gesamt")).toBeVisible();

    expect(errors).toEqual([]);
  } finally {
    await endAndDelete(page, gameId, baseURL!);
  }
});

/**
 * Give one Fahrgast a mode and wait for its route.
 *
 * The route is found on the client, and the row collapses onto a summary when it
 * lands — that is the only signal that the search is over. **A mode can honestly
 * have no route**: home and workplace are drawn at random per seat, and not every
 * pair is reachable by bus. So a refusal is not a failure of this spec, it is a
 * different turn, and the car takes over — a connected street network always has
 * one.
 */
async function pickMode(page: Page, index: number, wanted: string) {
  const row = page.locator("li").filter({ hasText: `Fahrgast ${index + 1}` });
  await row.getByRole("radio", { name: wanted, exact: true }).click();

  const routed = row.getByText("ändern");
  const refused = row.getByText("Auf diesem Weg");
  await expect(routed.or(refused).first()).toBeVisible({ timeout: 60_000 });

  if (await refused.isVisible()) {
    await row.getByRole("radio", { name: "Auto", exact: true }).click();
    await expect(routed).toBeVisible({ timeout: 60_000 });
  }
}

/** Create a game on the seeded map and return its id. */

async function createGame(page: Page): Promise<string> {
  await page.goto("/game/create/");
  await page.locator('input[name="game_name"]').fill("E2E Animation");
  const maps = page.locator('select[name="game_map"]');
  await maps.selectOption(
    (await maps.locator("option").nth(1).getAttribute("value"))!,
  );
  await page.locator('input[name="max_players"]').fill("2");
  await page.locator('input[name="agent_per_player"]').fill("2");
  await page.locator('input[name="max_rounds"]').fill("3");
  // S2's derivation by hand: district_commuters / (seats x Fahrgäste). The
  // server-rendered create form cannot follow the class size yet (S13), and at
  // the form's default this round has too little traffic to draw.
  await page.locator('input[name="people_per_agent"]').fill("800");
  await page.locator('form button[type="submit"]').first().click();
  await page.waitForURL(/\/app\/game\/[^/]+\/?$/);

  const gameId = new URL(page.url()).pathname.split("/").filter(Boolean).pop();
  expect(gameId).toBeTruthy();
  return gameId!;
}

/**
 * End the game and delete it.
 *
 * Ended first, so `end_reason` is recorded the way it would be in a real game,
 * and because a running game is refused by the delete route the profile page
 * uses. Both calls go through the browser's own cookies; Django checks the
 * Referer on a CSRF-protected request over HTTPS, so it is set by hand.
 */
async function endAndDelete(page: Page, gameId: string, baseURL: string) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "csrftoken")?.value;
  if (!csrf) return;
  const headers = { "X-CSRFToken": csrf, Referer: baseURL };

  await page.request.patch(`/api/game/${gameId}/`, {
    headers,
    data: { is_active: false },
  });
  await page.request.delete(`/api/game/${gameId}/`, { headers });
}
