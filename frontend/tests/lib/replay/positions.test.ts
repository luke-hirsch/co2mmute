import { describe, expect, it } from "vitest";

import { makeCursor, positionAt } from "@/lib/replay/positions";
import type { ReplayDot } from "@/lib/replay/types";

/**
 * Where one dot is at one simulated minute.
 *
 * The wire format is `[kind, ref, from, to, fromNode]` per leg, with one
 * timestamp per event on the backend — entering link N+1 *is* leaving link N —
 * so the legs join up exactly and there is never a gap to invent a position
 * for. See §6 of `[backend]-replay-aufzeichnung.md`.
 *
 * Two things here are not bookkeeping:
 *
 * - **`wants` is not the first leg.** The gap between them is the queue at the
 *   front door: someone who wanted to leave at 48 and whose street had no room
 *   until 55 stood at home for seven minutes. No instrument could see that
 *   until `stau-sichtbar`, and it is the most explanatory thing the animation
 *   draws.
 * - **Direction comes from the leg.** An edge is stored either way round
 *   (`sim.state.node_chain` exists for that), so `fromNode` is what says which
 *   end the dot started at. Reading the edge instead draws half the map's
 *   traffic backwards.
 */

const driver: ReplayDot = {
  id: 12,
  route: 34,
  agent: 2,
  line: null,
  mode: "car",
  wants: 48,
  pass: "out",
  legs: [
    ["e", 91, 55, 57, 7],
    ["e", 102, 57, 61, 12],
  ],
  end: "arrived",
};

const rider: ReplayDot = {
  id: 20,
  route: 34,
  agent: 3,
  line: null,
  mode: "public",
  wants: 40,
  pass: "out",
  legs: [
    ["e", 91, 40, 44, 7],
    ["s", 12, 44, 52, null],
    ["r", 5, 52, 63, null],
    ["e", 110, 63, 66, 30],
  ],
  end: "arrived",
};

const stranded: ReplayDot = {
  id: 33,
  route: 34,
  agent: 4,
  line: null,
  mode: "public",
  wants: 70,
  pass: "out",
  legs: [
    ["e", 91, 70, 74, 7],
    ["s", 12, 74, 225, null],
  ],
  end: "stranded",
};

describe("positionAt", () => {
  it("keeps a dot off screen before it wanted to leave", () => {
    expect(positionAt(driver, 30, makeCursor()).kind).toBe("pending");
  });

  it("stands it at the front door until the street has room", () => {
    // The door queue. 48 -> 55 is seven minutes at home, and drawing them on
    // the link instead would put the jam in the wrong place — the specific lie
    // the old heatmap told.
    const position = positionAt(driver, 51, makeCursor());

    expect(position.kind).toBe("waiting");
  });

  it("interpolates along the link it is crossing", () => {
    const position = positionAt(driver, 56, makeCursor());

    expect(position).toMatchObject({ kind: "edge", edgeId: 91, fromNode: 7 });
    if (position.kind === "edge") {
      expect(position.progress).toBeCloseTo(0.5, 6);
    }
  });

  it("carries the node the link was entered from", () => {
    // Both legs of this route run 'forwards', but the second starts at a
    // different node — which is the only thing that can orient it.
    const position = positionAt(driver, 59, makeCursor());

    expect(position).toMatchObject({ kind: "edge", edgeId: 102, fromNode: 12 });
  });

  it("stands a rider at the stop while it waits", () => {
    const position = positionAt(rider, 48, makeCursor());

    expect(position).toEqual({ kind: "node", nodeId: 12 });
  });

  it("puts a rider on the vehicle it boarded", () => {
    // Resolved against the same replay: every line vehicle is recorded
    // whatever the sampling stride, so the lookup cannot miss.
    const position = positionAt(rider, 57, makeCursor());

    expect(position).toEqual({ kind: "riding", vehicleId: 5 });
  });

  it("says how the trip ended once it is over", () => {
    expect(positionAt(driver, 200, makeCursor())).toEqual({
      kind: "done",
      end: "arrived",
    });
  });

  it("leaves whoever never got a seat standing at the stop", () => {
    // The beat may not claim everybody arrived while this dot is on screen.
    expect(positionAt(stranded, 150, makeCursor())).toEqual({
      kind: "node",
      nodeId: 12,
    });
    expect(positionAt(stranded, 240, makeCursor())).toEqual({
      kind: "done",
      end: "stranded",
    });
  });

  it("gives the same answer whether or not the cursor has run forward", () => {
    // The cursor exists so playback is O(1) per dot per frame instead of a
    // fresh scan — 500 dots at 60fps is 30 000 scans a second otherwise. It
    // must never change the answer, including when the user scrubs backwards.
    const cursor = makeCursor();
    for (let minute = 40; minute <= 66; minute += 0.5) {
      positionAt(rider, minute, cursor);
    }

    expect(positionAt(rider, 48, cursor)).toEqual(
      positionAt(rider, 48, makeCursor()),
    );
    expect(positionAt(rider, 57, cursor)).toEqual(
      positionAt(rider, 57, makeCursor()),
    );
  });
});
