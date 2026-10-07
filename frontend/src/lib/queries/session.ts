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
  /**
   * Null is allowed (`game_map` is `null=True, blank=True`) and it is fatal:
   * `GameSession.save()` forces `is_active` back to False when there is no map,
   * so such a game answers a start with 200 and stays in the lobby for ever.
   */
  game_map: number | null;
  max_players: number;
  /**
   * How many real people one Gruppe stands for — derived from the class size
   * when the game is created (`game/calibration.py`). Here because the host has
   * no seat, and the seat endpoint is the only other place it is served.
   */
  people_per_agent: number;
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

/**
 * Switch the chat on or off (F3). Like the rest of this file it reports nothing
 * back: `game.chat` arrives over the socket, for this screen and every phone.
 */
export function useSetChat(gameId: string) {
  return useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch<HostGame>(`/api/game/${gameId}/`, {
        method: "PATCH",
        body: JSON.stringify({ chat_enabled: enabled }),
      }),
  });
}

/** The bell. 409 `paused` / `not_running` when there is nothing to pause. */
export function usePauseGame(gameId: string) {
  return useMutation({ mutationFn: () => pauseGame(gameId) });
}

export function useResumeGame(gameId: string) {
  return useMutation({ mutationFn: () => resumeGame(gameId) });
}

/**
 * What `POST api/game/` takes. S13.
 *
 * Every field the Django form had, minus `lobby_open`: that one was collected,
 * validated and thrown away — `GameSession` has no such column and nothing
 * anywhere read it — so carrying it across would have been carrying a promise
 * the app does not keep. Plus `chat_enabled`, which the Django form never had:
 * the model defaulted it on and no screen could switch it off until S21.
 *
 * `people_per_agent` and `max_CO2_level` are derived by `lib/calibration.ts`
 * as the host changes the class size, the round count, the dial or the map.
 * The scale is an ordinary field from there on: the endpoint takes whatever it
 * is sent, so a host who types over it keeps their own number. The budget
 * follows `co2_kg_per_person`, the dial, which the game records (F8 step 2b).
 */
export type CreateGameBody = {
  game_name: string;
  game_password: string;
  game_map: number;
  map_updates: boolean;
  max_players: number;
  agent_per_player: number;
  max_rounds: number;
  max_CO2_level: number;
  co2_kg_per_person: string;
  people_per_agent: number;
  idle_end_days: number;
  chat_enabled: boolean;
};

/**
 * Make a game and take its host to it.
 *
 * The response carries the new `game_id`, and the two signed cookies ride on
 * the same response — the host is a Django session *and* a player row in their
 * own game, and `HasGameAccess` asks for the cookies rather than the session.
 * Nothing here has to do anything about them; they are set by the browser.
 */
export function useCreateGame() {
  return useMutation({
    mutationFn: (body: CreateGameBody) =>
      apiFetch<HostGame>("/api/game/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}
