import { expect, test, type Page } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * One way in for every code: a game id and a seat code are typed into the same
 * box, scanned from the same kind of URL, and the screen after it is told by
 * the code's length. The three old paths are gone.
 *
 * Set `E2E_SHOTS` to a folder and the participant card's screens are also saved
 * there, at the phone's width.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(120_000);

const shots = process.env.E2E_SHOTS;

async function shot(page: Page, name: string) {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png` });
}

test("a game id typed into the join box leads to a name and the lobby", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Ein Weg" });

  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const phone = await context.newPage();
  try {
    await phone.goto("/app/join/");
    await expect(
      phone.getByLabel("Spiel-ID, Platz-Code oder Teilnahmecode").first(),
    ).toBeVisible();
    await phone.getByLabel("Spiel-ID, Platz-Code oder Teilnahmecode").last().fill(gameId);
    await phone.getByRole("button", { name: "Weiter" }).click();

    await phone.getByLabel("Dein Name").fill("Ana");
    await phone.getByRole("button", { name: "Beitreten", exact: true }).click();
    await phone.waitForURL(/\/app\/game\/[^/]+\/?$/);
  } finally {
    await context.close();
  }
});

test("a seat code typed or scanned asks, then takes the seat over", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Platzcode" });

  const first = await browser.newContext({ ignoreHTTPSErrors: true });
  const oldPhone = await first.newPage();
  const second = await browser.newContext({ ignoreHTTPSErrors: true });
  const newPhone = await second.newPage();
  try {
    await joinAsPlayer(oldPhone, gameId, "Ana");

    const lobby = await oldPhone.request.get(`/api/game/${gameId}/lobby/`);
    const seat = (await lobby.json()).players.find(
      (p: { name: string }) => p.name === "Ana",
    );
    const issued = await oldPhone.request.post(
      `/api/game/${gameId}/player/${seat.player_id}/code/`,
    );
    expect(issued.status()).toBe(201);
    const { code } = await issued.json();
    expect(code).toHaveLength(7);

    // Typed into the box.
    await newPhone.goto("/app/join/");
    await newPhone.getByLabel("Spiel-ID, Platz-Code oder Teilnahmecode").last().fill(code);
    await newPhone.getByRole("button", { name: "Weiter" }).click();
    await expect(
      newPhone.getByText("Du übernimmst den Platz von Ana", { exact: false }),
    ).toBeVisible();

    // The scanned QR is the same URL: it asks again and uses nothing up.
    await newPhone.goto(`/app/join/${code}`);
    await expect(
      newPhone.getByText("Du übernimmst den Platz von Ana", { exact: false }),
    ).toBeVisible();

    await newPhone.getByRole("button", { name: "Platz übernehmen" }).click();
    await newPhone.waitForURL(/\/app\/game\/[^/]+\/?$/);
  } finally {
    await first.close();
    await second.close();
  }
});

test("the old API paths are gone", async ({ request }) => {
  for (const path of [
    "/api/game/lookup/ABC123/",
    "/api/game/seat/ABC1234/",
  ]) {
    const response = await request.get(path);
    expect(response.ok()).toBe(false);
  }
});

/** A study with twelve codes, through the staff pages; the games linked by id. */
async function makeStudy(
  page: Page,
  name: string,
  gameIds: string[],
): Promise<string[]> {
  await page.goto("/app/studies");
  await page.getByRole("button", { name: "Neue Studie" }).click();
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Studie anlegen" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await page.getByRole("button", { name: "Codes erzeugen" }).click();
  await expect(page.getByText("12 Codes")).toBeVisible();
  for (const [index, id] of gameIds.entries()) {
    await page.getByLabel("Spiel-ID").fill(id);
    await page.getByRole("button", { name: "Spiel verknüpfen" }).click();
    // Each link's own row, not the first one again: a card read before the
    // second link lands sees one waiting game.
    await expect(page.getByText("wartet in der Lobby")).toHaveCount(index + 1);
  }
  const pk = new URL(page.url()).pathname.split("/").filter(Boolean).pop();
  const codes = await (await page.request.get(`/api/studies/${pk}/codes/`)).json();
  return codes.map((row: { code: string }) => row.code);
}

test("a participant code finds the waiting game, once per game", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const first = await createGame(page, { name: "E2E Karte eins" });
  const codes = await makeStudy(page, "E2E Karten", [first]);

  const phone = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 375, height: 800 },
  });
  const other = await browser.newContext({ ignoreHTTPSErrors: true });
  try {
    const one = await phone.newPage();
    await one.goto(`/app/join/${codes[0]}`);
    await one.getByLabel("Dein Name").fill("Ana");
    await shot(one, "karte-name-375");
    await one.getByRole("button", { name: "Beitreten", exact: true }).click();
    await one.waitForURL(/\/app\/game\/[^/]+\/?$/);

    // The same card again: the game it played is not offered any more.
    const again = await other.newPage();
    await again.goto(`/app/join/${codes[0]}`);
    await expect(
      again.getByText("in allen wartenden Spielen schon mitgespielt", { exact: false }),
    ).toBeVisible();

    // A game id of a study with cards still joins, and points at the card.
    await again.goto(`/app/join/${first}`);
    await expect(
      again.getByText("Hast du eine Teilnahmekarte? Dann scann lieber die."),
    ).toBeVisible();
    await shot(again, "spiel-id-hinweis-375");
  } finally {
    await phone.close();
    await other.close();
  }
});

test("a card with two waiting games asks which, one with none says so", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const a = await createGame(page, { name: "E2E Karte A" });
  const b = await createGame(page, { name: "E2E Karte B" });
  const codes = await makeStudy(page, "E2E Zwei", [a, b]);
  const empty = await makeStudy(page, "E2E Leer", []);

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 375, height: 800 },
  });
  try {
    const phone = await context.newPage();
    await phone.goto(`/app/join/${codes[0]}`);
    await expect(phone.getByRole("heading", { name: "Welches Spiel?" })).toBeVisible();
    await shot(phone, "welches-spiel-375");
    await phone.getByRole("button", { name: /E2E Karte B/ }).click();
    await phone.getByLabel("Dein Name").fill("Ben");
    await phone.getByRole("button", { name: "Beitreten", exact: true }).click();
    // The lobby rendered, not only its URL: the game route still navigates on
    // its own, and a goto now would be cut off by it.
    await expect(phone.getByRole("button", { name: "Chat" })).toBeVisible();

    await phone.goto(`/app/join/${empty[0]}`);
    await expect(
      phone.getByText("Gerade wartet kein Spiel dieser Studie. Frag die Spielleitung."),
    ).toBeVisible();
    await shot(phone, "kein-spiel-375");

    // The typed box takes the longer code too.
    await phone.goto("/app/join/");
    await expect(
      phone.getByLabel("Spiel-ID, Platz-Code oder Teilnahmecode").last(),
    ).toBeVisible();
    await phone.getByLabel("Spiel-ID, Platz-Code oder Teilnahmecode").last().fill(codes[1]);
    await expect(
      phone.getByLabel("Spiel-ID, Platz-Code oder Teilnahmecode").last(),
    ).toHaveValue(codes[1]);
  } finally {
    await context.close();
  }
});
