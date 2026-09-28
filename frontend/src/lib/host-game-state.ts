/**
 * What the host's game list says a game is doing, in one word.
 *
 * Pure, and in `lib/` rather than beside the screen, because the order of the
 * branches is the whole rule and it is not the obvious one:
 * `GameSession.save()` forces `is_active` back to False for an **ended** game
 * *and* for one with **no map**, so the flag alone cannot tell a finished game
 * from a broken one.
 *
 * The broken one is the case the list exists for. A game created over the REST
 * API or in the admin without a map can never be started, never be ended, and
 * before the per-game delete it had no way out of the page at all.
 */

import { de } from "@/lib/de";
import type { HostGameRow } from "@/lib/queries/host-games";

export function hostGameState(game: HostGameRow): string {
  if (game.ended_at) return de.hostHome.over;
  if (game.paused_at) return de.hostHome.paused;
  if (game.is_active) return de.hostHome.running;
  if (game.game_map === null) return de.hostHome.noMap;
  return de.hostHome.notStarted;
}
