/**
 * The two numbers the replay says in words: what one dot is worth, and who did
 * not get there.
 *
 * ### Who did not get there is counted, not sampled
 *
 * The dots are a sample, and the sample cannot see everybody who missed the
 * morning: people still at their own front door when the clock stopped never
 * became vehicles, so no dot exists for any of them. On the shipped map nobody
 * misses the morning at all — every measured round is over by minute ~135 of a
 * 1000-minute clock — but where somebody does, the closing sentence must not say
 * "Alle sind angekommen". So since S25 the simulator writes its own count into
 * the recording (`replay.endings`, people), and a recording from before falls
 * back to the sample.
 *
 * ### A dot is a whole number of people
 *
 * `people_per_dot` is the ratio as sampled (205 people at a stride of ten are 21
 * dots of 9.76), because crowds at a stop are multiplied by it. Printed, it is a
 * whole number of people, and never fewer than one.
 */

import type { Replay, ReplayEndings } from "@/lib/replay/types";

export function replayEndings(replay: Replay): ReplayEndings {
  if (replay.endings) return replay.endings;

  let unfinished = 0;
  let stranded = 0;
  for (const dot of replay.dots) {
    if (dot.line !== null) continue;
    if (dot.end === "unfinished") unfinished += 1;
    if (dot.end === "stranded") stranded += 1;
  }
  return {
    unfinished: Math.round(unfinished * replay.people_per_dot),
    stranded: Math.round(stranded * replay.people_per_dot),
  };
}

export function dotScale(replay: Replay): number {
  return Math.max(1, Math.round(replay.people_per_dot));
}
