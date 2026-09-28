/**
 * The host's own games, and throwing one away. S13.
 *
 * `GET api/game/` is scoped to the logged-in host by the endpoint, not by a
 * parameter — there is no way to ask for somebody else's list. Both counts on a
 * row are annotated server-side, because the page shows every game and
 * `rounds.count()` per row is how a list of twenty-six becomes fifty-three
 * queries.
 *
 * **Deleting invalidates the list rather than patching it.** This is the one
 * screen in the SPA with no socket: nothing broadcasts "a game was deleted",
 * and there is no second source of truth to race with. A refetch after a
 * mutation is the right shape here precisely because the rule it would
 * otherwise break — REST seeds, the socket owns updates — does not apply.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export type HostGameRow = {
  game_id: string;
  game_name: string;
  /** Null is fatal for playing: a mapless game can never be started. */
  game_map: number | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  /** `co2_limit` | `max_rounds` | `host` | `idle`, or null for an old game. */
  end_reason: string | null;
  paused_at: string | null;
  is_active: boolean;
  round_count: number;
  /** Seats that are not the host's own row — students, in other words. */
  player_count: number;
};

export const hostGameKeys = {
  list: () => ["host", "games"] as const,
};

export function useHostGames() {
  return useQuery({
    queryKey: hostGameKeys.list(),
    queryFn: () => apiFetch<HostGameRow[]>("/api/game/"),
    staleTime: 30_000,
  });
}

/**
 * Throw a game away. 409 `running` when it has not been ended yet.
 *
 * The refusal is the endpoint's, not this screen's: ending a game is what
 * writes `end_reason`, and that cannot be worked out afterwards — which is how
 * a game stopped by hand in round 1 of 3 used to report "Alle Runden sind
 * gefahren". The screen reads the reason and says so.
 */
export function useDeleteGame() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (gameId: string) =>
      apiFetch<void>(`/api/game/${gameId}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: hostGameKeys.list() }),
  });
}
