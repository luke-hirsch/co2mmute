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

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { ExtendedMapGraph } from "@/types/routeTypes";

export const mapKeys = {
  graph: (mapId: number | null, versionId: number | null) =>
    ["map", mapId, "graph", versionId] as const,
};

export function useMapGraph(
  mapId: number | null | undefined,
  versionId: number | null | undefined,
) {
  const path = versionId
    ? `/api/maps/${mapId}/graph/version/${versionId}`
    : `/api/maps/${mapId}/graph/baseversion/`;

  return useQuery({
    queryKey: mapKeys.graph(mapId ?? null, versionId ?? null),
    queryFn: () => apiFetch<ExtendedMapGraph>(path),
    enabled: !!mapId,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
