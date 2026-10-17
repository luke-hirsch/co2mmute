import { expect, test } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * One way in for every code: a game id and a seat code are typed into the same
 * box, scanned from the same kind of URL, and the screen after it is told by
 * the code's length. The three old paths are gone.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(120_000);

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
      phone.getByLabel("Spiel-ID oder Platz-Code").first(),
    ).toBeVisible();
    await phone.getByLabel("Spiel-ID oder Platz-Code").last().fill(gameId);
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
    await newPhone.getByLabel("Spiel-ID oder Platz-Code").last().fill(code);
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
