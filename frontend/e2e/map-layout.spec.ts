import { expect, test } from "@playwright/test";

import { createGame, joinAsPlayer } from "./game";
import { loginAsHost } from "./host";

/**
 * The map beside the turn, or above it (S24).
 *
 * The research group asked for beside on large screens; a beamer is a large
 * screen too and beside is wrong there, so it is a switch and the default is the
 * old layout. The switch only exists from `lg` (1024px) up, and what is asserted
 * is geometry rather than classes: beside means the map's right edge is left of
 * the list's left edge, above means the list starts below the map's bottom.
 * `template/legal/cookies.html` §3.4 promises a single remembered setting, so
 * the reload is held here too.
 */

test.use({ actionTimeout: 20_000 });
test.setTimeout(120_000);

test("the map can sit beside the turn on a large screen", async ({
  browser,
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Layout" });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1400, height: 900 },
  });
  const player = await context.newPage();
  const errors: string[] = [];
  player.on("pageerror", (error) => errors.push(error.message));

  try {
    await joinAsPlayer(player, gameId, "Ana");
    await page.getByRole("button", { name: "Spiel starten" }).click();

    const map = player.getByRole("region", { name: "Karte" });
    const list = player.getByRole("heading", { name: "Deine Gruppen" });
    await expect(map).toBeVisible({ timeout: 30_000 });

    const above = async () => {
      const m = await map.boundingBox();
      const l = await list.boundingBox();
      return l!.y >= m!.y + m!.height - 1;
    };

    // Default: above, exactly as before the switch existed.
    expect(await above()).toBe(true);

    await player.getByRole("button", { name: "Daneben" }).click();
    await expect.poll(above).toBe(false);
    const m = (await map.boundingBox())!;
    const l = (await list.boundingBox())!;
    expect(m.x + m.width).toBeLessThanOrEqual(l.x + 1);

    // Remembered on this device…
    await player.reload();
    await expect(map).toBeVisible({ timeout: 30_000 });
    await expect.poll(above).toBe(false);

    // …and gone from a phone, where there is one column and nothing to choose.
    await player.setViewportSize({ width: 390, height: 800 });
    await expect(player.getByRole("button", { name: "Daneben" })).toBeHidden();
    expect(await above()).toBe(true);

    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});
