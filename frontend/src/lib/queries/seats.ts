/**
 * Seats: adding one, removing one, moving one to another device.
 *
 * The backend half is 1.6 and 1.7 (`game/seats.py`). Nothing here refetches
 * anything afterwards, and that is deliberate: `add_seat`, `remove_seat` and
 * `take_over` all call `schedule_broadcast`, so the roster arrives over the
 * socket — sooner than a refetch would, and as the same one truth every other
 * screen reads. A mutation's job is to send the request and report the refusal.
 *
 * The refusals are the interesting part, so each request function is pure and
 * throws `ApiError` with its status and `reason` intact:
 *
 *   add      409 `full`, `ended`
 *   takeover 409 `host`, `controlled`, `ended`
 *   code     409 `host`, `ended`
 *   redeem   404 (gone or used), 409 `host`, `seated`, `ended`
 */

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

/** What `POST .../code/` answers. `game/views_rest.py:SeatCodeIssueView`. */
export type IssuedSeatCode = {
  code: string;
  /** Seconds. `game/seats.py:CODE_TTL` — 5 minutes today. */
  expires_in: number;
  /**
   * Where a scannable version of the code lives, once the backend renders one
   * (`[backend]-seat-code-qr.md`). Optional on purpose: this screen shipped
   * before that guide, and a missing QR just means the six characters stand on
   * their own — which is what the alphabet was chosen for.
   */
  qr_url?: string;
};

/** What `GET api/game/seat/<code>/` answers — a look, not a redemption. */
export type SeatCodeLookup = {
  game_id: string;
  game_name: string;
  player_name: string;
};

/** What `POST api/game/seat/<code>/` answers. Both cookies come with it. */
export type RedeemedSeat = {
  game_id: string;
  game_name: string;
  player_id: string;
  name: string;
  agent_assignments: unknown;
};

/** A seat row as the REST endpoints serialise it (`PlayerSerializer`). */
export type SeatRow = {
  player_id: string;
  name: string;
  controlled_by_host: boolean;
};

/**
 * A code as read off a projector or typed on a phone: upper case, no spaces.
 * The backend does the same (`seat_for_code`), but the URL is built here, so
 * it has to happen here too.
 */
function normaliseCode(code: string): string {
  return code.trim().toUpperCase();
}

// ─────────────────────────────────────────────────────────────────────────────
// The requests, without React. Testable with a stubbed fetch.
// ─────────────────────────────────────────────────────────────────────────────

export function addSeat(gameId: string, name: string): Promise<SeatRow> {
  return apiFetch<SeatRow>(`/api/game/${gameId}/player/`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function removeSeat(gameId: string, seatId: string): Promise<unknown> {
  return apiFetch(`/api/game/${gameId}/player/${seatId}/`, { method: "DELETE" });
}

export function takeOverSeat(gameId: string, seatId: string): Promise<SeatRow> {
  return apiFetch<SeatRow>(`/api/game/${gameId}/player/${seatId}/takeover/`, {
    method: "POST",
  });
}

export function issueSeatCode(
  gameId: string,
  seatId: string,
): Promise<IssuedSeatCode> {
  return apiFetch<IssuedSeatCode>(`/api/game/${gameId}/player/${seatId}/code/`, {
    method: "POST",
  });
}

export function lookUpSeatCode(code: string): Promise<SeatCodeLookup> {
  return apiFetch<SeatCodeLookup>(`/api/game/seat/${normaliseCode(code)}/`);
}

export function redeemSeatCode(code: string): Promise<RedeemedSeat> {
  return apiFetch<RedeemedSeat>(`/api/game/seat/${normaliseCode(code)}/`, {
    method: "POST",
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Hooks. Thin wiring, no toasts — the screens decide what a failure looks like.
// ─────────────────────────────────────────────────────────────────────────────

export function useAddSeat(gameId: string) {
  return useMutation({ mutationFn: (name: string) => addSeat(gameId, name) });
}

export function useRemoveSeat(gameId: string) {
  return useMutation({ mutationFn: (seatId: string) => removeSeat(gameId, seatId) });
}

export function useTakeOverSeat(gameId: string) {
  return useMutation({ mutationFn: (seatId: string) => takeOverSeat(gameId, seatId) });
}

export function useIssueSeatCode(gameId: string) {
  return useMutation({ mutationFn: (seatId: string) => issueSeatCode(gameId, seatId) });
}

/**
 * The question a scanned code asks before it is used up: "Du übernimmst Ana?"
 *
 * `retry: false` because the two failures here are answers, not glitches: 404
 * means the code is gone, 409 means not from this browser.
 */
export function useSeatCodeLookup(code: string) {
  return useQuery({
    queryKey: ["seat-code", normaliseCode(code)],
    queryFn: () => lookUpSeatCode(code),
    enabled: normaliseCode(code).length > 0,
    staleTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useRedeemSeatCode() {
  return useMutation({ mutationFn: (code: string) => redeemSeatCode(code) });
}
