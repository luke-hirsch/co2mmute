/**
 * `GET api/game/<game_id>/round/<n>/replay/` — one finished round, recorded.
 *
 * The biggest payload in the game, and the only one that is worth a fetch of its
 * own: `round.completed` carries the numbers, and nothing over the socket carries
 * the trajectories. It is not game state — it describes a round that is over and
 * can never change — so there is no reducer, no event and nothing to invalidate.
 *
 * Read once and kept (`staleTime: Infinity`). A round's recording is immutable by
 * construction.
 *
 * `HasGameAccess` lets both halves in, the host through their session and a player
 * through the game cookie, so one hook serves the player's stats screen and the
 * host's.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { ReplayPayload } from "@/lib/replay/types";

export const replayKeys = {
  round: (gameId: string, roundNumber: number) =>
    ["game", gameId, "round", roundNumber, "replay"] as const,
};

export function useRoundReplay(gameId: string, roundNumber: number | null) {
  return useQuery({
    queryKey: replayKeys.round(gameId, roundNumber ?? 0),
    queryFn: () =>
      apiFetch<ReplayPayload>(
        `/api/game/${gameId}/round/${roundNumber}/replay/`,
      ),
    enabled: gameId.length > 0 && roundNumber !== null && roundNumber > 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
