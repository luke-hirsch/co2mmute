/**
 * Two hours of simulated morning into about two minutes of screen time.
 *
 * Three rates get confused here, so to be explicit: `GameSession
 * .tick_duration_min` is a **physics** parameter and is not touched by any of
 * this; the recorder's sampling rate is an **observer**; and this module owns
 * the **playback** rate and only that.
 *
 * The budget is the fixed thing. A round is about 225 simulated minutes at the
 * defaults, but since `pt-service-period` removed the PT service cap a line
 * dispatches for as long as somebody needs it, so `end_min` varies by a factor
 * of six between rounds of the same game. Playback normalises to whatever the
 * round did rather than assuming a span — a round that drained for four hours
 * must not take twice as long to watch.
 *
 * ### Why the warp is driven by activity
 *
 * Measured on a real round in the dev DB: the peak sits around sim-minute
 * 50–100 and **half the run is a slow drain afterwards**. Playing that at a
 * constant rate spends a quarter of the budget on nothing happening. So the
 * budget is handed out in proportion to how many dots are actually moving in
 * each simulated minute.
 *
 * The floor is strictly positive, which is Lukas's rule for the quiet stretch:
 * "we don't need to wait when no dots move, just a tiny bit". A quiet minute
 * still advances, visibly faster — a speed-up you can see rather than a cut,
 * because the clock on screen reads simulated time throughout.
 */

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
 * The quiet minute's share of the busiest minute's screen time.
 *
 * At 0.15 an empty stretch runs about five times faster than the peak on a real
 * profile — fast enough to read as a fast-forward, slow enough that 30 minutes
 * of nothing still takes four seconds instead of a blink. Raising it flattens
 * the warp towards a constant rate; lowering it turns the drain into a cut.
 */
export const REPLAY_ACTIVITY_FLOOR_SHARE = 0.15;

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
};

export type WarpOptions = {
  /**
   * The round's own `end_min`. Defaults to the profile's length, which is what
   * the tests use and what a minute-indexed profile means anyway.
   */
  endMin?: number;
  budgetSec?: number;
  beatSec?: number;
};

/**
 * @param profile How many dots are moving in each simulated minute — index is
 *   the minute. `activityProfile()` builds it from a replay.
 */
export function buildWarp(
  profile: readonly number[],
  options: WarpOptions = {},
): Warp {
  const durationSec = options.budgetSec ?? REPLAY_BUDGET_SEC;
  const beatSec = Math.min(options.beatSec ?? REPLAY_BEAT_SEC, durationSec);
  const playSec = durationSec - beatSec;
  const endMin = options.endMin ?? profile.length;

  // A round that recorded nothing still needs a warp: the screen falls back to
  // the street fill and the clock has to run somewhere. One flat bucket.
  const buckets = Math.max(profile.length, 1);

  // Peak-relative rather than mean-relative, so the floor does not move when
  // the drain gets longer — it is the ratio between the quietest and the
  // busiest minute that the class sees, and that should not depend on how much
  // quiet there is.
  let peak = 0;
  for (const count of profile) peak = Math.max(peak, count);
  const floor = Math.max(peak * REPLAY_ACTIVITY_FLOOR_SHARE, 1);

  // Cumulative screen seconds and simulated minutes at every bucket boundary.
  // Buckets are equal in simulated time and unequal in screen time; that
  // inequality IS the warp.
  const secAt: number[] = [0];
  const minuteAt: number[] = [0];
  let total = 0;
  for (let i = 0; i < buckets; i++) total += floor + (profile[i] ?? 0);

  let cumulative = 0;
  for (let i = 0; i < buckets; i++) {
    cumulative += floor + (profile[i] ?? 0);
    secAt.push((playSec * cumulative) / total);
    minuteAt.push((endMin * (i + 1)) / buckets);
  }

  function simMinuteAt(second: number): number {
    // Also catches NaN, and gives an exact 0 at the start rather than a
    // rounding artefact — the first frame must not place anybody.
    if (!(second > 0)) return 0;
    if (second >= playSec) return endMin;

    // Binary search: the rAF loop calls this once per frame, not per dot, so
    // O(log n) is free and a cursor would only be state to get wrong.
    let low = 0;
    let high = buckets - 1;
    while (low < high) {
      const mid = (low + high) >> 1;
      if (second < secAt[mid + 1]) high = mid;
      else low = mid + 1;
    }

    const span = secAt[low + 1] - secAt[low];
    const within = span > 0 ? (second - secAt[low]) / span : 0;
    return minuteAt[low] + within * (minuteAt[low + 1] - minuteAt[low]);
  }

  return {
    durationSec,
    beatFromSec: playSec,
    endMin,
    simMinuteAt,
    isBeat: (second: number) => second >= playSec,
  };
}
