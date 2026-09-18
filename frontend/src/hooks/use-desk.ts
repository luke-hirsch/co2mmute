/**
 * The desk reducer, wired to the game.
 *
 * All it adds to `lib/game/desk.ts` is the `sync` — the roster and the round
 * number arrive from the provider, and every change is pushed through the
 * reducer so that a seat which submits, moves to a phone or disappears closes
 * itself. Nothing here fetches, nothing polls; the roster is already the one
 * truth for all of it.
 */

import { useCallback, useEffect, useMemo, useReducer } from "react";

import { useGame } from "@/components/game/game-context";
import {
  activeSeatId,
  deskDone,
  deskReducer,
  deskSeats,
  initialDeskState,
  nextDeskSeat,
} from "@/lib/game/desk";
import { seatById } from "@/lib/game/game-state";

export function useDesk() {
  const { state } = useGame();
  const [desk, dispatch] = useReducer(
    deskReducer,
    state.currentRound,
    initialDeskState,
  );

  useEffect(() => {
    dispatch({
      kind: "sync",
      seats: state.seats,
      roundNumber: state.currentRound,
    });
  }, [state.seats, state.currentRound]);

  const seats = useMemo(() => deskSeats(state.seats), [state.seats]);
  const openSeatId = activeSeatId(desk);
  const openSeat = seatById(state, openSeatId);

  const pick = useCallback((seatId: string) => dispatch({ kind: "pick", seatId }), []);
  const ready = useCallback(() => dispatch({ kind: "ready" }), []);
  const leave = useCallback(() => dispatch({ kind: "leave" }), []);

  /**
   * Hand the machine to whoever still owes a move, carrying on after the seat
   * just played. Does nothing when everyone here is through — the screen says
   * so rather than opening a seat that has nothing to do.
   */
  const playNext = useCallback(() => {
    const next = nextDeskSeat(state.seats, openSeatId);
    if (next) dispatch({ kind: "pick", seatId: next.player_id });
  }, [state.seats, openSeatId]);

  return {
    mode: desk.mode.kind,
    /** The seat behind the curtain or on screen, as the roster knows it. */
    openSeat,
    openSeatId,
    seats,
    done: deskDone(state.seats),
    hasNext: nextDeskSeat(state.seats, openSeatId) !== null,
    pick,
    ready,
    leave,
    playNext,
  };
}
