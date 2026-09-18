/**
 * The controls only the host has: start, end, pause, resume — and the one read
 * that needs a host session, the game row with its join QR.
 *
 * Starting a game is `PATCH api/game/<id>/ {"is_active": true}`
 * (`GameSessionDetailView.update`), which also creates round 1 and pins the
 * base map version. It is not a `/start/` endpoint, which is worth saying
 * because it does not look like one.
 *
 * **This is what went missing in F3.** `currentScreen()` sends a host who has
 * not started yet to the lobby, and since F3 the lobby is the player's lobby —
 * which has no start button, because players do not need one. The old screen
 * that had it only runs between rounds now. So for one chunk a game could not
 * be started from the browser at all.
 *
 * Like everywhere else: no invalidation afterwards. `game.started`,
 * `game.paused`, `game.resumed` and `game.ended` all arrive over the socket and
 * the reducer applies them.
 */

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

/**
 * The slice of `GameSessionSerializer` the host screens use. The whole row is
 * bigger; naming only this much keeps it obvious what a host screen may show.
 */
export type HostGame = {
  game_id: string;
  game_name: string;
  /** Media URL of the join QR. `GameSession.generate_qr_code()`. */
  game_qr_code: string | null;
  game_password: string | null;
  max_players: number;
  is_active: boolean;
  started_at: string | null;
  paused_at: string | null;
  ended_at: string | null;
};

export const sessionKeys = {
  game: (gameId: string) => ["game", gameId, "session"] as const,
};

/**
 * The game row, for the host only — `GameSessionDetailView` requires a logged-in
 * user. Read once: everything on it that moves during a game moves over the
 * socket instead.
 */
export function useHostGame(gameId: string, enabled: boolean) {
  return useQuery({
    queryKey: sessionKeys.game(gameId),
    queryFn: () => apiFetch<HostGame>(`/api/game/${gameId}/`),
    enabled: enabled && gameId.length > 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function setGameActive(gameId: string, active: boolean): Promise<HostGame> {
  return apiFetch<HostGame>(`/api/game/${gameId}/`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: active }),
  });
}

export function pauseGame(gameId: string): Promise<{ paused_at: string }> {
  return apiFetch(`/api/game/${gameId}/pause/`, { method: "POST" });
}

export function resumeGame(gameId: string): Promise<{ paused_at: null }> {
  return apiFetch(`/api/game/${gameId}/resume/`, { method: "POST" });
}

export function useStartGame(gameId: string) {
  return useMutation({ mutationFn: () => setGameActive(gameId, true) });
}

export function useEndGame(gameId: string) {
  return useMutation({ mutationFn: () => setGameActive(gameId, false) });
}

/** The bell. 409 `paused` / `not_running` when there is nothing to pause. */
export function usePauseGame(gameId: string) {
  return useMutation({ mutationFn: () => pauseGame(gameId) });
}

export function useResumeGame(gameId: string) {
  return useMutation({ mutationFn: () => resumeGame(gameId) });
}
