/**
 * Everything the map editor writes.
 *
 * Moved out of `hooks/mapEditorHooks.ts` (F7) with **every URL, method and
 * payload preserved exactly**. That is not politeness about a refactor: these
 * are the only calls in the app that change a real map, and maps take real work
 * to build (Lukas, 2026-09-18 — "creating those maps take time"). The port is
 * allowed to move this code and rename it; it is not allowed to change what
 * goes over the wire. `tests/lib/queries/map-editor.test.ts` pins that.
 *
 * What did change, and why it is safe:
 *
 * - **`API_BASE_URL` is gone.** It resolved to `window.location.protocol + host`
 *   — the same origin the relative path already targets — so the request is
 *   byte-for-byte the same one, and it now works in a test with no `window`.
 * - **Everything goes through `apiFetch`**, which sets the CSRF header and the
 *   JSON content type itself and throws an `ApiError` carrying the status. The
 *   two hand-rolled `fetch` calls (the image upload and delete) threw
 *   `new Error("Failed to upload image")`, which told the screen nothing.
 * - **No toasts.** `lib/queries/` is toast-free; the screen decides.
 *
 * The split is the same one `lib/queries/seats.ts` uses: a plain async function
 * per call, and a thin hook that wraps it with its invalidations. The plain half
 * is what the tests can reach without a React renderer — vitest runs in a node
 * env here, with no jsdom.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { csrfToken } from "@/lib/api";
import type { ImageTransformValues, VersionDiffPayload } from "@/types/editorTypes";

type MapId = string | number;

export const mapEditorKeys = {
  /**
   * `["map", <id>]` is a **prefix** of the graph's own key
   * (`mapKeys.graph` in `map-graph.ts` is `["map", id, "graph", version]`), and
   * React Query invalidates by prefix — so this one call reaches the map row
   * and every version's graph with it.
   *
   * Worth spelling out because it was nearly a silent bug: these hooks used to
   * invalidate `["mapGraph", <id>]`, which was the old `hooks/mapHooks.ts` key.
   * Pointing the editor at the newer graph hook without fixing this would have
   * left every write saved on the server and invisible on screen until a
   * reload — the editor would look like it had stopped saving.
   */
  map: (mapId: MapId) => ["map", mapId] as const,
  graph: (mapId: MapId) => ["map", mapId] as const,
  versions: (mapId: MapId) => ["mapVersions", mapId] as const,
};

const base = (mapId: MapId) => `/api/maps/${mapId}`;

// ── the background image ────────────────────────────────────────────────────

/**
 * Multipart, so it cannot go through `apiFetch` — that one sets a JSON content
 * type and a body must not carry its own boundary past it. The CSRF header is
 * therefore set by hand here, the one place it still is.
 */
export async function uploadBackgroundImage(mapId: MapId, file: File) {
  const body = new FormData();
  body.append("image", file);

  const res = await fetch(`${base(mapId)}/background-image/`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRFToken": csrfToken() },
    body,
  });
  if (!res.ok) throw new Error(`Upload failed (${res.status})`);
  return res.json();
}

export function deleteBackgroundImage(mapId: MapId) {
  return apiFetch(`${base(mapId)}/background-image/`, { method: "DELETE" });
}

/** Where the image sits against the graph: offsets, scale, crops. */
export function updateImageTransform(mapId: MapId, values: ImageTransformValues) {
  return apiFetch(`${base(mapId)}/`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });
}

// ── the map row ─────────────────────────────────────────────────────────────

export function updateMapSettings(mapId: MapId, data: object) {
  return apiFetch(`${base(mapId)}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ── nodes ───────────────────────────────────────────────────────────────────

export type NodeInput = {
  name?: string;
  x_position: number;
  y_position: number;
  node_type?: number[];
  map_versions?: number[];
};

/**
 * The drag. This is the call the whole "don't touch the editing path" rule is
 * about: `EditorCanvas` resolves a drag to `x_position + dx / 100` and this
 * sends it. Position only — a drag must never carry the rest of the node with
 * it, or a concurrent rename is overwritten by whatever the canvas last saw.
 */
export function updateNodePosition(
  mapId: MapId,
  nodeId: number,
  x_position: number,
  y_position: number,
) {
  return apiFetch(`${base(mapId)}/nodes/${nodeId}/`, {
    method: "PATCH",
    body: JSON.stringify({ x_position, y_position }),
  });
}

export function createNode(mapId: MapId, data: NodeInput) {
  return apiFetch<{ id: number }>(`${base(mapId)}/nodes/`, {
    method: "POST",
    body: JSON.stringify({ game_map: mapId, ...data }),
  });
}

export function updateNode(mapId: MapId, nodeId: number, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/nodes/${nodeId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteNode(mapId: MapId, nodeId: number) {
  return apiFetch(`${base(mapId)}/nodes/${nodeId}/`, { method: "DELETE" });
}

// ── edges, and the two kinds that hang off them ─────────────────────────────

export type EdgeInput = {
  start_node: number;
  end_node: number;
  biking?: boolean;
  walking?: boolean;
  max_lanes?: number;
  map_versions?: number[];
  bidirectional?: boolean;
};

/** DRF answers a create with the serialised row, so the new id comes back. */
export function createEdge(mapId: MapId, data: EdgeInput) {
  return apiFetch<{ id: number }>(`${base(mapId)}/edges/`, {
    method: "POST",
    body: JSON.stringify({ game_map: mapId, ...data }),
  });
}

export function updateEdge(mapId: MapId, edgeId: number, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/edges/${edgeId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteEdge(mapId: MapId, edgeId: number) {
  return apiFetch(`${base(mapId)}/edges/${edgeId}/`, { method: "DELETE" });
}

export function createStreetEdge(mapId: MapId, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/street-edges/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateStreetEdge(
  mapId: MapId,
  streetEdgeId: number,
  data: Record<string, unknown>,
) {
  return apiFetch(`${base(mapId)}/street-edges/${streetEdgeId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteStreetEdge(mapId: MapId, streetEdgeId: number) {
  return apiFetch(`${base(mapId)}/street-edges/${streetEdgeId}/`, { method: "DELETE" });
}

export function createTrainEdge(mapId: MapId, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/train-edges/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteTrainEdge(mapId: MapId, trainEdgeId: number) {
  return apiFetch(`${base(mapId)}/train-edges/${trainEdgeId}/`, { method: "DELETE" });
}

// ── public transport lines ──────────────────────────────────────────────────

export type PTLineType = "bus" | "train";

/** `bus` and `train` differ only in their path and their capacity field. */
const lineSegment: Record<PTLineType, string> = {
  bus: "bus-lines",
  train: "train-lines",
};

export function createBusLine(mapId: MapId, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/bus-lines/`, {
    method: "POST",
    body: JSON.stringify({ game_map: mapId, ...data }),
  });
}

export function createTrainLine(mapId: MapId, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/train-lines/`, {
    method: "POST",
    body: JSON.stringify({ game_map: mapId, ...data }),
  });
}

export function updateBusLine(mapId: MapId, lineId: number, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/bus-lines/${lineId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function updateTrainLine(mapId: MapId, lineId: number, data: Record<string, unknown>) {
  return apiFetch(`${base(mapId)}/train-lines/${lineId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** The whole edge list of a line, replaced — hence PUT rather than PATCH. */
export function updateBusLineEdges(mapId: MapId, lineId: number, edges: number[]) {
  return apiFetch(`${base(mapId)}/bus-lines/${lineId}/edges/`, {
    method: "PUT",
    body: JSON.stringify({ edges }),
  });
}

export function updateTrainLineEdges(mapId: MapId, lineId: number, edges: number[]) {
  return apiFetch(`${base(mapId)}/train-lines/${lineId}/edges/`, {
    method: "PUT",
    body: JSON.stringify({ edges }),
  });
}

export function deletePTLine(mapId: MapId, lineId: number, lineType: PTLineType) {
  return apiFetch(`${base(mapId)}/${lineSegment[lineType]}/${lineId}/`, {
    method: "DELETE",
  });
}

// ── versions ────────────────────────────────────────────────────────────────

/**
 * A new version described as a diff against an existing one — which is how a
 * map version works at all: nodes, edges and lines carry `map_versions`, so a
 * version is a filter over one shared graph rather than a copy of it.
 */
export function createVersionFromDiff(mapId: MapId, payload: VersionDiffPayload) {
  return apiFetch(`${base(mapId)}/versions/create-from-diff/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── hooks ───────────────────────────────────────────────────────────────────
// Thin wrappers. Each keeps exactly the invalidations its hook had before.

function useMapMutation<TArgs = void, TData = unknown>(
  mapId: MapId,
  fn: (args: TArgs) => Promise<TData>,
  invalidate: (mapId: MapId) => readonly (readonly unknown[])[],
) {
  const qc = useQueryClient();
  // Generic in both directions on purpose: the callers type their own
  // `onSuccess` against what the endpoint returns (a created edge's id, say),
  // and the ones that take no argument have to stay callable as `mutate()`.
  return useMutation<TData, Error, TArgs>({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of invalidate(mapId)) {
        qc.invalidateQueries({ queryKey: key });
      }
    },
  });
}

const graphOnly = (mapId: MapId) => [mapEditorKeys.graph(mapId)] as const;
const mapAndGraph = (mapId: MapId) =>
  [mapEditorKeys.map(mapId), mapEditorKeys.graph(mapId)] as const;

export const useUploadBackgroundImage = (mapId: MapId) =>
  useMapMutation(mapId, (file: File) => uploadBackgroundImage(mapId, file), mapAndGraph);

export const useDeleteBackgroundImage = (mapId: MapId) =>
  useMapMutation(mapId, () => deleteBackgroundImage(mapId), mapAndGraph);

export const useUpdateImageTransform = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (values: ImageTransformValues) => updateImageTransform(mapId, values),
    mapAndGraph,
  );

export const useUpdateMapSettings = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (data: object) => updateMapSettings(mapId, data),
    mapAndGraph,
  );

export const useUpdateNodePosition = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ nodeId, x_position, y_position }: { nodeId: number; x_position: number; y_position: number }) =>
      updateNodePosition(mapId, nodeId, x_position, y_position),
    graphOnly,
  );

export const useCreateNode = (mapId: MapId) =>
  useMapMutation(mapId, (data: NodeInput) => createNode(mapId, data), graphOnly);

export const useUpdateNode = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ nodeId, ...data }: { nodeId: number } & Record<string, unknown>) =>
      updateNode(mapId, nodeId, data),
    graphOnly,
  );

export const useDeleteNode = (mapId: MapId) =>
  useMapMutation(mapId, (nodeId: number) => deleteNode(mapId, nodeId), graphOnly);

export const useCreateEdge = (mapId: MapId) =>
  useMapMutation(mapId, (data: EdgeInput) => createEdge(mapId, data), graphOnly);

export const useUpdateEdge = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ edgeId, ...data }: { edgeId: number } & Record<string, unknown>) =>
      updateEdge(mapId, edgeId, data),
    graphOnly,
  );

export const useDeleteEdge = (mapId: MapId) =>
  useMapMutation(mapId, (edgeId: number) => deleteEdge(mapId, edgeId), graphOnly);

export const useCreateStreetEdge = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (data: Record<string, unknown>) => createStreetEdge(mapId, data),
    graphOnly,
  );

export const useUpdateStreetEdge = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ streetEdgeId, ...data }: { streetEdgeId: number } & Record<string, unknown>) =>
      updateStreetEdge(mapId, streetEdgeId, data),
    graphOnly,
  );

export const useDeleteStreetEdge = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (streetEdgeId: number) => deleteStreetEdge(mapId, streetEdgeId),
    graphOnly,
  );

export const useCreateTrainEdge = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (data: Record<string, unknown>) => createTrainEdge(mapId, data),
    graphOnly,
  );

export const useDeleteTrainEdge = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (trainEdgeId: number) => deleteTrainEdge(mapId, trainEdgeId),
    graphOnly,
  );

export const useCreateBusLine = (mapId: MapId) =>
  useMapMutation(mapId, (data: Record<string, unknown>) => createBusLine(mapId, data), graphOnly);

export const useCreateTrainLine = (mapId: MapId) =>
  useMapMutation(mapId, (data: Record<string, unknown>) => createTrainLine(mapId, data), graphOnly);

export const useUpdateBusLine = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ lineId, ...data }: { lineId: number } & Record<string, unknown>) =>
      updateBusLine(mapId, lineId, data),
    graphOnly,
  );

export const useUpdateTrainLine = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ lineId, ...data }: { lineId: number } & Record<string, unknown>) =>
      updateTrainLine(mapId, lineId, data),
    graphOnly,
  );

export const useUpdateBusLineEdges = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ lineId, edges }: { lineId: number; edges: number[] }) =>
      updateBusLineEdges(mapId, lineId, edges),
    graphOnly,
  );

export const useUpdateTrainLineEdges = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ lineId, edges }: { lineId: number; edges: number[] }) =>
      updateTrainLineEdges(mapId, lineId, edges),
    graphOnly,
  );

export const useDeletePTLine = (mapId: MapId) =>
  useMapMutation(
    mapId,
    ({ lineId, lineType }: { lineId: number; lineType: PTLineType }) =>
      deletePTLine(mapId, lineId, lineType),
    graphOnly,
  );

export const useCreateVersionFromDiff = (mapId: MapId) =>
  useMapMutation(
    mapId,
    (payload: VersionDiffPayload) => createVersionFromDiff(mapId, payload),
    (id) => [mapEditorKeys.versions(id), mapEditorKeys.graph(id)] as const,
  );
