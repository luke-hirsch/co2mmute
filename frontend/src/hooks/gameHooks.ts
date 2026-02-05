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
