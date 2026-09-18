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
  graph: (mapId: string | number | null, versionId: string | number | null) =>
    ["map", mapId, "graph", versionId] as const,
};

export function useMapGraph(
  mapId: string | number | null | undefined,
  versionId: string | number | null | undefined,
) {
  // Both with the trailing slash Django's routes carry. Without it every graph
  // fetch costs an APPEND_SLASH 301 first — harmless, and still two round trips
  // for the biggest payload in the game, on a school wifi.
  const path = versionId
    ? `/api/maps/${mapId}/graph/version/${versionId}/`
    : `/api/maps/${mapId}/graph/baseversion/`;

  return useQuery({
    queryKey: mapKeys.graph(mapId ?? null, versionId ?? null),
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
