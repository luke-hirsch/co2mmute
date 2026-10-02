/**
 * The graph of one map version — nodes, edges, PT lines.
 *
 * Exactly what `src/utils/pathfinding.ts` and `ptRouting.ts` take as input.
 * Unchanged from `hooks/mapHooks.ts` apart from the layer it lives in: through
 * `apiFetch` (so failures carry a status), relative (so the vite proxy and
 * nginx both reach it), and without a toast.
 *
 * Without a version the backend serves the base version. In a game there is
 * always one: `GameSession.active_map_version` is set when the game is created
 * and again after every vote — so the graph changes underneath the players when
 * the class has voted a bus lane in.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch, csrfToken } from "@/lib/api";
import type { ExtendedMapGraph } from "@/types/routeTypes";
import type { GameMap, MapVersion, NodeType } from "@/types/mapTypes";

export const mapKeys = {
  graph: (
    mapId: string | number | null,
    versionId: string | number | null,
    traffic: TrafficFor | null = null,
  ) =>
    [
      "map",
      mapId,
      "graph",
      versionId,
      traffic?.gameId ?? null,
      traffic?.roundNumber ?? null,
    ] as const,
};

/**
 * Whose traffic to attach, and as of when.
 *
 * The round is in here because it is in the cache key, not because the endpoint
 * takes it: the backend always serves the *last completed* round's speeds for
 * the game. Without the round the key would never change between rounds and
 * `staleTime: Infinity` would hand round 3 the speeds round 1 drove on.
 */
export type TrafficFor = { gameId: string; roundNumber: number };

/**
 * The traffic for a screen shown *after* a round has been played — the vote and
 * the discussion — named by the round that comes next.
 *
 * Named by the round just played, the key is the one that round's own screen
 * filled while it was still running, so `staleTime: Infinity` hands back the
 * response from before it finished: the round before's speeds, and after round 1
 * none at all. That is how the vote's map lost its jams (F3) while the host's,
 * which has no round screen to fill the cache, kept them. Named by the next
 * round, it is exactly what that round's screen will ask for, so the class
 * routes on the picture it voted over.
 */
export function trafficAfter(gameId: string, playedRound: number): TrafficFor {
  return { gameId, roundNumber: playedRound + 1 };
}

/**
 * @param traffic The game and round whose observed car speeds to attach.
 *
 * `previous_round_traffic` is the join between two halves that were built years
 * apart and never met: `StreetPerRound.speed_under_load` has been written since
 * the beginning and read by nobody, while `PathfindingOptions.trafficData` was
 * threaded all the way through the frontend with nothing ever supplying a value.
 * So "schnellste" was computed on a graph that had never seen a jam — the loop
 * the README describes as routing "unter der Auslastung der letzten Runde" did
 * not exist.
 *
 * The speed is the one the run measured (`EdgeState.mean_speed_kmh`, cars only),
 * not a mean over snapshots. `_update_street_speeds` was changed to write
 * exactly that, for exactly this.
 *
 * The graph itself is identical for every game on a map version and the backend
 * caches it for an hour; the traffic is neither, so the endpoint attaches it
 * outside that cache. React Query caches the whole response though, which is why
 * both the game and the round are in the key. The cost is one graph fetch per
 * round instead of one per version — the backend serves it from its own cache,
 * and correctness beats the round trip.
 */
export function useMapGraph(
  mapId: string | number | null | undefined,
  versionId: string | number | null | undefined,
  traffic?: TrafficFor | null,
) {
  // Both with the trailing slash Django's routes carry. Without it every graph
  // fetch costs an APPEND_SLASH 301 first — harmless, and still two round trips
  // for the biggest payload in the game, on a school wifi.
  const base = versionId
    ? `/api/maps/${mapId}/graph/version/${versionId}/`
    : `/api/maps/${mapId}/graph/baseversion/`;
  const path = traffic
    ? `${base}?game=${encodeURIComponent(traffic.gameId)}`
    : base;

  return useQuery({
    queryKey: mapKeys.graph(mapId ?? null, versionId ?? null, traffic ?? null),
    queryFn: () => apiFetch<ExtendedMapGraph>(path),
    enabled: !!mapId,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

// ── the rest of the map's reads, moved out of `hooks/mapHooks.ts` (F7) ───────
//
// Same queries, same keys, same shapes — only the layer changed: relative URLs
// through `apiFetch`, so a failure carries its status and nothing depends on
// `window.location`. The keys stay exactly as they were, because
// `lib/queries/map-editor.ts` invalidates them by name after every write.

/** Every map, for a list. */
export function useGameMaps() {
  return useQuery<GameMap[]>({
    queryKey: ["maps"],
    queryFn: () => apiFetch("/api/maps/"),
  });
}

/** One map's row — its name, dimensions, speeds and image placement. */
export function useGameMap(mapId: string | number) {
  return useQuery<GameMap>({
    queryKey: ["map", mapId],
    queryFn: () => apiFetch(`/api/maps/${mapId}/`),
    enabled: !!mapId,
  });
}

/** The node types a node can carry (home, workplace, station, …). */
export function useNodeTypes() {
  return useQuery<NodeType[]>({
    queryKey: ["nodeTypes"],
    queryFn: () => apiFetch("/api/maps/node-types/"),
  });
}

/** Every version of a map — what the class ends up voting between. */
export function useMapVersions(mapId: string | number) {
  return useQuery<MapVersion[]>({
    queryKey: ["mapVersions", mapId],
    queryFn: () => apiFetch(`/api/maps/${mapId}/versions/`),
    enabled: !!mapId,
  });
}

/**
 * A version's own row. Multipart, because a version can carry an image of its
 * own — so this one cannot go through `apiFetch` either (see the upload in
 * `map-editor.ts` for the same reason).
 */
export function useUpdateMapVersion(mapId: string | number, versionId: number) {
  const qc = useQueryClient();
  return useMutation<MapVersion, Error, FormData>({
    mutationFn: async (body: FormData) => {
      const res = await fetch(`/api/maps/${mapId}/versions/${versionId}/`, {
        method: "PATCH",
        credentials: "include",
        headers: { "X-CSRFToken": csrfToken() },
        body,
      });
      if (!res.ok) {
        throw new ApiError(res.status, await res.json().catch(() => null), "Version");
      }
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mapVersions", mapId] }),
  });
}

/**
 * Build the combinations of a set of atomic versions.
 *
 * This is what wires `compatible_versions` up, and without it the ballot has
 * nothing to offer: `vote_options()` walks that M2M from the active version.
 */
export function useGenerateCombinations(mapId: string | number) {
  const qc = useQueryClient();
  return useMutation<{ created: number }, Error, { version_ids: number[] }>({
    mutationFn: (data) =>
      apiFetch(`/api/maps/${mapId}/versions/generate-combinations/`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mapVersions", mapId] }),
  });
}
