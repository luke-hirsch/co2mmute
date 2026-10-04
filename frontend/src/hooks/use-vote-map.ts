import { useMemo } from "react";

import { useGame } from "@/components/game/game-context";
import { edgeLoads } from "@/lib/map/traffic";
import { trafficAfter, useMapGraph } from "@/lib/queries/map-graph";
import { useSeatGame } from "@/lib/queries/seat";
import { useHostGame } from "@/lib/queries/session";

/**
 * The map to show while the class votes (S24): the version the game is on, with
 * the round that has just been played drawn on it.
 *
 * It asks for exactly what the next round's screen will ask for — same version,
 * same game, the *next* round in the key (`trafficAfter`) — so what the class
 * looks at while deciding is the picture they will route on, jam and all.
 * `currentRound` is still the round that was played until `round.started`, and
 * the backend serves the last completed round's speeds whatever round the client
 * names (`map-graph.ts`). Keyed by `currentRound` itself, it read back the round
 * screen's own cache entry, fetched before that round had finished.
 *
 * **The map's id has two sources** because only a seat knows it from its own
 * endpoint and the host has no seat; the host's game row has it. Both are read
 * once and kept, like everywhere else.
 */
export function useVoteMap() {
  const { state, seatId, isHost } = useGame();
  const seat = useSeatGame(state.gameId, seatId);
  const host = useHostGame(state.gameId, isHost);

  const mapId = seat.data?.game_map ?? host.data?.game_map;
  const graph = useMapGraph(
    mapId,
    state.activeMapVersionId ?? seat.data?.active_map_version,
    trafficAfter(state.gameId, state.currentRound),
  );

  const jam = useMemo(
    () =>
      edgeLoads(graph.data?.edges ?? [], graph.data?.previous_round_traffic),
    [graph.data],
  );

  return { graph: graph.data ?? null, jam, isLoading: graph.isLoading, mapId };
}
