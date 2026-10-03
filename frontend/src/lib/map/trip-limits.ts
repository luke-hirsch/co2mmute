/**
 * How far anybody is willing to go under their own power.
 *
 * Lukas, 2026-09-28: **"5 km walking and 15 km bike, that is with both about one
 * hour. Anything beyond that is lunacy."**
 *
 * Two distances rather than one hour, so the numbers are the ones he named. At
 * Berlin Mitte-West's own speeds (`walk_speed_kmh` 5, `bike_speed_kmh` 20) that
 * is 60 minutes on foot and 45 on a bike — not the same hour, and not meant to
 * be: nobody holds 20 km/h door to door, so the bike cap is the tighter of the
 * two on purpose. The cost of storing distances is that they do not follow a map
 * with different speeds; a map that needs different numbers gets them here.
 *
 * ### Why a cap at all, when the clock already prices it
 *
 * The same reason `ptRouting` caps the first and last mile at 2 km: a routed
 * answer that nobody would act on is not an answer. The difference is that this
 * one is on the whole trip rather than one leg.
 *
 * ### What it does to the shipped map
 *
 * Measured over all 36 home/workplace pairs, in every version: the shortest
 * routed walk is 2.75 km, the median 5.4, the longest 10.0. So the walk cap
 * refuses **22 of 36** and leaves 14 walkable — the three Bellevue homes to
 * Brandenburger Tor, Lützowplatz, TU Berlin and Hegelplatz, and two to
 * Lützowplatz from the south. Before the Tiergarten paths (F11) it refused 33
 * and the map had no walkable commute. The bike cap refuses **none of them**,
 * and is a guard for a map that has not been drawn yet.
 *
 * ### Two places it is checked, and why both
 *
 * `airDistanceM` gates **before** the pick, so a mode that cannot work is not
 * offered; the routed distance is the real cap and refuses the rest. The air
 * gate has to be sound rather than complete — it may only refuse a mode that
 * could not have worked — and it is, because the straight line is a lower bound
 * on any route. On this map it catches 14 of the 22 walk refusals and the router
 * catches the other 8; the detour factor runs 1.06 to 1.54, so nothing tighter
 * would be safe.
 */

import type { Node } from "@/types/mapTypes";
import type { TransportMode } from "@/types/routeTypes";

/** An hour on foot at 5 km/h. */
export const MAX_WALK_M = 5000;

/** 45 minutes on a bike at 20 km/h — the tighter of the two, deliberately. */
export const MAX_BIKE_M = 15000;

/**
 * The cap for a mode, or null where there is none.
 *
 * A car and a PT trip are already priced in CO₂, euros and minutes, and those
 * are the currencies the class argues in. The cap exists only for the two modes
 * where the sole argument against a three-hour trip is that nobody would make
 * it.
 */
export function modeLimitM(mode: TransportMode): number | null {
  switch (mode) {
    case "walk":
      return MAX_WALK_M;
    case "bike":
      return MAX_BIKE_M;
    default:
      return null;
  }
}

/** Whether a trip of this length is past what the mode allows. */
export function exceedsModeLimit(mode: TransportMode, distanceM: number): boolean {
  const limit = modeLimitM(mode);
  return limit !== null && distanceM > limit;
}

/**
 * The straight line between two nodes, in metres.
 *
 * What real life gives you before you have chosen anything: you know roughly how
 * far away the place is, and nothing about the route. `scale` is the map's
 * metres per coordinate unit.
 */
export function airDistanceM(a: Node, b: Node, scale: number): number {
  const dx = b.x_position - a.x_position;
  const dy = b.y_position - a.y_position;
  return Math.sqrt(dx * dx + dy * dy) * scale;
}
