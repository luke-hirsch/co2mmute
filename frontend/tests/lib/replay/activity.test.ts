import { describe, expect, it } from "vitest";

import { activityProfile } from "@/lib/replay/activity";
import type { Replay, ReplayDot } from "@/lib/replay/types";

/**
 * What counts as "happening", which is the whole of the time warp's input.
 *
 * Two of the three rules here are judgements rather than bookkeeping, and both
 * are things the animation exists to show:
 *
 * - **the crowd at the front door is activity.** A dot counts from when it wanted
 *   to leave, not from when the street let it out. Fast-forwarding past a growing
 *   queue outside a full street would skip the finding behind `stau-sichtbar`.
 * - **a bus is not.** Since `pt-service-period` a line dispatches for as long as
 *   anybody needs it, so buses roll to the end of the clock. Counting them would
 *   make the drain read as busy as the peak and flatten the warp to a constant
 *   rate — exactly what the warp exists to avoid.
 */

function replay(dots: ReplayDot[], endMin: number): Replay {
  return {
    version: 1,
    people_per_dot: 50,
    tick_duration_min: 5,
    window_min: 120,
    end_min: endMin,
    dots,
  };
}

const driver: ReplayDot = {
  id: 1,
  route: 1,
  agent: 1,
  line: null,
  mode: "car",
  wants: 10,
  // Held at the door from 10 to 20, then on the road until 30.
  legs: [["e", 91, 20, 30, 7]],
  end: "arrived",
};

const bus: ReplayDot = {
  id: -2,
  route: null,
  agent: null,
  line: "M1",
  mode: "bus",
  wants: 0,
  legs: [["e", 91, 0, 60, 7]],
  end: "arrived",
};

describe("activityProfile", () => {
  it("has one entry per simulated minute", () => {
    // The index IS the minute — buildWarp assumes exactly that when no endMin is
    // passed to it.
    expect(activityProfile(replay([driver], 30))).toHaveLength(30);
    expect(activityProfile(replay([driver], 227.4))).toHaveLength(228);
  });

  it("counts a dot from when it WANTED to leave", () => {
    // Minute 15 is inside the door queue: the dot is on screen, standing at home,
    // and the ten minutes it stands there are the most explanatory in the round.
    const profile = activityProfile(replay([driver], 40));

    expect(profile[15]).toBe(1);
    expect(profile[25]).toBe(1);
  });

  it("does not count it before that, or after it is done", () => {
    const profile = activityProfile(replay([driver], 40));

    expect(profile[5]).toBe(0);
    expect(profile[35]).toBe(0);
  });

  it("leaves the timetable out of it", () => {
    const profile = activityProfile(replay([driver, bus], 60));

    expect(profile[50]).toBe(0);
    expect(profile[25]).toBe(1);
  });

  it("can be asked for the timetable anyway", () => {
    // A PT-only map would otherwise produce a flat profile. The default is a
    // judgement, not a fact, so it is a flag rather than a hard-coded filter.
    const profile = activityProfile(replay([driver, bus], 60), {
      includeVehicles: true,
    });

    expect(profile[50]).toBe(1);
    expect(profile[25]).toBe(2);
  });

  it("keeps somebody who never arrived on screen to the end", () => {
    // The dot the beat card may not claim arrived. It is still standing at its
    // stop, and the drain must not be fast-forwarded past it as if it were empty.
    const stuck: ReplayDot = {
      ...driver,
      id: 3,
      mode: "public",
      legs: [["s", 12, 20, 200, null]],
      end: "unfinished",
    };
    const profile = activityProfile(replay([stuck], 200));

    expect(profile[199]).toBe(1);
  });

  it("gives the peak more than the drain, which is what the warp reads", () => {
    const crowd: ReplayDot[] = Array.from({ length: 40 }, (_, index) => ({
      ...driver,
      id: index + 10,
      wants: 20,
      legs: [["e", 91, 20, 60, 7]] as ReplayDot["legs"],
    }));
    const straggler: ReplayDot = {
      ...driver,
      id: 99,
      wants: 20,
      legs: [["e", 91, 20, 200, 7]],
      end: "arrived",
    };
    const profile = activityProfile(replay([...crowd, straggler], 200));

    expect(profile[30]).toBe(41);
    expect(profile[150]).toBe(1);
  });

  it("survives a round that recorded nothing", () => {
    expect(activityProfile(replay([], 0))).toEqual([]);
  });
});
