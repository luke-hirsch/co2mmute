import { expect, test, type Page } from "@playwright/test";

import { createGame } from "./game";
import { loginAsHost } from "./host";

/**
 * S4: the numbers say what scale they are on, and the summary says what the
 * class decided.
 *
 * Covers Z-15 … Z-18 and E-11 … E-13 in `docs/testfaelle.md`. One round is
 * enough for all of it — the class-scale figures, the switch, the timetable's own
 * share and the explainer are all per round, and the host then ends the game by
 * hand so the summary is reached without paying for a second simulation.
 *
 * **The round it plays must not be the last one.** An ending round gets no stats
 * phase and cannot have one: `ws_auth.resolve_player` refuses a socket for a game
 * with an `ended_at`, so a phase there could never be acked or seen. Hence
 * `max_rounds: 2` and an ending by hand rather than `max_rounds: 1`, which would
 * skip the table this spec is about.
 *
 * The seats are played at the host machine — the classroom scenario, and the only
 * one a single browser can drive.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(420_000);

const MODES = ["Auto", "Auto", "Fahrrad", "Auto"];

test("the numbers name their scale, and the summary names the vote", async ({
  page,
  baseURL,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Zahlen",
    agentPerPlayer: 2,
    // Deliberately below what the screen derives (1600 on this map at this
    // class size): half the traffic, so the round simulates quickly, and still
    // enough of it that there are numbers to read.
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
    await page.getByRole("button", { name: "Überspringen" }).click();
    await expect(page.getByText("Runde gesamt")).toBeVisible();

    // ── Z-15: the table says which scale it is on, and starts per person ──
    const perPerson = page.getByRole("radio", { name: "pro Person" });
    const everyone = page.getByRole("radio", { name: "alle Pendler" });
    await expect(perPerson).toBeChecked();
    await expect(page.getByText(/Eine Gruppe steht für/)).toBeVisible();

    // Ana's own CO2 cell, in both scales. The whole point of the switch is that
    // these are different numbers, and by three orders of magnitude.
    const anaCo2 = page
      .locator("tr", { has: page.getByRole("rowheader", { name: /Ana/ }) })
      .locator("td")
      .first();
    const asPerson = await anaCo2.innerText();

    // ── Z-16: flipping it changes every figure in the two number columns ──
    // Clicked the way a finger does it — on the label. The input itself is
    // `sr-only`, so the label sits over it and takes the tap, which is exactly
    // what a native radio is supposed to do.
    await page.locator("label", { hasText: "alle Pendler" }).first().click();
    await expect(everyone).toBeChecked();
    await expect(anaCo2).not.toHaveText(asPerson);
    await expect(page.getByText(/Menschen pro Gruppe/)).toBeVisible();

    // And back with the keyboard, because two radios sharing a name are a
    // radiogroup and arrow keys have to move between them.
    await everyone.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(perPerson).toBeChecked();
    await expect(anaCo2).toHaveText(asPerson);

    // ── Z-17: the rows do not add up to the total, and the table says why ──
    // The shipped map carries six train lines and two bus lines; nobody in a
    // two-seat round rides all of them, so there is always an unridden rest.
    await expect(page.getByText("Leer gefahrene Linien")).toBeVisible();
    await expect(page.getByText(/auch wenn niemand einsteigt/)).toBeVisible();

    // ── Z-18: what it cost against what was paid ──
    // The desk has no seat, so it reads the class's line. It compares against
    // what the commutes cost, not the round — the timetable nobody rode has its
    // own row above and inside this gap would read as subsidy.
    await expect(page.getByText(/Für eure Wege/)).toBeVisible();

    // The footer is the wide scale while the rows are per person, and says so.
    await expect(page.getByText("alle Pendler").last()).toBeVisible();

    // ── Z-19: the explainer opens, and is not in the ballot ──
    await page.getByRole("button", { name: "Wie wird gerechnet?" }).click();
    const overlay = page.getByRole("dialog");
    await expect(overlay.getByText("Hinter einer Gruppe stecken viele Menschen")).toBeVisible();
    await expect(overlay.getByText("Der Fahrplan fährt auch leer")).toBeVisible();
    await overlay.getByRole("button", { name: "Verstanden" }).click();
    await expect(overlay).toHaveCount(0);

    // ── the summary, reached by ending the game by hand ──
    await page.getByRole("button", { name: "Spiel beenden" }).first().click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Spiel beenden" })
      .click();
    await expect(page.getByText("Spiel zu Ende")).toBeVisible({ timeout: 30_000 });

    // E-11: the timetable's own cost, named, class scale.
    await expect(page.getByText("Was der Fahrplan gekostet hat")).toBeVisible();
    await expect(page.getByText("Fahrplan insgesamt")).toBeVisible();
    // Nobody in this round rides, so the unridden share *is* the timetable and
    // the second row would repeat the first number (S24): one sentence instead.
    await expect(
      page.getByText("Niemand ist mitgefahren: Der ganze Fahrplan lief leer."),
    ).toBeVisible();
    await expect(
      page.getByText("davon auf Linien, die niemand genutzt hat"),
    ).toHaveCount(0);

    // E-12: the three lists are per commute, and the switch is on them too.
    await expect(
      page.getByRole("radio", { name: "pro Person" }).first(),
    ).toBeChecked();
    await expect(page.getByText("Am wenigsten CO₂")).toBeVisible();

    // What was paid, inside the cost list, where the subsidy is legible. The
    // rows are `<details>`, so the thing that opens one is its `<summary>`.
    const cheapest = page
      .getByRole("heading", { name: "Am günstigsten" })
      .locator("..");
    await cheapest.locator("summary").first().click();
    // `.first()`, because a closed `<details>` keeps its children in the DOM —
    // every row has this line and strict mode counts them before it checks
    // whether any of them is on screen.
    await expect(cheapest.getByText("davon selbst bezahlt").first()).toBeVisible();

    // E-13: the vote list. One round and a single-version map, so it is the
    // honest empty case rather than a missing section.
    await expect(page.getByText("Was ihr geändert habt")).toBeVisible();
    await expect(
      page.getByText("In diesem Spiel wurde nichts abgestimmt."),
    ).toBeVisible();

    expect(errors).toEqual([]);
  } finally {
    await endAndDelete(page, gameId, baseURL!);
  }
});

/**
 * Give one Gruppe a mode and wait for its route. A mode can honestly have no
 * route — home and workplace are drawn at random per seat — so a refusal falls
 * back to the car, which a connected street network always has.
 */
async function pickMode(page: Page, index: number, wanted: string) {
  const row = page.locator("li").filter({ hasText: `Gruppe ${index + 1}` });
  await row.getByRole("radio", { name: wanted, exact: true }).click();

  const routed = row.getByText("ändern");
  const refused = row.getByText("Auf diesem Weg");
  await expect(routed.or(refused).first()).toBeVisible({ timeout: 60_000 });

  if (await refused.isVisible()) {
    await row.getByRole("radio", { name: "Auto", exact: true }).click();
    await expect(routed).toBeVisible({ timeout: 60_000 });
  }
}


/** End the game if it is still running, then delete it. */
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
