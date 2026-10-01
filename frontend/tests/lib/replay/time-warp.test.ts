import { describe, expect, it } from "vitest";

import {
  buildWarp,
  REPLAY_BUDGET_SEC,
  REPLAY_MIDDAY_SEC,
  warpSpan,
} from "@/lib/replay/time-warp";
import type { Replay, ReplayDot } from "@/lib/replay/types";

/**
 * A round, there and back, in about two minutes.
 *
 * Morning and evening run at ONE constant rate and the empty middle of the day
 * is the only fast-forward. It was handed out by how many dots moved until F2b,
 * and that made every dot — the trains too, whose link times the simulation
 * holds constant — run five to seven times faster in the quiet tails than at
 * the peak. Lukas read it as "all buses and trains slow down" in a jam.
 */

/** A shaped like a real round: 135 minutes there, 1000-minute tick budget, 135 back. */
const span = {
  endMin: 1135,
  morningEndMin: 135,
  homeStartMin: 1000,
};

describe("buildWarp", () => {
  it("always runs for the same length, whatever the round did", () => {
    const short = buildWarp({ endMin: 60, morningEndMin: 60, homeStartMin: null });
    const long = buildWarp(span);

    expect(short.durationSec).toBe(REPLAY_BUDGET_SEC);
    expect(long.durationSec).toBe(REPLAY_BUDGET_SEC);
  });

  it("starts at the beginning and holds the end", () => {
    const warp = buildWarp(span);

    expect(warp.simMinuteAt(0)).toBe(0);
    expect(warp.simMinuteAt(warp.durationSec)).toBe(1135);
  });

  it("never runs time backwards", () => {
    const warp = buildWarp(span);

    let previous = -1;
    for (let second = 0; second <= warp.durationSec; second += 0.1) {
      const minute = warp.simMinuteAt(second);
      expect(minute).toBeGreaterThanOrEqual(previous);
      previous = minute;
    }
  });

  it("runs the morning and the evening at the same rate", () => {
    const warp = buildWarp(span);
    const rateOver = (fromSec: number, toSec: number) =>
      (warp.simMinuteAt(toSec) - warp.simMinuteAt(fromSec)) / (toSec - fromSec);

    // Inside the morning, and inside the evening (the jump is `middaySec` long).
    const morning = rateOver(1, 20);
    const evening = rateOver(warp.beatFromSec - 20, warp.beatFromSec - 1);

    expect(morning).toBeCloseTo(evening, 6);
  });

  it("is constant inside the morning, however much moves", () => {
    // The point of the change: no minute of the morning is faster than another.
    const warp = buildWarp(span);

    const first = warp.simMinuteAt(10) - warp.simMinuteAt(9);
    const later = warp.simMinuteAt(40) - warp.simMinuteAt(39);

    expect(later).toBeCloseTo(first, 6);
  });

  it("jumps the middle of the day in the fixed time and says so", () => {
    const warp = buildWarp(span);

    let jumping = 0;
    for (let second = 0; second < warp.beatFromSec; second += 0.01) {
      if (warp.isMidday(second)) jumping += 0.01;
    }

    expect(jumping).toBeCloseTo(REPLAY_MIDDAY_SEC, 1);
    expect(warp.isMidday(1)).toBe(false);
    // Nothing of the day is skipped: the clock passes through the gap.
    let gapMinutes = 0;
    for (let second = 0.5; second < warp.beatFromSec; second += 0.5) {
      if (warp.isMidday(second)) gapMinutes += 1;
    }
    expect(gapMinutes).toBeGreaterThan(0);
  });

  it("has no midday for a round with no way home", () => {
    const warp = buildWarp({ endMin: 135, morningEndMin: 135, homeStartMin: null });

    for (let second = 0; second <= warp.durationSec; second += 0.5) {
      expect(warp.isMidday(second)).toBe(false);
    }
    expect(warp.simMinuteAt(warp.beatFromSec / 2)).toBeCloseTo(135 / 2, 5);
  });

  it("has no midday when the morning ran into the evening's start", () => {
    // Somebody still on the road when the pass's clock stopped: nothing to skip.
    const warp = buildWarp({ endMin: 2000, morningEndMin: 1000, homeStartMin: 1000 });

    for (let second = 0; second <= warp.durationSec; second += 0.5) {
      expect(warp.isMidday(second)).toBe(false);
    }
  });

  it("holds the last moment so the arrival can land", () => {
    const warp = buildWarp(span);

    expect(warp.isBeat(warp.durationSec - 0.1)).toBe(true);
    expect(warp.isBeat(warp.durationSec * 0.5)).toBe(false);
    expect(warp.simMinuteAt(warp.durationSec - 0.1)).toBe(1135);
  });

  it("survives a round that recorded nothing", () => {
    const warp = buildWarp({ endMin: 0, morningEndMin: 0, homeStartMin: null });

    expect(warp.durationSec).toBe(REPLAY_BUDGET_SEC);
    expect(warp.simMinuteAt(0)).toBe(0);
    expect(Number.isFinite(warp.simMinuteAt(warp.durationSec))).toBe(true);
  });
});

function dot(overrides: Partial<ReplayDot> & Pick<ReplayDot, "legs">): ReplayDot {
  return {
    id: 1,
    route: 1,
    agent: 1,
    line: null,
    mode: "car",
    wants: 0,
    pass: "out",
    end: "arrived",
    ...overrides,
  };
}

function replay(dots: ReplayDot[], extra: Partial<Replay> = {}): Replay {
  return {
    version: 2,
    people_per_dot: 10,
    tick_duration_min: 5,
    window_min: 120,
    end_min: 1135,
    home_start_min: 1000,
    dots,
    ...extra,
  };
}

describe("warpSpan", () => {
  it("ends the morning at the last person, not the last bus", () => {
    const person = dot({ legs: [["e", 1, 5, 130, 1]] });
    // A bus dispatching for as long as anybody needs it, far past the people.
    const bus = dot({ id: 2, route: null, line: "M1", mode: "bus", legs: [["e", 1, 0, 900, 1]] });

    expect(warpSpan(replay([person, bus])).morningEndMin).toBe(130);
  });

  it("does not let the evening end the morning", () => {
    const out = dot({ legs: [["e", 1, 5, 130, 1]] });
    const home = dot({ id: 3, pass: "home", legs: [["e", 2, 1005, 1100, 2]] });

    expect(warpSpan(replay([out, home])).morningEndMin).toBe(130);
  });

  it("falls back to the end of the recording when nobody is a person", () => {
    expect(warpSpan(replay([], { end_min: 80, home_start_min: null })).morningEndMin).toBe(80);
  });

  it("carries where the evening starts", () => {
    expect(warpSpan(replay([])).homeStartMin).toBe(1000);
  });
});
