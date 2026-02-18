import { useMutation, useQueryClient } from "@tanstack/react-query";
import { API_BASE_URL } from "../config";
import { apiFetch, csrf } from "../utils/api";
import type { ImageTransformValues, VersionDiffPayload } from "../types/editorTypes";

export const useUploadBackgroundImage = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("image", file);
      const res = await fetch(
        `${API_BASE_URL}/api/maps/${mapId}/background-image/`,
        {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRFToken": csrf() },
          body: formData,
        }
      );
      if (!res.ok) throw new Error("Failed to upload image");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["map", mapId] });
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useDeleteBackgroundImage = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(
        `${API_BASE_URL}/api/maps/${mapId}/background-image/`,
        {
          method: "DELETE",
          credentials: "include",
          headers: { "X-CSRFToken": csrf() },
        }
      );
      if (!res.ok) throw new Error("Failed to delete image");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["map", mapId] });
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateImageTransform = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (values: ImageTransformValues) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/`, {
        method: "PATCH",
        body: JSON.stringify(values),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["map", mapId] });
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateNodePosition = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      nodeId,
      x_position,
      y_position,
    }: {
      nodeId: number;
      x_position: number;
      y_position: number;
    }) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/nodes/${nodeId}/`,
        {
          method: "PATCH",
          body: JSON.stringify({ x_position, y_position }),
        }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

// --- Node CRUD ---

export const useCreateNode = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name?: string;
      x_position: number;
      y_position: number;
      node_type?: number[];
      map_versions?: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/nodes/`, {
        method: "POST",
        body: JSON.stringify({ game_map: mapId, ...data }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateNode = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      nodeId,
      ...data
    }: {
      nodeId: number;
      name?: string;
      node_type?: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/nodes/${nodeId}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useDeleteNode = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (nodeId: number) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/nodes/${nodeId}/`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

// --- Edge CRUD ---

export const useCreateEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      start_node: number;
      end_node: number;
      biking?: boolean;
      walking?: boolean;
      max_lanes?: number;
      map_versions?: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/edges/`, {
        method: "POST",
        body: JSON.stringify({ game_map: mapId, ...data }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      edgeId,
      ...data
    }: {
      edgeId: number;
      biking?: boolean;
      walking?: boolean;
      max_lanes?: number;
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/edges/${edgeId}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useDeleteEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (edgeId: number) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/edges/${edgeId}/`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

// --- StreetEdge / TrainEdge ---

export const useCreateStreetEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      edge: number;
      speed_limit?: number;
      lanes?: number;
      dedicated_bus_lane?: boolean;
      map_versions?: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/street-edges/`, {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useDeleteStreetEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (streetEdgeId: number) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/street-edges/${streetEdgeId}/`,
        { method: "DELETE" }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useCreateTrainEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      edge: number;
      map_versions?: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/train-edges/`, {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useDeleteTrainEdge = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (trainEdgeId: number) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/train-edges/${trainEdgeId}/`,
        { method: "DELETE" }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

// --- PT Line Update ---

export const useUpdateBusLine = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lineId,
      ...data
    }: {
      lineId: number;
      name?: string;
      intervall?: number;
      bus_capacity?: number;
      bus_speed_kmh?: number;
    }) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/bus-lines/${lineId}/`,
        { method: "PATCH", body: JSON.stringify(data) }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateTrainLine = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lineId,
      ...data
    }: {
      lineId: number;
      name?: string;
      intervall?: number;
      train_capacity?: number;
      train_speed_kmh?: number;
    }) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/train-lines/${lineId}/`,
        { method: "PATCH", body: JSON.stringify(data) }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateBusLineEdges = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lineId,
      edges,
    }: {
      lineId: number;
      edges: number[];
    }) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/bus-lines/${lineId}/edges/`,
        { method: "PUT", body: JSON.stringify({ edges }) }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useUpdateTrainLineEdges = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lineId,
      edges,
    }: {
      lineId: number;
      edges: number[];
    }) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/train-lines/${lineId}/edges/`,
        { method: "PUT", body: JSON.stringify({ edges }) }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

// --- Version Diff ---

export const useCreateVersionFromDiff = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: VersionDiffPayload) => {
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/versions/create-from-diff/`,
        { method: "POST", body: JSON.stringify(payload) }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapVersions", mapId] });
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useCreateBusLine = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      intervall: number;
      bus_capacity: number;
      bus_speed_kmh: number;
      edges: number[];
      map_versions: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/bus-lines/`, {
        method: "POST",
        body: JSON.stringify({ game_map: mapId, ...data }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useCreateTrainLine = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      intervall: number;
      train_capacity: number;
      train_speed_kmh: number;
      edges: number[];
      map_versions: number[];
    }) => {
      return apiFetch(`${API_BASE_URL}/api/maps/${mapId}/train-lines/`, {
        method: "POST",
        body: JSON.stringify({ game_map: mapId, ...data }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};

export const useDeletePTLine = (mapId: string | number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lineId,
      lineType,
    }: {
      lineId: number;
      lineType: "bus" | "train";
    }) => {
      const endpoint =
        lineType === "bus" ? "bus-lines" : "train-lines";
      return apiFetch(
        `${API_BASE_URL}/api/maps/${mapId}/${endpoint}/${lineId}/`,
        { method: "DELETE" }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
    },
  });
};
