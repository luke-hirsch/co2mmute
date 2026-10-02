/**
 * Where one dot is at one simulated minute.
 *
 * The events the backend records carry one timestamp each — entering link N+1
 * *is* leaving link N — so `build_replay` pairs them into legs that join up
 * exactly. There is never a gap to invent a position for, which is why this
 * module interpolates and never guesses.
 *
 * Two of the six states are not bookkeeping:
 *
 * - **`waiting` is the queue at the front door.** `wants` is when this person
 *   wanted to leave and `legs[0]` is when the street had room for them; someone
 *   who wanted to go at 48 and got out at 55 stood at home for seven minutes.
 *   Drawing them along the link instead would put the jam in the wrong place,
 *   which is the specific lie the old heatmap told.
 * - **`riding` is not a position.** A rider aboard a vehicle *is* the vehicle,
 *   so the caller resolves it against the same replay. Drawing the rider and the
 *   bus as two dots at one point would say a bus with forty people is forty
 *   things on the street; the boarding story is told at the stop, not in transit.
 */

import type { ReplayDot, ReplayEnd } from "@/lib/replay/types";

export type ReplayPosition =
  /** Has not wanted to leave yet. Not on screen. */
  | { kind: "pending" }
  /**
   * Standing at their own front door because the street outside is full.
   * `nodeId` is null when the route's edges did not connect and no end of the
   * first link can be named, and then there is nowhere honest to draw them.
   */
  | { kind: "waiting"; nodeId: number | null }
  /** Crossing a link. `progress` runs 0 → 1 from `fromNode`. */
  | { kind: "edge"; edgeId: number; fromNode: number | null; progress: number }
  /** Standing at a node, waiting for a line. */
  | { kind: "node"; nodeId: number }
  /** Aboard vehicle `vehicleId` — its position is that dot's position. */
  | { kind: "riding"; vehicleId: number }
  /** Over. Not on screen, but the ending is what the beat card may claim. */
  | { kind: "done"; end: ReplayEnd };

/**
 * Where the last lookup for this dot stopped.
 *
 * Playback runs forward and legs are ordered, so the scan starts where it left
 * off. Without it, 500 dots at 60 fps is 30 000 leg comparisons a second for no
 * reason. It is an optimisation and nothing more: the answer never depends on
 * it, including when the user scrubs backwards.
 */
export type ReplayCursor = { leg: number };

export function makeCursor(): ReplayCursor {
  return { leg: 0 };
}

export function positionAt(
  dot: ReplayDot,
  minute: number,
  cursor: ReplayCursor,
): ReplayPosition {
  const legs = dot.legs;
  if (legs.length === 0) return { kind: "done", end: dot.end };

  if (minute < dot.wants) return { kind: "pending" };

  const first = legs[0];
  if (minute < first[2]) {
    // The door queue. The first link's entry node is the door; an "s" first leg
    // (a rider whose trip starts at a stop) names the node outright.
    const nodeId = first[0] === "e" ? first[4] : first[0] === "s" ? first[1] : null;
    return { kind: "waiting", nodeId };
  }

  const last = legs[legs.length - 1];
  if (minute >= last[3]) return { kind: "done", end: dot.end };

  let index = Math.min(Math.max(cursor.leg, 0), legs.length - 1);
  while (index > 0 && minute < legs[index][2]) index--;
  while (index < legs.length - 1 && minute >= legs[index][3]) index++;
  cursor.leg = index;

  const [kind, ref, from, to, fromNode] = legs[index];

  if (kind === "s") return { kind: "node", nodeId: ref };
  if (kind === "r") return { kind: "riding", vehicleId: ref };

  const span = to - from;
  const progress = span > 0 ? (minute - from) / span : 0;
  return {
    kind: "edge",
    edgeId: ref,
    fromNode,
    progress: progress < 0 ? 0 : progress > 1 ? 1 : progress,
  };
}

/**
 * Every dot's cursor, by dot id.
 *
 * One map for the whole replay rather than one per dot, so a scrub can reset the
 * lot in a line.
 */
export function makeCursors(dots: readonly ReplayDot[]): Map<number, ReplayCursor> {
  const cursors = new Map<number, ReplayCursor>();
  for (const dot of dots) cursors.set(dot.id, makeCursor());
  return cursors;
}

/** Rewind every cursor. Called when playback jumps backwards. */
export function resetCursors(cursors: Map<number, ReplayCursor>): void {
  for (const cursor of cursors.values()) cursor.leg = 0;
}
