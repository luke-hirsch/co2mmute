import { expect, test } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * The host's lobby and the end card (F3): the password on the projector, an
 * invitation to copy, the chat as a switch every screen follows, and a way back
 * to the host's games once a game is over.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(120_000);

test("the lobby shows the password and copies an invitation with it", async ({
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, {
    name: "E2E Einladung",
    password: "Tram42",
  });

  await expect(page.getByText("Tram42", { exact: true })).toBeVisible();

  // The real clipboard first: WebKit takes the write on a click.
  await page.getByRole("button", { name: "Einladung kopieren" }).click();
  await expect(page.getByRole("button", { name: "Kopiert" })).toBeVisible();

  // It will not let the page read it back, so the second copy is caught on
  // its way in — what is checked is the text, not WebKit.
  await page.evaluate(() => {
    const w = window as unknown as { copied?: string };
    navigator.clipboard.writeText = async (text: string) => {
      w.copied = text;
    };
  });
  await expect(page.getByRole("button", { name: "Einladung kopieren" })).toBeVisible({
    timeout: 5_000,
  });
  await page.getByRole("button", { name: "Einladung kopieren" }).click();
  const text = await page.evaluate(
    () => (window as unknown as { copied?: string }).copied ?? "",
  );
  expect(text).toContain(`/app/join/${gameId}`);
  expect(text).toContain(`Spiel-ID: ${gameId}`);
  expect(text).toContain("Passwort: Tram42");
  expect(text).toContain("„E2E Einladung“");
});

test("the host switches the chat off and on, and the phone follows", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Chatschalter" });

  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const player = await context.newPage();
  try {
    await joinAsPlayer(player, gameId, "Ana");
    const dock = player.getByRole("button", { name: "Chat" });
    await expect(dock).toBeVisible();

    const box = page.getByRole("checkbox", { name: "an" });
    await expect(box).toBeChecked();

    await box.uncheck();
    await expect(dock).toHaveCount(0);
    await expect(player.getByText("aus", { exact: true })).toBeVisible();
    await expect(box).not.toBeChecked();

    await box.check();
    await expect(dock).toBeVisible();
    await expect(box).toBeChecked();
  } finally {
    await context.close();
  }
});

test("a finished game leads the host back to their games", async ({ page }) => {
  await loginAsHost(page);
  await createGame(page, { name: "E2E Zurück" });

  await page.getByRole("button", { name: "Spiel beenden" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Spiel beenden" })
    .click();

  await page.getByRole("button", { name: "Zu deinen Spielen" }).click();
  await expect(page).toHaveURL(/\/app\/host\/?$/);
  await expect(page.getByRole("heading", { name: "Deine Spiele" })).toBeVisible();
});
