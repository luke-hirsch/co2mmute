/**
 * Submitting a turn.
 *
 * `POST api/game/<game_id>/player/<player_id>/move/`. The status codes carry
 * meaning, so the `ApiError` flies up with its status and body intact rather
 * than being flattened into a message:
 *
 *   409 + `reason: "paused"`  — the bell rang (1.7, P-03)
 *   400 `No active round`     — the round finished while this was open
 *   400 `error: [...]`        — the route validation found something
 *   403                       — someone else's seat, without a host session
 *
 * No `onSuccess` invalidation: that the move arrived is something the roster
 * says over the socket (`status: "waiting"`), and it says it sooner than any
 * refetch would.
 */

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { RouteSubmissionPayload } from "@/types/routeTypes";

export type MovePayload = RouteSubmissionPayload;

/**
 * The request itself, without React.
 *
 * Split from the hook because vitest runs here without jsdom (CLAUDE.md,
 * frontend target conventions): a function with a stubbed `fetch` is testable,
 * a `useMutation` is not. The hook below is then only wiring.
 */
export function submitMove(
  gameId: string,
  seatId: string,
  payload: MovePayload,
): Promise<unknown> {
  return apiFetch(`/api/game/${gameId}/player/${seatId}/move/`, {
    method: "POST",
    body: JSON.stringify({ action: "route_submission", payload }),
  });
}

export function useSubmitMove(gameId: string, seatId: string | null) {
  return useMutation({
    mutationFn: (payload: MovePayload) => submitMove(gameId, seatId ?? "", payload),
  });
}
