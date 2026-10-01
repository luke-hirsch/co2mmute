import { describe, expect, it } from "vitest";

import { dotScale, replayEndings } from "@/lib/replay/counts";
import type { Replay, ReplayDot, ReplayEnd } from "@/lib/replay/types";

/**
 * The two numbers the replay prints in words: what a dot is worth, and who did
 * not get there.
 *
 * The closing sentence may only say everybody arrived when everybody did, and the
 * sample cannot know that — the people still at their front door when the clock
 * stops never became vehicles, so no dot exists for any of them. Since S25 the
 * recording carries the simulator's own count; a recording from before falls
 * back to the sample, which is the best that recording can say.
 */

function person(id: number, end: ReplayEnd): ReplayDot {
  return {
    id,
    route: 1,
    agent: 1,
    line: null,
    mode: "car",
    wants: 0,
  pass: "out",
    legs: [["e", 91, 0, 10, 7]],
    end,
  };
}

const bus: ReplayDot = {
  id: -1,
  route: null,
  agent: null,
  line: "M1",
  mode: "bus",
  wants: 0,
  pass: "out",
  legs: [["e", 91, 0, 10, 7]],
  // A line vehicle still rolling at the end is not a person who did not arrive.
  end: "unfinished",
};

function replay(dots: ReplayDot[], extra: Partial<Replay> = {}): Replay {
  return {
    version: 2,
    people_per_dot: 10,
    tick_duration_min: 5,
    window_min: 120,
    end_min: 60,
    home_start_min: null,
    dots,
    ...extra,
  };
}

describe("replayEndings", () => {
  it("reads the simulator's count when the recording carries one", () => {
    // One sampled dot made it; 1 668 people were still at their door.
    const counted = replay([person(1, "arrived"), bus], {
      endings: { unfinished: 1668, stranded: 0 },
    });

    expect(replayEndings(counted)).toEqual({ unfinished: 1668, stranded: 0 });
  });

  it("says nobody is missing only when the count says so", () => {
    const everybody = replay([person(1, "arrived")], {
      endings: { unfinished: 0, stranded: 0 },
    });

    expect(replayEndings(everybody)).toEqual({ unfinished: 0, stranded: 0 });
  });

  it("falls back to the sample for a recording from before the count", () => {
    const old = replay(
      [person(1, "arrived"), person(2, "unfinished"), person(3, "stranded"), bus],
      { people_per_dot: 50 },
    );

    expect(replayEndings(old)).toEqual({ unfinished: 50, stranded: 50 });
  });

  it("rounds the fallback, because a ratio need not be whole", () => {
    const old = replay([person(1, "unfinished")], { people_per_dot: 9.76 });

    expect(replayEndings(old)).toEqual({ unfinished: 10, stranded: 0 });
  });
});

describe("dotScale", () => {
  it("names a whole number of people", () => {
    expect(dotScale(replay([], { people_per_dot: 9.76 }))).toBe(10);
    expect(dotScale(replay([], { people_per_dot: 10 }))).toBe(10);
  });

  it("never says a dot is nobody", () => {
    expect(dotScale(replay([], { people_per_dot: 0.4 }))).toBe(1);
  });
});
