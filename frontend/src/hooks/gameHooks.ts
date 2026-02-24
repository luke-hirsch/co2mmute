import { apiFetch } from "../utils/api";
import { useQuery } from "@tanstack/react-query";

export function useGameDetails(gameId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["gameDetails", gameId],
    queryFn: () => apiFetch(`/api/game/${gameId}/`),
    staleTime: 2000,
    refetchInterval: 2000,
    enabled: enabled && !!gameId,
  });
}

export function usePlayerGameDetails(
  gameId: string,
  playerId: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ["playerGameDetails", gameId, playerId],
    queryFn: () => apiFetch(`/api/game/${gameId}/${playerId}/`),
    staleTime: 2000,
    refetchInterval: 2000,
    enabled: enabled && !!gameId && !!playerId,
  });
}

export function usePlayerDetail(gameId: string, playerId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["playerDetail", gameId, playerId],
    queryFn: () => apiFetch(`/api/game/${gameId}/player/${playerId}/`),
    staleTime: 15000,
    enabled: enabled && !!gameId && !!playerId,
  });
}

export function usePlayerList(gameId: string) {
  useQuery({
    queryKey: ["playerList", gameId],
    queryFn: () => apiFetch(`/api/game/${gameId}/player/`),
    staleTime: 15000,
  });
}

export function useGameSessionList() {
  useQuery({
    queryKey: ["sessions"],
    queryFn: () => apiFetch(`/api/game/sessions/`),
    staleTime: 15000,
  });
}

export interface TrafficEdgeData {
  edge_id: number;
  avg_vehicle_count: number;
  max_vehicle_count: number;
  avg_speed_kmh: number;
  free_flow_speed_kmh: number;
  congestion_ratio: number;
}

interface TrafficHeatmapResponse {
  round_number: number;
  edge_count: number;
  edges: TrafficEdgeData[];
}

export function useRoundTraffic(gameId: string, roundNumber: number | null) {
  return useQuery<TrafficHeatmapResponse>({
    queryKey: ["roundTraffic", gameId, roundNumber],
    queryFn: () => apiFetch(`/api/game/${gameId}/round/${roundNumber}/traffic/`),
    enabled: !!gameId && roundNumber !== null && roundNumber > 0,
    staleTime: Infinity,
  });
}
