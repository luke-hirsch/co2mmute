import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * Muting a seat in the chat (S9).
 *
 * `Player.is_muted` and `MuteUnmutePlayerView` had both existed since 1.x and
 * neither did anything: the view was routed nowhere, and no consumer read the
 * flag. So this spec is the first thing that has ever exercised the feature
 * end to end, and it needs the whole chain — the host's list writes it, the
 * roster carries it, `ChatConsumer` obeys it.
 *
 * **Two browser contexts, and there is no way round it.** A seat played at the
 * host machine shares the host's cookies and the host's socket, and the host
 * chats as a `HostPlayer` duck-type that is never muted (`ws_auth.py`). So the
 * only device that can prove a mute is a real second one, joined through the
 * student funnel.
 *
 * Needs **Redis**, like `chat.spec.ts`: `ChatConsumer` is the one consumer
 * that talks to it directly. A red run here with a green `smoke.spec.ts` means
 * valkey is down.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(180_000);

test("a muted seat is told so, and can write again once it is lifted", async ({
  page,
  browser,
  baseURL,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await loginAsHost(page);
  const gameId = await createGame(page);

  let playerContext: BrowserContext | null = null;

  try {
    playerContext = await browser.newContext({ ignoreHTTPSErrors: true });
    const player = await playerContext.newPage();
    await joinAsPlayer(player, gameId, "Ana");

    // Ana can write before anything is done to her, or the assertion below
    // would pass against a chat that never worked.
    await player.getByRole("button", { name: "Chat" }).click();
    const playerPanel = player.getByRole("region", { name: "Chat" });
    await send(player, "bin da");
    await expect(playerPanel.getByText("bin da")).toBeVisible();

    // The host's roster has Ana on it, unmuted, with a mute control.
    const anaRow = page.locator("li").filter({ hasText: "Ana" }).first();
    await expect(anaRow).toBeVisible();
    await expect(anaRow.getByText("stummgeschaltet")).toHaveCount(0);

    // Muting asks first — taking the chat away is not a mis-tap's business.
    await anaRow.getByRole("button", { name: "Stummschalten" }).click();
    await page
      .getByRole("button", { name: "Stummschalten", exact: true })
      .last()
      .click();

    // The badge arrives over the socket. Nothing here refetches: `set_muted`
    // broadcasts the roster, which is the one place a screen looks.
    await expect(anaRow.getByText("stummgeschaltet")).toBeVisible();

    // And Ana's next line is refused — in German, and saying why. The backend
    // answers the English "You are muted"; that must not reach the class.
    await player.waitForTimeout(500);
    await send(player, "und jetzt?");
    await expect(playerPanel.getByText(/stummgeschaltet/)).toBeVisible();
    await expect(playerPanel.getByText("You are muted")).toHaveCount(0);
    await expect(playerPanel.getByText("und jetzt?")).toHaveCount(0);

    // Nobody else sees it either — a refused line must not be stored or
    // broadcast, or muting is only a label on a message everybody still reads.
    await page.getByRole("button", { name: "Chat" }).click();
    const hostPanel = page.getByRole("region", { name: "Chat" });
    await expect(hostPanel.getByText("bin da")).toBeVisible();
    await expect(hostPanel.getByText("und jetzt?")).toHaveCount(0);
    await page.getByRole("button", { name: "Chat schließen" }).click();

    // Lifting it needs no confirmation, and Ana does not have to reconnect:
    // the flag is read per message, not kept from the handshake.
    await anaRow.getByRole("button", { name: "Stummschaltung aufheben" }).click();
    await expect(anaRow.getByText("stummgeschaltet")).toHaveCount(0);

    await player.waitForTimeout(500);
    await send(player, "wieder da");
    await expect(playerPanel.getByText("wieder da")).toBeVisible();

    expect(errors).toEqual([]);
  } finally {
    await playerContext?.close();
    await endAndDelete(page, gameId, baseURL!);
  }
});

async function send(page: Page, text: string) {
  const panel = page.getByRole("region", { name: "Chat" });
  await panel.getByRole("textbox").fill(text);
  await panel.getByRole("button", { name: "Senden" }).click();
}

/** Create a game on the seeded map and return its id. */
async function createGame(page: Page): Promise<string> {
  await page.goto("/game/create/");
  await page.locator('input[name="game_name"]').fill("E2E Mute");
  const maps = page.locator('select[name="game_map"]');
  await maps.selectOption(
    (await maps.locator("option").nth(1).getAttribute("value"))!,
  );
  await page.locator('input[name="max_players"]').fill("2");
  await page.locator('input[name="agent_per_player"]').fill("1");
  await page.locator('input[name="max_rounds"]').fill("2");

  await page.locator('form button[type="submit"]').first().click();
  await page.waitForURL(/\/app\/game\/[^/]+\/?$/);

  const gameId = new URL(page.url()).pathname.split("/").filter(Boolean).pop();
  expect(gameId).toBeTruthy();
  return gameId!;
}

async function joinAsPlayer(page: Page, gameId: string, name: string) {
  await page.goto(`/join/${gameId}/`);
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.locator("form input[type=text]").first().fill(name);
  await page.locator('form button[type="submit"]').first().click();
  await page.waitForURL(/\/app\/game\/[^/]+\/?$/);
}

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
