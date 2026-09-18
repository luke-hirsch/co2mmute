import { describe, expect, it } from "vitest";

import type { RosterSeat } from "@/lib/game/events";
import {
  activeSeatId,
  deskDone,
  deskReducer,
  deskSeats,
  initialDeskState,
  nextDeskSeat,
  seatsDoneMoving,
  type DeskState,
} from "@/lib/game/desk";

/**
 * The host desk: which seat is being played at the host machine, and when the
 * screen has to fall back to the list.
 *
 * All of this is here rather than in the component because the interesting
 * cases are the ones nobody produces by clicking: a seat taken over while the
 * host has it open, a round that turns over mid-turn, a seat removed from
 * under the screen. Each of them must land back at the desk, and none of them
 * may leave the previous player's choices on a projector.
 *
 * Since F5 the desk also runs the map vote, so what counts as "this seat is
 * through" is the caller's to decide: the roster answers it during a round
 * (`seatsDoneMoving`), and between rounds the caller keeps its own record,
 * because the roster reports `ready` for everybody once no round is open.
 */

function seat(overrides: Partial<RosterSeat> & { player_id: string }): RosterSeat {
  return {
    name: "Ben",
    is_host: false,
    controlled_by_host: true,
    online: true,
    status: "making_move",
    ...overrides,
  };
}

const host = seat({ player_id: "H-1", name: "Host", is_host: true, controlled_by_host: false });
const ben = seat({ player_id: "P-1", name: "Ben" });
const ana = seat({ player_id: "P-2", name: "Ana" });
/** A student on their own phone. The desk never plays this one. */
const phone = seat({ player_id: "P-3", name: "Kim", controlled_by_host: false });

const roster = [host, ben, ana, phone];

/** Nobody is through yet. */
const none: ReadonlySet<string> = new Set();

const ROUND_1 = "round:1";
const ROUND_2 = "round:2";

function playing(seatId: string, epoch = ROUND_1): DeskState {
  return { mode: { kind: "playing", seatId }, epoch };
}

describe("deskSeats", () => {
  it("keeps only the seats played at the host machine", () => {
    expect(deskSeats(roster).map((s) => s.player_id)).toEqual(["P-1", "P-2"]);
  });

  it("never includes the host's own row", () => {
    // controlled_by_host is False on a host row since migration 0008, but the
    // desk must not depend on that: is_host is the rule.
    const oddHost = { ...host, controlled_by_host: true };
    expect(deskSeats([oddHost]).length).toBe(0);
  });
});

describe("seatsDoneMoving", () => {
  it("is the seats the roster says have submitted", () => {
    const seats = [host, { ...ben, status: "waiting" as const }, ana, phone];
    expect([...seatsDoneMoving(seats)]).toEqual(["P-1"]);
  });

  it("is empty between rounds, when no round is open", () => {
    // `game/roster.py` reports `ready` for every connected seat while no round
    // is active — which is exactly why the vote desk cannot use this and keeps
    // its own record instead.
    const seats = roster.map((s) => ({ ...s, status: "ready" as const }));
    expect(seatsDoneMoving(seats).size).toBe(0);
  });
});

describe("deskReducer", () => {
  it("starts at the desk", () => {
    const state = initialDeskState(ROUND_1);
    expect(state.mode.kind).toBe("desk");
    expect(activeSeatId(state)).toBeNull();
  });

  it("puts a curtain in front of every seat", () => {
    const state = deskReducer(initialDeskState(ROUND_1), {
      kind: "pick",
      seatId: "P-1",
    });

    expect(state.mode).toEqual({ kind: "curtain", seatId: "P-1" });
    // The curtain names the seat but the screen behind it is not rendered yet:
    // that is the whole point on a projector.
    expect(activeSeatId(state)).toBe("P-1");
  });

  it("opens the seat only on 'ready'", () => {
    let state = deskReducer(initialDeskState(ROUND_1), {
      kind: "pick",
      seatId: "P-1",
    });
    state = deskReducer(state, { kind: "ready" });

    expect(state.mode).toEqual({ kind: "playing", seatId: "P-1" });
  });

  it("ignores 'ready' at the desk", () => {
    const state = initialDeskState(ROUND_1);
    expect(deskReducer(state, { kind: "ready" })).toBe(state);
  });

  it("goes back to the desk on leave", () => {
    const state = deskReducer(playing("P-1"), { kind: "leave" });
    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("curtains again when the host picks the next seat", () => {
    const state = deskReducer(playing("P-1"), { kind: "pick", seatId: "P-2" });
    expect(state.mode).toEqual({ kind: "curtain", seatId: "P-2" });
  });
});

describe("deskReducer sync", () => {
  it("leaves an untouched seat alone", () => {
    const state = playing("P-1");
    expect(
      deskReducer(state, {
        kind: "sync",
        seats: roster,
        done: none,
        epoch: ROUND_1,
      }),
    ).toBe(state);
  });

  it("closes the seat when the round turns over", () => {
    const state = deskReducer(playing("P-1"), {
      kind: "sync",
      seats: roster,
      done: none,
      epoch: ROUND_2,
    });

    expect(state.mode).toEqual({ kind: "desk" });
    expect(state.epoch).toBe(ROUND_2);
  });

  it("closes the seat when the phase turns over", () => {
    // The vote desk's epoch carries the phase as well as the round: a revote
    // after a tie reopens `voting`, and whatever ballot was on the projector
    // must not still be standing.
    const state = deskReducer(playing("P-1", "2:voting"), {
      kind: "sync",
      seats: roster,
      done: none,
      epoch: "2:stalemate",
    });

    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("closes the seat once it has submitted", () => {
    // The roster is the one truth for "has this seat moved" (F3). When it says
    // waiting, the turn is over and the next student steps up.
    const seats = [host, { ...ben, status: "waiting" as const }, ana, phone];
    const state = deskReducer(playing("P-1"), {
      kind: "sync",
      seats,
      done: seatsDoneMoving(seats),
      epoch: ROUND_1,
    });

    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("closes the seat once the caller says it is through", () => {
    // The vote's version of the case above: the roster still says `ready`, and
    // the seat is finished because this device has cast its vote.
    const state = deskReducer(playing("P-1", "2:voting"), {
      kind: "sync",
      seats: roster,
      done: new Set(["P-1"]),
      epoch: "2:voting",
    });

    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("closes the seat when it moves to a device", () => {
    // A code was redeemed: the seat is somebody's phone now, and the host
    // machine may not keep it open.
    const seats = [host, { ...ben, controlled_by_host: false }, ana, phone];
    const state = deskReducer(playing("P-1"), {
      kind: "sync",
      seats,
      done: none,
      epoch: ROUND_1,
    });

    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("closes the seat when it leaves the game", () => {
    const state = deskReducer(playing("P-1"), {
      kind: "sync",
      seats: [host, ana, phone],
      done: none,
      epoch: ROUND_1,
    });

    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("closes a curtained seat on the same rules", () => {
    const state = deskReducer(
      { mode: { kind: "curtain", seatId: "P-1" }, epoch: ROUND_1 },
      { kind: "sync", seats: [host, ana, phone], done: none, epoch: ROUND_1 },
    );

    expect(state.mode).toEqual({ kind: "desk" });
  });

  it("follows the epoch while sitting at the desk", () => {
    const state = deskReducer(initialDeskState(ROUND_1), {
      kind: "sync",
      seats: roster,
      done: none,
      epoch: "round:3",
    });

    expect(state.mode).toEqual({ kind: "desk" });
    expect(state.epoch).toBe("round:3");
  });
});

describe("nextDeskSeat", () => {
  it("is the first seat that still owes a move", () => {
    const seats = [host, { ...ben, status: "waiting" as const }, ana, phone];
    expect(nextDeskSeat(seats, seatsDoneMoving(seats))?.player_id).toBe("P-2");
  });

  it("carries on after the seat just played, and wraps", () => {
    expect(nextDeskSeat(roster, none, "P-1")?.player_id).toBe("P-2");
    expect(nextDeskSeat(roster, none, "P-2")?.player_id).toBe("P-1");
  });

  it("skips the seat just played when it has submitted", () => {
    const seats = [host, ben, { ...ana, status: "waiting" as const }, phone];
    expect(nextDeskSeat(seats, seatsDoneMoving(seats), "P-2")?.player_id).toBe(
      "P-1",
    );
  });

  it("takes the done set from the caller, whatever the roster says", () => {
    // Between rounds every seat is `ready`; the vote's record is what decides.
    expect(nextDeskSeat(roster, new Set(["P-1"]))?.player_id).toBe("P-2");
  });

  it("is null when every seat at the machine is through", () => {
    const seats = [
      host,
      { ...ben, status: "waiting" as const },
      { ...ana, status: "waiting" as const },
      phone,
    ];
    const done = seatsDoneMoving(seats);
    expect(nextDeskSeat(seats, done)).toBeNull();
    expect(deskDone(seats, done)).toBe(true);
  });

  it("is not 'done' when there is no seat at the machine at all", () => {
    // Every student on their own phone: the desk has nothing to play, which is
    // a different sentence from "everyone here is through".
    expect(deskDone([host, phone], none)).toBe(false);
  });
});
