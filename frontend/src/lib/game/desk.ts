/**
 * The host desk, as state: which seat is being played at the host machine.
 *
 * The host does not play (Roadmap.md 2.7, decided 18.09.26). What the desk does
 * is hand the machine to one student at a time, and the awkward part is not the
 * handing over — it is everything that can happen to a seat while it is open.
 * It can submit, it can be given to a phone, it can be removed, and the round
 * can turn over under it. Each of those has to close the seat and put the list
 * back on screen, or a projector keeps showing somebody else's turn.
 *
 * So the rule is written once, here, as a reducer over the roster rather than
 * as conditions inside a component:
 *
 *   desk ──pick──► curtain ──ready──► playing ──┐
 *     ▲                                          │
 *     └────── leave / sync says it is over ──────┘
 *
 * **The curtain is state, not a timer.** It has to appear whenever the desk
 * changes seat, including when the change did not come from a click — and a
 * `setTimeout` only catches that by accident.
 *
 * Pure: no React, no fetch. `use-desk.ts` wires it to the provider.
 */

import type { RosterSeat } from "@/lib/game/events";

export type DeskMode =
  | { kind: "desk" }
  | { kind: "curtain"; seatId: string }
  | { kind: "playing"; seatId: string };

export type DeskState = {
  mode: DeskMode;
  /**
   * What this desk belongs to. When it changes, whatever was open closes.
   *
   * A string rather than the round number, because F5 runs the same carousel
   * for the map vote, where the thing that has to close an open seat is the
   * *phase* turning over as well as the round — a revote after a tie must not
   * leave the previous ballot standing on the projector.
   */
  epoch: string;
};

export type DeskAction =
  | { kind: "pick"; seatId: string }
  | { kind: "ready" }
  | { kind: "leave" }
  | {
      kind: "sync";
      seats: RosterSeat[];
      /** Seats that are finished with whatever this desk is for. */
      done: ReadonlySet<string>;
      epoch: string;
    };

export function initialDeskState(epoch: string): DeskState {
  return { mode: { kind: "desk" }, epoch };
}

/**
 * The seats the roster says have submitted this round.
 *
 * "waiting" is the roster's word for "has moved" (`game/roster.py`), and it is
 * the one truth for it — the same one the round screen reads (F3). The vote
 * desk cannot use it: between rounds the roster reports `ready` for everyone,
 * because there is no open round to have moved in. It builds its own set from
 * what the device has sent instead.
 */
export function seatsDoneMoving(seats: RosterSeat[]): ReadonlySet<string> {
  return new Set(
    seats.filter((seat) => seat.status === "waiting").map((seat) => seat.player_id),
  );
}

/**
 * The seats this machine plays: at the host machine, and never the host's own
 * row. `is_host` is the rule and `controlled_by_host` the condition — they look
 * alike and are not the same thing (`game/models.py:PlayerQuerySet`).
 */
export function deskSeats(seats: RosterSeat[]): RosterSeat[] {
  return seats.filter((seat) => !seat.is_host && seat.controlled_by_host);
}

/** The seat the desk is on, curtained or open. */
export function activeSeatId(state: DeskState): string | null {
  return state.mode.kind === "desk" ? null : state.mode.seatId;
}

/** Whether this seat still has something to do at the machine right now. */
function playable(
  seats: RosterSeat[],
  seatId: string,
  done: ReadonlySet<string>,
): boolean {
  const seat = deskSeats(seats).find((candidate) => candidate.player_id === seatId);
  return !!seat && !done.has(seatId);
}

/**
 * The next seat that still owes something, carrying on after the one just
 * played and wrapping around. Null when every seat at this machine is through.
 */
export function nextDeskSeat(
  seats: RosterSeat[],
  done: ReadonlySet<string>,
  afterSeatId?: string | null,
): RosterSeat | null {
  const playing = deskSeats(seats);
  if (playing.length === 0) return null;

  const from = afterSeatId
    ? playing.findIndex((seat) => seat.player_id === afterSeatId) + 1
    : 0;

  for (let step = 0; step < playing.length; step += 1) {
    const seat = playing[(from + step) % playing.length];
    if (!done.has(seat.player_id)) return seat;
  }
  return null;
}

/**
 * Every seat at this machine is through. Deliberately false when there is no
 * such seat at all: "all done here" and "nothing to do here" are different
 * sentences, and the desk says a different one for each.
 */
export function deskDone(
  seats: RosterSeat[],
  done: ReadonlySet<string>,
): boolean {
  const playing = deskSeats(seats);
  return playing.length > 0 && playing.every((seat) => done.has(seat.player_id));
}

export function deskReducer(state: DeskState, action: DeskAction): DeskState {
  switch (action.kind) {
    case "pick":
      // Always through the curtain, even from another seat: the point is that
      // the room never sees the switch itself.
      return { ...state, mode: { kind: "curtain", seatId: action.seatId } };

    case "ready":
      if (state.mode.kind !== "curtain") return state;
      return { ...state, mode: { kind: "playing", seatId: state.mode.seatId } };

    case "leave":
      if (state.mode.kind === "desk") return state;
      return { ...state, mode: { kind: "desk" } };

    case "sync": {
      // A new round — or, for the vote desk, a new phase — is the one change
      // that closes a seat no matter what: everyone owes something again, so
      // the machine goes back to the list.
      if (action.epoch !== state.epoch) {
        return { mode: { kind: "desk" }, epoch: action.epoch };
      }
      if (state.mode.kind === "desk") return state;
      if (playable(action.seats, state.mode.seatId, action.done)) return state;
      return { ...state, mode: { kind: "desk" } };
    }
  }
}
