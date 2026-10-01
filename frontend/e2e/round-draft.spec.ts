import { expect, test, type Page } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * A locked phone must not cost the turn (S7, R-22).
 *
 * The case is the ordinary one in a classroom rather than an edge case: a
 * student picks a mode for one Gruppe, the screen goes dark while they argue
 * with the next desk, and the phone discards the page. Before S7 the half-made
 * turn went with it.
 *
 * Driven on a **player's own device**, not at the host desk, because that is
 * where it happens and because the desk deliberately forgets which seat it was
 * playing — the curtain is the point there. A student's own seat comes from
 * `whoami`, so a reload lands straight back on the same turn.
 *
 * What is asserted is the shape of the thing, not just that something came
 * back: the chosen Gruppe is routed again **and** the untouched one is still
 * empty, with the turn still refusing to be sent. A restore that filled in both
 * would pass a weaker test and be a worse bug than the one being fixed.
 *
 * Note the route is never stored — only the tap. So this also pins that the
 * pathfinder runs again on reload: the row only collapses onto its summary once
 * a route has actually been found.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(180_000);

test("a reload keeps the half-made turn", async ({ browser, page, baseURL }) => {
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Entwurf",
    // Two seats, because the form refuses more Gruppen per person than there
    // are seats. Only one is ever joined; the round never completes, which is
    // the point.
    agentPerPlayer: 2,
  });

  const playerContext = await browser.newContext({ ignoreHTTPSErrors: true });
  const player = await playerContext.newPage();

  const errors: string[] = [];
  player.on("pageerror", (error) => errors.push(error.message));

  try {
    await joinAsPlayer(player, gameId, "Ana");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    const first = row(player, 1);
    const second = row(player, 2);

    await expect(first.getByRole("radiogroup")).toBeVisible({ timeout: 30_000 });

    // Half a turn: one Gruppe chosen, one untouched.
    const mode = await pickRoutableMode(player, 1);
    await expect(second.getByRole("radiogroup")).toBeVisible();
    await expect(player.getByRole("button", { name: "Losfahren" })).toBeDisabled();

    await player.reload();

    // R-22: the tap is back, and the route with it — found again, not restored.
    await expect(first.getByText("ändern")).toBeVisible({ timeout: 60_000 });
    await expect(first.getByText(mode, { exact: true })).toBeVisible();
    // R-23: the way home was found with it, and is on the card.
    await expect(first.getByText(/^zurück \d+/)).toBeVisible();

    // …and nothing was invented for the one that was never chosen.
    await expect(second.getByRole("radiogroup")).toBeVisible();
    await expect(second.getByText("ändern")).toHaveCount(0);
    await expect(player.getByRole("button", { name: "Losfahren" })).toBeDisabled();

    await expect.poll(() => stored(player)).toHaveLength(1);

    // Finish the turn: the draft has done its job and must not outlive it.
    // `template/legal/cookies.html` §3.3 promises exactly this in writing —
    // "gelöscht, sobald du die Runde abschickst" — so it is held by a test
    // rather than by the comment above the code that does it.
    await pickRoutableMode(player, 2);
    const submit = player.getByRole("button", { name: "Losfahren" });
    await expect(submit).toBeEnabled();
    await submit.click();

    await expect(
      player.getByRole("heading", { name: "Abgeschickt" }),
    ).toBeVisible({ timeout: 30_000 });
    await expect.poll(() => stored(player)).toHaveLength(0);

    expect(errors).toEqual([]);
  } finally {
    await playerContext.close();
    await endAndDelete(page, gameId, baseURL!);
  }
});

/**
 * The draft keys this device is holding.
 *
 * Read out of the browser rather than asserted through the interface, because
 * there is nothing on screen to see: the entry is a retention promise, not a
 * feature. `co2mmute.draft.` is `draft-storage.ts`'s prefix.
 *
 * **Polled by every caller, never `expect(...).resolves`.** The write and the
 * clear are React effects, which flush *after* the paint that made the row or
 * the heading visible — so a single read can land in the window between the two
 * and fail for no reason. It did, once, in a full run under load.
 */
async function stored(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    Object.keys(window.localStorage).filter((key) =>
      key.startsWith("co2mmute.draft."),
    ),
  );
}

/** One Gruppe's row. */
function row(page: Page, index: number) {
  return page.locator("li").filter({ hasText: `Gruppe ${index}` });
}

/**
 * Pick a mode that actually routes, and say which it was.
 *
 * Home and workplace are drawn at random per seat, so a bike or a walk can
 * honestly have no route — the car is the fallback a connected street network
 * always has. Which mode it ends up being does not matter here; that the same
 * one comes back does.
 */
async function pickRoutableMode(page: Page, index: number): Promise<string> {
  const target = row(page, index);
  const routed = target.getByText("ändern");
  const refused = target.getByText("Auf diesem Weg");

  for (const mode of ["Fahrrad", "Auto"]) {
    await target.getByRole("radio", { name: mode, exact: true }).click();
    await expect(routed.or(refused).first()).toBeVisible({ timeout: 60_000 });
    if (await routed.isVisible()) return mode;
  }

  throw new Error("no mode routed for this seat — the map or the seed is wrong");
}



/** End the game and delete it, so a run leaves no row behind. */
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
