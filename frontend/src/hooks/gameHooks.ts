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

export interface PlayerRoundSummary {
  round_number: number;
  co2_kg: number;
  cost_eur: number;
  time_min: number;
}

export interface PlayerSummary {
  player_id: string;
  name: string;
  total_co2_kg: number;
  total_cost_eur: number;
  total_time_min: number;
  modes_used: string[];
  rounds: PlayerRoundSummary[];
}

export interface GameSummaryData {
  game_id: string;
  game_name: string;
  end_reason: "co2_limit" | "max_rounds" | null;
  rounds_played: number;
  max_rounds: number;
  total_co2_kg: number;
  max_co2_kg: number;
  players: PlayerSummary[];
}

export function useGameSummary(gameId: string, enabled: boolean = true) {
  return useQuery<GameSummaryData>({
    queryKey: ["gameSummary", gameId],
    queryFn: () => apiFetch(`/api/game/${gameId}/summary/`),
    enabled: enabled && !!gameId,
    staleTime: Infinity,
  });
}
