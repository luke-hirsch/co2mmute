/**
 * The three join and lobby endpoints, as React Query hooks.
 *
 * Toast-free by convention: these return state, the screens
 * decide what a failure looks like. That matters most for the join, where four
 * different statuses come back with deliberately similar prose and only the
 * screen knows which field to put the message next to.
 *
 * `staleTime: Infinity` on the lobby snapshot is the point of one source of
 * truth, not a tuning knob: the snapshot exists to have something to draw
 * before the socket is up, and the socket owns every update after that. A
 * refetch here would be the second source of truth coming back.
 */

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { JoinBlockedReason } from "@/lib/de";
import type { LobbySnapshot } from "@/lib/game/game-state";

/** What a game says about itself, however it was reached. */
export type GameFacts = {
  game_id: string;
  game_name: string;
  requires_password: boolean;
  joinable: boolean;
  reason: JoinBlockedReason | null;
  player_count: number;
  max_players: number;
  /** The game belongs to a study that hands out participant codes. */
  coded_study?: boolean;
};

/** What a game id opens (`GET api/game/code/<id>/`). */
export type GameLook = GameFacts & { kind: "game" };

/** What a participant code opens: the card's study and the games waiting for it. */
export type ParticipantLook = {
  kind: "participant";
  study_name: string;
  games: GameFacts[];
  /** Why none is on offer: nothing waits, or the card has played what waits. */
  reason: "none_waiting" | "played" | null;
};

/** What a seat code opens: a look, the code not used up. */
export type SeatLook = {
  kind: "seat";
  game_id: string;
  game_name: string;
  player_name: string;
};

/** `GET api/game/code/<code>/` — the first call after a scan or a typed code. */
export type CodeLook = GameLook | SeatLook | ParticipantLook;

/** `POST api/game/code/<game_id>/` — the answer, plus both cookies. */
export type JoinResult = {
  game_id: string;
  game_name: string;
  player_id: string;
  name: string;
  agent_assignments: unknown;
};

export const gameKeys = {
  code: (code: string) => ["code", code] as const,
  lobby: (gameId: string) => ["game", gameId, "lobby"] as const,
};

/**
 * What a code opens. The length says the kind, the backend answers which.
 * Readable without any cookie — it is what the join screen asks before the
 * player has one. Enabled only for a non-empty code so the screen can mount the
 * hook before the field is filled in.
 */
export function useCodeLook(code: string) {
  return useQuery({
    queryKey: gameKeys.code(code),
    queryFn: () => apiFetch<CodeLook>(`/api/game/code/${code}/`),
    enabled: code.length > 0,
    // A game that fills up while the name is being typed should be noticed on
    // submit, not by polling a lookup nobody is looking at. A seat code is
    // asked again each time the screen opens.
    staleTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/**
 * Join a game. With a participant code the post goes to the card's endpoint and
 * names the game; the backend writes the seat's code in the same step.
 */
export function useJoinGame(gameId: string, participantCode?: string) {
  return useMutation({
    mutationFn: (body: { name: string; password?: string }) =>
      apiFetch<JoinResult>(`/api/game/code/${participantCode ?? gameId}/`, {
        method: "POST",
        body: JSON.stringify(
          participantCode ? { ...body, game_id: gameId } : body,
        ),
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
