/**
 * `GET api/game/<game_id>/summary/` — everything the game did, per player, per
 * round. `game/views_rest.py:GameSummaryView`.
 *
 * The one request the end screen makes, and the only one in the SPA that reads
 * across all the rounds of a game: the reducer knows the last round and nothing
 * before it, because that is all the socket ever sent.
 *
 * Read once and never invalidated. The game is over — this is the single screen
 * where the socket genuinely has nothing left to say, and a poll here would be
 * the 2.2 bug turning up on the last screen of the game.
 *
 * `HasGameAccess` lets both halves in: the host through their session, a player
 * through the game cookie. So one hook serves both screens.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { GameEndReason } from "@/lib/game/events";
import type { TransportMode } from "@/lib/de";

/** One round of one player's game. Kilos, euro, minutes. */
export type SummaryRound = {
  round_number: number;
  co2_kg: number;
  cost_eur: number;
  time_min: number;
};

export type SummaryPlayer = {
  player_id: string;
  /**
   * Real until anonymisation runs, 24 h after the end of the game (1.3), which
   * is deliberate — the debrief happens in the lesson and the names go after
   * it. On the screen only: never into a log, a toast or an error string.
   */
  name: string;
  total_co2_kg: number;
  total_cost_eur: number;
  total_time_min: number;
  /** Every mode this player used at least once, over the whole game. */
  modes_used: TransportMode[];
  /**
   * Only the rounds this player actually moved in, so it can be shorter than
   * the game — somebody who joined in round 2 has no round 1 here. Always key
   * on `round_number`, never on the position in the array.
   */
  rounds: SummaryRound[];
};

export type GameSummary = {
  game_id: string;
  game_name: string;
  /**
   * Recomputed by the view from the totals, so an idle-ended game reports
   * `max_rounds` here exactly as it does everywhere else (E-05, open).
   *
   * It is still worth having: `game.state` carries `ended_at` and **no**
   * reason, so after a reload of the end screen the reducer has none and this
   * is the only source left. Prefer the reducer's when it is there — that one
   * came from the live `game.ended` — and fall back to this.
   */
  end_reason: GameEndReason | null;
  rounds_played: number;
  max_rounds: number;
  /**
   * **Kilos here, grams on the socket.** See lib/co2.ts: convert at the edge,
   * and never do arithmetic on a number whose unit is not in its name.
   */
  total_co2_kg: number;
  max_co2_kg: number;
  /**
   * `Player.objects.filter(game=…).playing()` — so a player who left mid-game
   * is not in here, while their emissions stay in `total_co2_kg`. The two do
   * not have to add up; the total is the authoritative one.
   */
  players: SummaryPlayer[];
};

export const summaryKeys = {
  summary: (gameId: string) => ["game", gameId, "summary"] as const,
};

export function fetchSummary(gameId: string): Promise<GameSummary> {
  return apiFetch<GameSummary>(`/api/game/${gameId}/summary/`);
}

export function useGameSummary(gameId: string, enabled: boolean) {
  return useQuery({
    queryKey: summaryKeys.summary(gameId),
    queryFn: () => fetchSummary(gameId),
    enabled: enabled && gameId.length > 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
