/**
 * A round, there and back, in about two minutes of screen time.
 *
 * Three rates get confused here, so to be explicit: `GameSession
 * .tick_duration_min` is a **physics** parameter and is not touched by any of
 * this; the recorder's sampling rate is an **observer**; and this module owns
 * the **playback** rate and only that.
 *
 * ### One clock for the morning, one for the evening, a jump between
 *
 * The recording holds two passes on one axis: the way to work from minute 0, the
 * way home from `home_start_min` (the pass's own tick budget, about 1000 minutes
 * in). Between them nothing moves — the model has no day, only two peaks. So the
 * gap is the one place time is spent fast: a short fixed "Mittag", and everything
 * else runs at **one constant rate**.
 *
 * It used to be handed out by how many dots were moving (F2b, replaced). That
 * made every dot — the trains too, whose link times the simulation holds
 * constant — run five to seven times faster in the quiet tails than at the peak,
 * and it read as "everything slows down when it jams". A dot's speed on screen
 * is now the same all morning, so a dot that crawls is a dot that crawls.
 *
 * The budget is the fixed thing. A round can drain for four hours or for one, so
 * playback normalises whatever the round did into the budget rather than
 * assuming a span.
 */

import { isVehicleDot, type Replay } from "@/lib/replay/types";

/** The whole animation, in seconds of screen time. Always. */
export const REPLAY_BUDGET_SEC = 120;

/**
 * The hold at the end, inside the budget and never added to it.
 *
 * "just a tiny bit so people get 'ah, now everybody arrived'". That pause is
 * also the pivot the evening commute would drop in on, the day it exists.
 */
export const REPLAY_BEAT_SEC = 6;

/**
 * The jump over the middle of the day, inside the budget and never added to it.
 * Long enough to read "Mittag" and see the clock run on, short enough that
 * nobody waits for it.
 */
export const REPLAY_MIDDAY_SEC = 5;

export type Warp = {
  /** Screen seconds, beat included. Always `REPLAY_BUDGET_SEC`. */
  durationSec: number;
  /** Where the hold at the end starts. */
  beatFromSec: number;
  /** The last simulated minute — what the beat holds at. */
  endMin: number;
  /** Simulated minute at a screen second. Monotone, exact at both ends. */
  simMinuteAt: (second: number) => number;
  /** True once playback has reached the hold. */
  isBeat: (second: number) => boolean;
  /** True while playback is jumping over the middle of the day. */
  isMidday: (second: number) => boolean;
};

export type WarpSpan = {
  /** The last simulated minute of the recording. */
  endMin: number;
  /**
   * Where the way to work is over: the last minute a *person* is still under
   * way. A line vehicle does not count — it dispatches for as long as anybody
   * needs it and would drag the morning to the end of the clock.
   */
  morningEndMin: number;
  /** `home_start_min`, or null for a round with no way home. */
  homeStartMin: number | null;
};

/**
 * Where the stretches of a recording are, read off its dots.
 *
 * The morning ends at the last leg of the last person of the way to work — a
 * person, not a line vehicle, for the reason on `WarpSpan`. A recording with no
 * person dot (a map that moved nobody) falls back to its own `end_min`.
 */
export function warpSpan(replay: Replay): WarpSpan {
  let morningEnd = 0;
  for (const dot of replay.dots) {
    if (dot.pass !== "out" || isVehicleDot(dot) || dot.legs.length === 0) continue;
    morningEnd = Math.max(morningEnd, dot.legs[dot.legs.length - 1][3]);
  }
  return {
    endMin: replay.end_min,
    morningEndMin: morningEnd > 0 ? morningEnd : replay.end_min,
    homeStartMin: replay.home_start_min,
  };
}

export type WarpOptions = {
  budgetSec?: number;
  beatSec?: number;
  middaySec?: number;
};

type Segment = {
  fromMin: number;
  toMin: number;
  fromSec: number;
  toSec: number;
};

export function buildWarp(span: WarpSpan, options: WarpOptions = {}): Warp {
  const durationSec = options.budgetSec ?? REPLAY_BUDGET_SEC;
  const beatSec = Math.min(options.beatSec ?? REPLAY_BEAT_SEC, durationSec);
  const playSec = durationSec - beatSec;
  const endMin = Math.max(span.endMin, 1);

  // A midday exists only when the evening starts after the morning is over. A
  // round whose morning ran into the evening's start (somebody still on the road
  // when the clock stopped) has no gap to jump, and is one stretch.
  const home = span.homeStartMin;
  const morningEnd = Math.min(Math.max(span.morningEndMin, 0), endMin);
  const hasMidday = home !== null && home > morningEnd && home < endMin;
  const middaySec = hasMidday
    ? Math.min(options.middaySec ?? REPLAY_MIDDAY_SEC, playSec / 2)
    : 0;

  const stretches: [number, number][] = hasMidday
    ? [
        [0, morningEnd],
        [home, endMin],
      ]
    : [[0, endMin]];
  const stretchMinutes = stretches.reduce((sum, [a, b]) => sum + (b - a), 0);
  const rate = stretchMinutes > 0 ? (playSec - middaySec) / stretchMinutes : 0;

  const segments: Segment[] = [];
  let second = 0;
  stretches.forEach(([fromMin, toMin], index) => {
    if (index === 1) {
      // The jump: from where the morning ended to where the evening starts.
      segments.push({
        fromMin: morningEnd,
        toMin: home as number,
        fromSec: second,
        toSec: second + middaySec,
      });
      second += middaySec;
    }
    const length = (toMin - fromMin) * rate;
    segments.push({ fromMin, toMin, fromSec: second, toSec: second + length });
    second += length;
  });

  const middayFrom = hasMidday ? segments[1].fromSec : Infinity;
  const middayTo = hasMidday ? segments[1].toSec : Infinity;

  function simMinuteAt(at: number): number {
    // Also catches NaN, and gives an exact 0 at the start rather than a
    // rounding artefact — the first frame must not place anybody.
    if (!(at > 0)) return 0;
    if (at >= playSec) return endMin;

    for (const segment of segments) {
      if (at < segment.toSec) {
        const length = segment.toSec - segment.fromSec;
        const within = length > 0 ? (at - segment.fromSec) / length : 0;
        return segment.fromMin + within * (segment.toMin - segment.fromMin);
      }
    }
    return endMin;
  }

  return {
    durationSec,
    beatFromSec: playSec,
    endMin,
    simMinuteAt,
    isBeat: (at: number) => at >= playSec,
    isMidday: (at: number) => at >= middayFrom && at < middayTo,
  };
}
