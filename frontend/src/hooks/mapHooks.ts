import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "../config";
import { apiFetch } from "../utils/api";
import type { GameMap, MapGraph } from "../types/mapTypes";

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
  const queryUrl = versionId
    ? `${API_BASE_URL}/api/maps/${mapId}/versions/${versionId}/graph/`
    : `${API_BASE_URL}/api/maps/${mapId}/versions/1/graph/`;

  return useQuery<MapGraph>({
    queryKey: ["mapGraph", mapId, versionId],
    queryFn: async () => {
      return apiFetch(queryUrl);
    },
    enabled: !!mapId,
  });
};

/**
 * Fetch all map versions for a specific map
 */
export const useMapVersions = (mapId: string | number) => {
  return useQuery({
    queryKey: ["mapVersions", mapId],
    queryFn: async () => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/versions/`);
    },
    enabled: !!mapId,
  });
};
