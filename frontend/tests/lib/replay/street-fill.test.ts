import { describe, expect, it } from "vitest";

import {
  buildStreetFill,
  doorNodeByEdge,
  waitingByNode,
} from "@/lib/replay/street-fill";
import type { ReplayDot, ReplayTick } from "@/lib/replay/types";

/**
 * The street layer, and the one thing about it that is easy to get wrong.
 *
 * `_advance_traffic()` runs tick `t` over `[t·d, (t+1)·d)` and the snapshot is
 * taken **after** it, so a row labelled `t` describes minute `(t+1)·d`. Off by
 * one tick and a jam appears five minutes before the cars that cause it.
 *
 * And `_record_edge_traffic` only writes a row for a link that had something on
 * it, so a gap in an edge's rows is a genuinely quiet stretch. Interpolating
 * across it would invent traffic — which is the class of thing the old heatmap
 * did when it averaged the time axis away.
 */

const TICK_MIN = 5;

/** Two links: 91 busy early with a door queue, 102 busy after a quiet tick. */
const ticks: ReplayTick[] = [
  { t: 0, edges: [[91, 100, 400, 46.7]] },
  { t: 1, edges: [[91, 200, 200, 30.1]] },
  { t: 2, edges: [[91, 0, 0, 48.0], [102, 40, 0, 44.0]] },
  // No row for 102 at tick 3: nothing was on it.
  { t: 4, edges: [[102, 80, 0, 41.0]] },
];

describe("buildStreetFill", () => {
  it("reads a row at the END of the tick it is labelled with", () => {
    const fill = buildStreetFill(ticks, TICK_MIN);

    // Tick 0 is minute 5, not minute 0.
    expect(fill.fillAt(91, 5).vehicles).toBe(100);
    expect(fill.fillAt(91, 10).vehicles).toBe(200);
  });

  it("interpolates between two ticks", () => {
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.fillAt(91, 7.5).vehicles).toBeCloseTo(150, 6);
    expect(fill.fillAt(91, 7.5).waiting).toBeCloseTo(300, 6);
  });

  it("starts empty and ramps into the first row", () => {
    // The street is empty before anybody leaves; the first tick's fill arrives
    // over that tick rather than being there from frame one.
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.fillAt(91, 0).vehicles).toBe(0);
    expect(fill.fillAt(91, 2.5).vehicles).toBeCloseTo(50, 6);
  });

  it("empties again after the last row", () => {
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.fillAt(102, 25).vehicles).toBe(80);
    expect(fill.fillAt(102, 27.5).vehicles).toBeCloseTo(40, 6);
    expect(fill.fillAt(102, 30).vehicles).toBe(0);
  });

  it("does not interpolate across a tick a link had nothing on it", () => {
    // 102 has rows at ticks 2 and 4 and none at 3. Minute 20 IS tick 3, and it
    // has to read empty — a link nobody was on may not borrow its neighbours'
    // traffic.
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.fillAt(102, 20).vehicles).toBe(0);
  });

  it("reports nothing for a link that never carried anything", () => {
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.fillAt(7, 10)).toEqual({
      vehicles: 0,
      waiting: 0,
      speedKmh: 0,
    });
    expect(fill.edgeIds).toEqual([91, 102]);
  });

  it("holds the nearest measured speed instead of fading it to a standstill", () => {
    // Speed is an output of the model, and an unsampled minute is an empty
    // street, not a street at 0 km/h. It is never drawn as a colour either way.
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.fillAt(91, 0).speedKmh).toBe(46.7);
    expect(fill.fillAt(91, 100).speedKmh).toBe(48.0);
  });

  it("names the worst fill anywhere, for scaling", () => {
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(fill.peakVehicles).toBe(200);
    expect(fill.peakWaiting).toBe(400);
  });

  it("survives a round that recorded no street at all", () => {
    const fill = buildStreetFill([], TICK_MIN);

    expect(fill.edgeIds).toEqual([]);
    expect(fill.fillAt(91, 10).vehicles).toBe(0);
    expect(fill.peakVehicles).toBe(0);
  });
});

/** Dots leaving link 91 from node 7, and one bus that must not be read as one. */
const dots: ReplayDot[] = [
  {
    id: 1,
    route: 1,
    agent: 1,
    line: null,
    mode: "car",
    wants: 48,
    pass: "out",
    legs: [["e", 91, 55, 57, 7]],
    end: "arrived",
  },
  {
    id: 2,
    route: 2,
    agent: 2,
    line: null,
    mode: "car",
    wants: 49,
    pass: "out",
    legs: [["e", 91, 56, 58, 7]],
    end: "arrived",
  },
  {
    id: 3,
    route: 3,
    agent: 3,
    line: null,
    mode: "car",
    wants: 50,
    pass: "out",
    // The other end of the same street — a real case, and the minority here.
    legs: [["e", 91, 57, 59, 12]],
    end: "arrived",
  },
  {
    id: -4,
    route: null,
    agent: null,
    line: "M1",
    mode: "bus",
    wants: 0,
    pass: "out",
    legs: [["e", 91, 0, 2, 12]],
    end: "arrived",
  },
];

describe("doorNodeByEdge", () => {
  it("learns which end of a link people leave from", () => {
    // `waiting_count` is per link and carries no direction. The dots' first legs
    // are the only thing that does.
    expect(doorNodeByEdge(dots).get(91)).toBe(7);
  });

  it("ignores a line vehicle, which has no front door", () => {
    // Without the filter the bus's node would be a third vote on link 91 — and
    // on a link no person ever starts on, the bus would invent a door.
    const busOnly = dots.filter((dot) => dot.line !== null);

    expect(doorNodeByEdge(busOnly).size).toBe(0);
  });

  it("says nothing about a link nobody started on", () => {
    expect(doorNodeByEdge(dots).has(102)).toBe(false);
  });
});

describe("waitingByNode", () => {
  it("puts the front-door queue at the node, never on the link", () => {
    // The whole finding behind stau-sichtbar: these people are not on the street
    // yet, and drawing them along the edge is the specific lie the old heatmap
    // told.
    const fill = buildStreetFill(ticks, TICK_MIN);
    const doors = doorNodeByEdge(dots);

    const byNode = waitingByNode(fill, 5, (edgeId) => doors.get(edgeId) ?? null);

    expect(byNode.get(7)).toBe(400);
    expect(byNode.size).toBe(1);
  });

  it("drops a crowd it cannot place rather than guessing a node", () => {
    const fill = buildStreetFill(ticks, TICK_MIN);

    expect(waitingByNode(fill, 5, () => null).size).toBe(0);
  });

  it("sums two links that queue at the same node", () => {
    const fill = buildStreetFill(
      [{ t: 0, edges: [[91, 1, 400, 40], [102, 1, 100, 40]] }],
      TICK_MIN,
    );

    const byNode = waitingByNode(fill, 5, () => 7);

    expect(byNode.get(7)).toBe(500);
  });
});
