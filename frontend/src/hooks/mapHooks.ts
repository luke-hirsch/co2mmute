import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_BASE_URL } from "../config";
import { apiFetch, csrf } from "../utils/api";
import type { GameMap, MapVersion, NodeType } from "../types/mapTypes";
import type { ExtendedMapGraph } from "../types/routeTypes";

/**
 * Fetch all game maps
 */
export const useGameMaps = () => {
  return useQuery<GameMap[]>({
    queryKey: ["maps"],
    queryFn: async () => {
      return apiFetch(`${API_BASE_URL}/api/maps/`);
    },
  });
};

/**
 * Fetch a specific game map
 */
export const useGameMap = (mapId: string | number) => {
  return useQuery<GameMap>({
    queryKey: ["map", mapId],
    queryFn: async () => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/`);
    },
    enabled: !!mapId,
  });
};

/**
 * Fetch the complete graph for a specific map version
 * Returns nodes and edges ready for visualization
 */
export const useMapGraph = (
  mapId: string | number,
  versionId?: string | number
) => {
  // If no versionId is provided, we'll get the base version
  // <int:pk>/graph/version/<int:version_pk>/
  const queryUrl = versionId
    ? `${API_BASE_URL}/api/maps/${mapId}/graph/version/${versionId}`
    : `${API_BASE_URL}/api/maps/${mapId}/graph/baseversion/`;

  return useQuery<ExtendedMapGraph>({
    queryKey: ["mapGraph", mapId, versionId],
    queryFn: async () => {
      return apiFetch(queryUrl);
    },
    enabled: !!mapId,
  });
};

/**
 * Fetch all available node types
 */
export const useNodeTypes = () => {
  return useQuery<NodeType[]>({
    queryKey: ["nodeTypes"],
    queryFn: async () => {
      return apiFetch(`${API_BASE_URL}/api/maps/node-types/`);
    },
  });
};

/**
 * Fetch all map versions for a specific map
 */
export const useMapVersions = (mapId: string | number) => {
  return useQuery<MapVersion[]>({
    queryKey: ["mapVersions", mapId],
    queryFn: async () => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/versions/`);
    },
    enabled: !!mapId,
  });
};

/**
 * PATCH a map version (supports image upload via FormData)
 */
export const useUpdateMapVersion = (mapId: string | number, versionId: number) => {
  const queryClient = useQueryClient();
  return useMutation<MapVersion, Error, FormData>({
    mutationFn: async (formData: FormData) => {
      const response = await fetch(
        `${API_BASE_URL}/api/maps/${mapId}/versions/${versionId}/`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "X-CSRFToken": csrf() },
          body: formData,
        }
      );
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(JSON.stringify(err));
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mapVersions", mapId] });
    },
  });
};

/**
 * POST to generate combination versions from atomic version IDs
 */
export const useGenerateCombinations = (mapId: string | number) => {
  const queryClient = useQueryClient();
  return useMutation<{ created: number }, Error, { version_ids: number[] }>({
    mutationFn: async (data) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/versions/generate-combinations/`, {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mapVersions", mapId] });
    },
  });
};
