/**
 * The desk reducer, wired to the game.
 *
 * All it adds to `lib/game/desk.ts` is the `sync` — the roster and the epoch
 * arrive from the provider, and every change is pushed through the reducer so
 * that a seat which finishes, moves to a phone or disappears closes itself.
 * Nothing here fetches, nothing polls; the roster is already the one truth for
 * all of it.
 *
 * **Two desks use it** (F5): the round's, where a seat is done when the roster
 * says `waiting`, and the map vote's, where the roster says nothing at all and
 * the caller keeps the record. What a seat is *for* is the caller's business;
 * the curtain rules are the same either way, and they are the part worth having
 * in one place.
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
  seatsDoneMoving,
} from "@/lib/game/desk";
import { seatById } from "@/lib/game/game-state";

export function useDesk({
  done,
  epoch,
}: {
  /** Seats that are finished with whatever this desk is for. */
  done: ReadonlySet<string>;
  /** Changing it closes whatever seat is open. */
  epoch: string;
}) {
  const { state } = useGame();
  const [desk, dispatch] = useReducer(deskReducer, epoch, initialDeskState);

  useEffect(() => {
    dispatch({ kind: "sync", seats: state.seats, done, epoch });
  }, [state.seats, done, epoch]);

  const seats = useMemo(() => deskSeats(state.seats), [state.seats]);
  const openSeatId = activeSeatId(desk);
  const openSeat = seatById(state, openSeatId);

  const pick = useCallback((seatId: string) => dispatch({ kind: "pick", seatId }), []);
  const ready = useCallback(() => dispatch({ kind: "ready" }), []);
  const leave = useCallback(() => dispatch({ kind: "leave" }), []);

  /**
   * Hand the machine to whoever still owes something, carrying on after the
   * seat just played. Does nothing when everyone here is through — the screen
   * says so rather than opening a seat that has nothing to do.
   */
  const playNext = useCallback(() => {
    const next = nextDeskSeat(state.seats, done, openSeatId);
    if (next) dispatch({ kind: "pick", seatId: next.player_id });
  }, [state.seats, done, openSeatId]);

  return {
    mode: desk.mode.kind,
    /** The seat behind the curtain or on screen, as the roster knows it. */
    openSeat,
    openSeatId,
    seats,
    done: deskDone(state.seats, done),
    hasNext: nextDeskSeat(state.seats, done, openSeatId) !== null,
    pick,
    ready,
    leave,
    playNext,
  };
}

/**
 * The round's desk: a seat is done when it has submitted its move.
 *
 * The set is derived from the roster on every render, so it is memoised — it is
 * a `useEffect` dependency in `useDesk`, and a fresh Set each time would sync
 * the reducer on every render for no reason.
 */
export function useRoundDesk() {
  const { state } = useGame();
  const done = useMemo(() => seatsDoneMoving(state.seats), [state.seats]);
  return useDesk({ done, epoch: `round:${state.currentRound}` });
}
