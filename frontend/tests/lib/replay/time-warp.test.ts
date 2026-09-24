import { describe, expect, it } from "vitest";

import { buildWarp, REPLAY_BUDGET_SEC } from "@/lib/replay/time-warp";

/**
 * Two hours of simulated morning into about two minutes of screen time.
 *
 * The shape of a real round, measured in the dev DB: the peak sits around
 * sim-minute 50–100 and **half the run is a slow drain afterwards**. Playing
 * that at a constant rate spends a quarter of the budget on nothing happening,
 * which is why the warp is driven by how much is actually moving.
 *
 * Lukas's rule for the quiet stretch, verbatim: "we dont need to wait, when no
 * dots move. jsut a tinyu bit" — so the floor is strictly positive and a
 * silent minute still advances, visibly faster rather than skipped. The clock
 * on screen reads real time throughout, so the speed-up is something you see.
 */

/** A profile shaped like a real round: quiet, peak, long drain. */
function realisticProfile(): number[] {
  const profile: number[] = [];
  for (let minute = 0; minute < 220; minute++) {
    if (minute < 30) profile.push(0);
    else if (minute < 110) profile.push(300);
    else profile.push(20);
  }
  return profile;
}

describe("buildWarp", () => {
  it("always runs for the same length, whatever the round did", () => {
    // "it always takes 2 min, so tick rate is dynamic to that" — the budget is
    // the fixed thing and the simulated span is normalised into it. A round
    // that drained for four hours must not take twice as long to watch.
    const short = buildWarp(new Array(60).fill(100));
    const long = buildWarp(new Array(400).fill(100));

    expect(short.durationSec).toBe(REPLAY_BUDGET_SEC);
    expect(long.durationSec).toBe(REPLAY_BUDGET_SEC);
  });

  it("starts at the beginning and reaches the end", () => {
    const warp = buildWarp(realisticProfile());

    expect(warp.simMinuteAt(0)).toBe(0);
    expect(warp.simMinuteAt(warp.durationSec)).toBeCloseTo(220, 5);
  });

  it("never runs time backwards", () => {
    // Scrubbing and the rAF loop both assume a monotone mapping; a dip would
    // make dots jump back down their links.
    const warp = buildWarp(realisticProfile());

    let previous = -1;
    for (let second = 0; second <= warp.durationSec; second += 0.25) {
      const minute = warp.simMinuteAt(second);
      expect(minute).toBeGreaterThanOrEqual(previous);
      previous = minute;
    }
  });

  it("gives the busy stretch more screen time than the quiet one", () => {
    // The whole point. The peak is 80 simulated minutes and the drain is 110,
    // and the peak must still get the larger share of the budget.
    const warp = buildWarp(realisticProfile());

    const secondsFor = (fromMin: number, toMin: number) => {
      let from = 0;
      let to = 0;
      for (let second = 0; second <= warp.durationSec; second += 0.05) {
        const minute = warp.simMinuteAt(second);
        if (minute <= fromMin) from = second;
        if (minute <= toMin) to = second;
      }
      return to - from;
    };

    const peak = secondsFor(30, 110);
    const drain = secondsFor(110, 220);

    expect(peak).toBeGreaterThan(drain);
  });

  it("still advances through a stretch where nothing moves", () => {
    // A floor, not a skip: the class should see the clock run on, not a cut.
    const warp = buildWarp(new Array(120).fill(0));

    expect(warp.simMinuteAt(warp.durationSec / 2)).toBeGreaterThan(0);
    expect(warp.simMinuteAt(warp.durationSec)).toBeCloseTo(120, 5);
  });

  it("holds the last moment so the arrival can land", () => {
    // "just a tiny bit so people get 'ah, now everybody arrived'". The hold is
    // inside the budget, not added to it.
    const warp = buildWarp(realisticProfile());
    const endMin = 220;

    expect(warp.isBeat(warp.durationSec - 0.1)).toBe(true);
    expect(warp.isBeat(warp.durationSec * 0.5)).toBe(false);
    expect(warp.simMinuteAt(warp.durationSec - 0.1)).toBeCloseTo(endMin, 5);
  });

  it("survives a round that recorded nothing", () => {
    // An empty profile is a round where no dot ever moved — a map with one
    // walker, or a replay from before the recorder existed.
    const warp = buildWarp([]);

    expect(warp.durationSec).toBe(REPLAY_BUDGET_SEC);
    expect(warp.simMinuteAt(0)).toBe(0);
    expect(Number.isFinite(warp.simMinuteAt(warp.durationSec))).toBe(true);
  });
});
