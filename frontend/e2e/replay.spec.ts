import { expect, test } from "@playwright/test";

import { createGame, endAndDelete, pickMode } from "./game";
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
  const gameId = await createGame(page, {
    name: "E2E Animation",
    agentPerPlayer: 2,
    maxRounds: 3,
    // Deliberately below what the screen derives (1600 here): enough traffic to
    // draw, without making the e2e run wait for a full-size round.
    peoplePerAgent: 800,
  });

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
    // A-13: 800 people to a Gruppe at a stride of ten — exactly ten to a dot (S25).
    await expect(page.getByText(/Ein Punkt steht für 10 Menschen/)).toBeVisible();

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
