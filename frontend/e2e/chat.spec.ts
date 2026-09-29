import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { createGame } from "./game";
import { loginAsHost } from "./host";

/**
 * The chat (S8 — C-01 to C-05, R-13).
 *
 * Two browser contexts, because the headline case cannot be proved with one:
 * C-01 is "a message reaches everyone", and a seat played at the host machine
 * shares the host's cookies and the host's socket. So the second context joins
 * through the real funnel — `/join/<id>/`, a screen name, no account — which is
 * also the only student-shaped path there is.
 *
 * It runs in the lobby rather than mid-round on purpose. `GameFrame` mounts the
 * dock once for every screen in a game, so the lobby exercises the same
 * component the round does, and it does not need a Celery worker to have
 * finished a simulation first.
 *
 * What the chat needs that nothing else in this tree does: **Redis**.
 * `ChatConsumer` is the one consumer that talks to it directly — history and
 * both rate limits live there — so a red run here with a green `smoke.spec.ts`
 * means valkey is down, not that the feature broke.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(180_000);

test("a message reaches the other device, and survives a reload", async ({
  page,
  browser,
  baseURL,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Chat", agentPerPlayer: 1 });

  let playerContext: BrowserContext | null = null;

  try {
    // L-06: the lobby says the chat is on, which it only may while there is a
    // way to reach it. The row was deleted in F5 for promising otherwise.
    await expect(page.getByText("Chat", { exact: true }).first()).toBeVisible();

    // C-05 / R-13: reachable from the game screen at all.
    const openChat = page.getByRole("button", { name: "Chat" });
    await openChat.click();

    const panel = page.getByRole("region", { name: "Chat" });
    await expect(panel).toBeVisible();
    await expect(panel.getByText("Noch nichts geschrieben.")).toBeVisible();

    // The retention promise stands beside the transcript, not only on the
    // cookie page — `CHAT_HISTORY_TTL_SECONDS` is two hours.
    await expect(panel.getByText(/zwei Stunden/)).toBeVisible();

    // C-01, first half: the host writes.
    await send(page, "hallo zusammen");
    await expect(panel.getByText("hallo zusammen")).toBeVisible();
    // The host chats as "<username> (Host)" — `HostPlayer.name` in ws_auth.py.
    await expect(panel.getByText(/\(Host\)/).first()).toBeVisible();

    // C-02: a reload gets the history back. Nothing is in browser storage —
    // `ChatConsumer.connect()` replays it from Redis on every connect.
    await page.reload();
    await page.getByRole("button", { name: "Chat" }).click();
    await expect(panel.getByText("hallo zusammen")).toBeVisible();

    // C-01, second half: a real second device, joined as a student would.
    playerContext = await browser.newContext({ ignoreHTTPSErrors: true });
    const player = await playerContext.newPage();
    await joinAsPlayer(player, gameId, "Ana");

    await player.getByRole("button", { name: "Chat" }).click();
    const playerPanel = player.getByRole("region", { name: "Chat" });

    // The history the host wrote before this device existed is there too.
    await expect(playerPanel.getByText("hallo zusammen")).toBeVisible();

    await send(player, "hallo Ana hier");
    await expect(playerPanel.getByText("hallo Ana hier")).toBeVisible();

    // And it arrives on the host's screen without a reload — the whole point.
    await expect(panel.getByText("hallo Ana hier")).toBeVisible();
    await expect(panel.getByText("Ana", { exact: true }).first()).toBeVisible();

    // What arrives while the panel is shut is counted on the button. The count
    // is a high-water mark against the transcript length, not a tally of
    // events, so that a reconnect replaying the history cannot inflate it.
    await page.getByRole("button", { name: "Chat schließen" }).click();
    const button = page.getByRole("button", { name: "Chat" });
    await expect(button).toBeVisible();
    await expect(button).not.toContainText("1");

    // 0.35 s is `INDIVIDUAL_RATE_LIMIT_SECONDS`, and the three steps above take
    // less than that — a negative Playwright assertion returns the moment it
    // holds rather than waiting out its timeout. Without this the second
    // message is refused and the badge is correctly 0, which reads as a bug in
    // the counter. Nobody types two sentences this fast.
    await player.waitForTimeout(500);
    await send(player, "und noch was");
    // It really went, rather than being refused — otherwise the next assertion
    // would be testing the rate limit instead of the counter.
    await expect(playerPanel.getByText("und noch was")).toBeVisible();

    await expect(button).toContainText("1");

    // Opening clears it, and it stays cleared.
    await button.click();
    await expect(panel.getByText("und noch was")).toBeVisible();
    await page.getByRole("button", { name: "Chat schließen" }).click();
    await expect(page.getByRole("button", { name: "Chat" })).not.toContainText(
      "1",
    );

    expect(errors).toEqual([]);
  } finally {
    await playerContext?.close();
    await endAndDelete(page, gameId, baseURL!);
  }
});

test("the rate limit says so in German", async ({ page, baseURL }) => {
  // C-03. `INDIVIDUAL_RATE_LIMIT_SECONDS` is 0.35, so two messages typed as
  // fast as a script can type them trip it. The backend answers "Slow down";
  // what the class must not see is that sentence.
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Chat", agentPerPlayer: 1 });

  try {
    await page.getByRole("button", { name: "Chat" }).click();
    const panel = page.getByRole("region", { name: "Chat" });

    for (const text of ["eins", "zwei", "drei"]) {
      await panel.getByRole("textbox").fill(text);
      await panel.getByRole("button", { name: "Senden" }).click();
    }

    await expect(panel.getByText(/Nicht so schnell|gleichzeitig/)).toBeVisible();
    await expect(panel.getByText("Slow down")).toHaveCount(0);
  } finally {
    await endAndDelete(page, gameId, baseURL!);
  }
});

/**
 * C-04.
 *
 * `chat_enabled` is switched **through the API**, because there is no control
 * for it anywhere: it is not on the create form, and the host lobby has no
 * toggle. `PATCH /api/game/<id>/` is the only way, and it is what this drives.
 *
 * The reload is not a convenience either. `chat_enabled` reaches the client
 * only in the REST lobby snapshot (`staleTime: Infinity`) — `game.state` does
 * not carry it and no event fires when it changes — so a running client does
 * not find out until it asks again.
 */
test("no chat is offered when the chat is switched off", async ({
  page,
  baseURL,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Chat", agentPerPlayer: 1 });

  try {
    await expect(page.getByRole("button", { name: "Chat" })).toBeVisible();

    await patchGame(page, gameId, baseURL!, { chat_enabled: false });
    await page.reload();

    // The dock renders nothing at all rather than a disabled button: the
    // server has wiped the history, so there is nothing behind it.
    await expect(page.getByRole("button", { name: "Chat" })).toHaveCount(0);
    await expect(page.getByText("aus").first()).toBeVisible();
  } finally {
    await endAndDelete(page, gameId, baseURL!);
  }
});

/**
 * R-13, and it is deliberately not inferred from the lobby.
 *
 * "Reachable from every screen" is a claim about `GameFrame`, and the round
 * screen is the one that owns its viewport and has a submit button at the
 * bottom — exactly where a floating dock can end up sitting on top of the
 * control it must not cover. So the round is entered for real.
 */
test("the chat is reachable while the round is being played", async ({
  page,
  baseURL,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Chat", agentPerPlayer: 1 });

  try {
    await page.getByRole("button", { name: "Platz anlegen" }).click();
    await page.getByLabel("Name").fill("Ana");
    await page.getByRole("button", { name: "Anlegen", exact: true }).click();
    await expect(page.getByText("Ana", { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "Spiel starten" }).click();
    await page.getByRole("button", { name: "Nächster Platz" }).click();
    await page.getByRole("button", { name: "Los", exact: true }).click();

    // On the round screen: the passenger is waiting for a mode.
    await expect(page.getByText("Gruppe 1")).toBeVisible();

    await page.getByRole("button", { name: "Chat" }).click();
    const panel = page.getByRole("region", { name: "Chat" });
    await expect(panel).toBeVisible();

    await send(page, "welchen Weg nehmt ihr?");
    await expect(panel.getByText("welchen Weg nehmt ihr?")).toBeVisible();

    // And the turn is still playable underneath — the dock is not modal, and
    // the mode picker is a radiogroup rather than four buttons.
    await page.getByRole("button", { name: "Chat schließen" }).click();
    await expect(
      page.getByRole("radio", { name: "Auto", exact: true }).first(),
    ).toBeVisible();
  } finally {
    await endAndDelete(page, gameId, baseURL!);
  }
});

async function patchGame(
  page: Page,
  gameId: string,
  baseURL: string,
  data: Record<string, unknown>,
) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "csrftoken")?.value;
  const response = await page.request.patch(`/api/game/${gameId}/`, {
    headers: { "X-CSRFToken": csrf ?? "", Referer: baseURL },
    data,
  });
  expect(response.ok()).toBe(true);
}

async function send(page: Page, text: string) {
  const panel = page.getByRole("region", { name: "Chat" });
  await panel.getByRole("textbox").fill(text);
  await panel.getByRole("button", { name: "Senden" }).click();
}


/**
 * Join as a student: no account, a screen name, two signed cookies.
 *
 * The two-step Django funnel — `/join/<id>/` confirms the game, then the next
 * form takes the name — and it ends in the SPA at `/app/game/<id>`.
 */
async function joinAsPlayer(page: Page, gameId: string, name: string) {
  await page.goto(`/join/${gameId}/`);
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.locator("form input[type=text]").first().fill(name);
  await page.locator('form button[type="submit"]').first().click();
  await page.waitForURL(/\/app\/game\/[^/]+\/?$/);
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
