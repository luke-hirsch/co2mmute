/**
 * The three 1.4 endpoints, as React Query hooks.
 *
 * Toast-free by convention (Roadmap.md 2.1): these return state, the screens
 * decide what a failure looks like. That matters most for the join, where four
 * different statuses come back with deliberately similar prose and only the
 * screen knows which field to put the message next to.
 *
 * `staleTime: Infinity` on the lobby snapshot is the point of 2.2, not a
 * tuning knob: the snapshot exists to have something to draw before the socket
 * is up, and the socket owns every update after that. A refetch here would be
 * the second source of truth coming back.
 */

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { JoinBlockedReason } from "@/lib/de";
import type { LobbySnapshot } from "@/lib/game/game-state";

/** `GET api/game/lookup/<game_id>/` — the first call after a QR scan. */
export type SessionLookup = {
  game_id: string;
  game_name: string;
  requires_password: boolean;
  joinable: boolean;
  reason: JoinBlockedReason | null;
  player_count: number;
  max_players: number;
};

/** `POST api/game/join/<game_id>/` — the answer, plus both cookies. */
export type JoinResult = {
  game_id: string;
  game_name: string;
  player_id: string;
  name: string;
  agent_assignments: unknown;
};

export const gameKeys = {
  lookup: (gameId: string) => ["game", gameId, "lookup"] as const,
  lobby: (gameId: string) => ["game", gameId, "lobby"] as const,
};

/**
 * Readable without any cookie — it is what the join screen asks before the
 * player has one. Enabled only for a non-empty id so the screen can mount the
 * hook before the field is filled in.
 */
export function useSessionLookup(gameId: string) {
  return useQuery({
    queryKey: gameKeys.lookup(gameId),
    queryFn: () => apiFetch<SessionLookup>(`/api/game/lookup/${gameId}/`),
    enabled: gameId.length > 0,
    // A game that fills up while the name is being typed should be noticed on
    // submit, not by polling a lookup nobody is looking at.
    staleTime: 30_000,
    retry: false,
  });
}

export function useJoinGame(gameId: string) {
  return useMutation({
    mutationFn: (body: { name: string; password?: string }) =>
      apiFetch<JoinResult>(`/api/game/join/${gameId}/`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

/**
 * The lobby snapshot. Needs the game cookie, which the join above just set.
 *
 * Read once and then left alone: no `refetchInterval`, and nothing calls
 * `refetch()` from a socket callback. If this ever grows one, the bug it
 * causes will look like a state bug somewhere else entirely — that is the
 * history this whole layer is a reaction to.
 */
export function useLobbySnapshot(gameId: string, enabled = true) {
  return useQuery({
    queryKey: gameKeys.lobby(gameId),
    queryFn: () => apiFetch<LobbySnapshot>(`/api/game/${gameId}/lobby/`),
    enabled: enabled && gameId.length > 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
