import { expect, type Page } from "@playwright/test";

/**
 * Making a game, for every spec that needs one to play in.
 *
 * It was copied into five spec files, which is how two of them ended up
 * carrying a comment about a limitation S13 has since removed. One copy, beside
 * `host.ts`, for the same reason: the create screen is a screen, it changes,
 * and a change to it should break one helper rather than five.
 *
 * The route is the Django one on purpose. `/game/create/` is a login-gated
 * redirect into `/app/game/create`, so going through it exercises the doorway
 * every link in the funnel still points at — and a spec that lands on the login
 * page instead fails here, where it is obvious, rather than on a form that
 * never appeared.
 */

/** What `e2e/seed.mjs` calls the map it uploads. */
export const MAP_NAME = process.env.E2E_MAP_NAME ?? "E2E Berlin";

export type CreateGameOptions = {
  /** The game's name. Each spec uses its own, so a run is readable in the admin. */
  name: string;
  maxPlayers?: number;
  agentPerPlayer?: number;
  maxRounds?: number;
  /**
   * Type over the derived `people_per_agent`.
   *
   * Only for a spec that wants a deliberately lighter round than the map's
   * calibration would give it. Leaving it out is the normal case and is what
   * S13 is about: the screen derives it from the class size.
   */
  peoplePerAgent?: number;
};

/** Create a game on the seeded map and return its id. Requires a host session. */
export async function createGame(
  page: Page,
  options: CreateGameOptions,
): Promise<string> {
  const {
    name,
    maxPlayers = 2,
    agentPerPlayer = 1,
    maxRounds = 2,
    peoplePerAgent,
  } = options;

  await page.goto("/game/create/");
  await page.waitForURL(/\/app\/game\/create\/?$/);

  await page.locator("#game_name").fill(name);
  // By label, not by index: the box a run points at may hold other maps, and
  // "the second option" is how a spec silently starts playing on one of them.
  await page.locator("#game_map").selectOption({ label: MAP_NAME });
  await page.locator("#max_players").fill(String(maxPlayers));
  await page.locator("#agent_per_player").fill(String(agentPerPlayer));
  await page.locator("#max_rounds").fill(String(maxRounds));
  // Last, because typing in either of the three above re-derives it.
  if (peoplePerAgent !== undefined) {
    await page.locator("#people_per_agent").fill(String(peoplePerAgent));
  }

  await page.getByRole("button", { name: "Spiel anlegen" }).click();
  // Not a bare `/app/game/<something>` regex: that also matches the screen we
  // are standing on, so it would resolve before the game was ever made.
  await page.waitForURL(
    (url) =>
      /^\/app\/game\/[^/]+\/?$/.test(url.pathname) &&
      !/\/create\/?$/.test(url.pathname),
  );

  const gameId = new URL(page.url()).pathname.split("/").filter(Boolean).pop();
  expect(gameId).toBeTruthy();
  return gameId!;
}
