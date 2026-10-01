/**
 * Last round's traffic, turned into something the map can draw.
 *
 * ### One source, not two
 *
 * `previous_round_traffic` rides along with the graph and is what "schnellste"
 * routes on: `StreetPerRound.speed_under_load`, which is the speed the run
 * actually measured (`EdgeState.mean_speed_kmh`, over cars only). The overlay is
 * computed from exactly those numbers, so what a player sees drawn and what the
 * router routed around cannot disagree.
 *
 * The alternative was `RoundTrafficHeatmapView`, which aggregates
 * `EdgeTrafficSnapshot` rows. It was rejected twice over: it would be a second
 * answer to one question — the bug class this project has been bitten by most —
 * and it averages snapshots that are themselves means, which is precisely what
 * `_update_street_speeds` was rewritten to stop doing.
 *
 * ### A ratio, not a hue ramp
 *
 * The number that comes out is 0 (ran at the limit) to 1 (stopped), and the map
 * spends it on **stroke weight and a step from ink towards the accent**
 * (`jamTint`, S24). A two-colour palette has no hue ramp, and the old
 * `getCongestionColor` green→yellow→orange→red was in open violation of the
 * rulebook — unused, because nothing ever passed it.
 *
 * ### What it is measured against
 *
 * Each street's own speed limit, never a network-wide default. `berlin_base_v2`
 * has 36 edges at Tempo 30; scoring them against 50 would draw every one of them
 * as congested while empty.
 */

import type { Edge } from "@/types/mapTypes";
import type { EdgeTrafficData } from "@/types/routeTypes";

/** How full a link ran last round: 0 free-flowing, 1 stopped. */
export type EdgeLoad = { edgeId: number; congestionRatio: number };

export function edgeLoads(
  edges: Edge[],
  traffic: EdgeTrafficData[] | undefined,
): EdgeLoad[] {
  if (!traffic?.length) return [];

  const speeds = new Map(traffic.map((row) => [row.edgeId, row.avgSpeedKmh]));
  const loads: EdgeLoad[] = [];

  for (const edge of edges) {
    const limit = edge.street_edge?.speed_limit;
    // No street under it, or a limit of zero: nothing to be slow against.
    if (!limit) continue;

    const observed = speeds.get(edge.id);
    // A link the round never reported is not a link that was empty and fast —
    // `_update_street_speeds` writes a row only for a link something crossed, so
    // absence means "nothing to say", not "free flow".
    if (observed === undefined) continue;

    // Clamped both ways. Desired speed is drawn per driver, so a mean slightly
    // over the limit is ordinary and must not come out negative.
    const ratio = Math.max(0, Math.min(1, 1 - observed / limit));
    loads.push({ edgeId: edge.id, congestionRatio: ratio });
  }

  return loads;
}

/**
 * How much of the accent a street takes on, 0 (ink) to 1 (full accent).
 *
 * Weight alone was too quiet — the difference between a street at 0.2 and one at
 * 0.5 is a pixel on a phone, and nobody could tell (S24). So a loaded street
 * also moves from ink towards the accent. **Not linear, on purpose**: a street
 * that lost a tenth of its speed is ordinary and stays ink, and by half its
 * speed the accent carries — the colour is for the streets worth looking at. The
 * accent is also the PT line's colour; a route is a continuous line from a home,
 * and an amber street with no line of its own is a jam, which a player tells
 * apart without being told.
 *
 * A smoothstep between 0.1 and 0.6, so there is no visible step at either end.
 */
export function jamTint(ratio: number): number {
  const t = Math.max(0, Math.min(1, (ratio - 0.1) / 0.5));
  return t * t * (3 - 2 * t);
}
