/**
 * How much of the class's morning is happening in each simulated minute.
 *
 * This is the only input to the time warp, and what counts as "happening" is the
 * whole decision:
 *
 * - **A dot counts from when it wanted to leave, not from when it got out.**
 *   The gap is the crowd at the front door, and a crowd growing outside a full
 *   street is the most explanatory thing in the round. Fast-forwarding past it
 *   would skip the finding the animation exists to show.
 * - **A dot counts until its last leg ends**, whatever the ending. Somebody still
 *   standing at a stop at the end of the clock is on screen and is the reason the
 *   beat card may not claim everybody arrived.
 * - **A line vehicle does not count.** Since `pt-service-period` a line
 *   dispatches for as long as anybody needs it, so buses roll to the end of the
 *   clock — counting them would make the drain look as busy as the peak and
 *   flatten the warp to a constant rate. The profile answers "how much of the
 *   *class's* morning is happening now"; an empty bus is the timetable.
 */

import { isVehicleDot, type Replay } from "@/lib/replay/types";

export type ActivityOptions = {
  /**
   * Count buses and trains as activity too. Off by default — see above. Here
   * because a PT-only map would otherwise produce a flat profile, and because
   * the reason it is off is a judgement rather than a fact.
   */
  includeVehicles?: boolean;
};

/**
 * One entry per simulated minute, from 0 to `ceil(end_min)`.
 *
 * The index IS the minute, which is what `buildWarp` assumes when no `endMin` is
 * passed to it.
 */
export function activityProfile(
  replay: Replay,
  options: ActivityOptions = {},
): number[] {
  const minutes = Math.max(0, Math.ceil(replay.end_min));
  if (minutes === 0) return [];

  // A difference array, so a dot on screen for two hours costs two additions
  // rather than a hundred and twenty.
  const delta = new Float64Array(minutes + 1);

  for (const dot of replay.dots) {
    if (!options.includeVehicles && isVehicleDot(dot)) continue;
    if (dot.legs.length === 0) continue;

    const onScreenFrom = Math.min(dot.wants, dot.legs[0][2]);
    const from = Math.max(0, Math.min(minutes, Math.floor(onScreenFrom)));
    const to = Math.max(0, Math.min(minutes, Math.ceil(dot.legs[dot.legs.length - 1][3])));
    if (to <= from) continue;

    delta[from] += 1;
    delta[to] -= 1;
  }

  const profile: number[] = new Array(minutes);
  let running = 0;
  for (let minute = 0; minute < minutes; minute++) {
    running += delta[minute];
    profile[minute] = running;
  }
  return profile;
}
