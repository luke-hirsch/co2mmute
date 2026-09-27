/**
 * The street layer: how full each link was, and who was still at their front door.
 *
 * The dots are a sample — one stands for `people_per_dot` — and the street fill is
 * the whole population, counted by the simulator itself. So the two layers are
 * drawn differently on purpose: the fill is the link's weight, the dots are faces
 * you can follow, and the caption under the map says what a dot is worth.
 *
 * ### Where a tick sits on the clock
 *
 * `_advance_traffic()` runs tick `t` over `[t·d, (t+1)·d)` and the snapshot is
 * taken **after** it, so a row labelled `t` is the state at minute `(t+1)·d`.
 * Getting that off by one tick would show a jam forming five minutes before the
 * cars that cause it.
 *
 * ### Missing is empty, not unknown
 *
 * `_record_edge_traffic` writes a row only for a link with a queue, a traversal
 * or somebody held at its door. So an edge absent from a tick carried nothing,
 * and a gap between two of an edge's rows is genuinely quiet — interpolating
 * straight across it would invent traffic that never existed. Hence the dense
 * per-tick array with zeros in the gaps, and the ramp from zero into the first
 * row and out of the last one.
 *
 * ### Why `waiting_count` goes on the node
 *
 * Those people are not on the link yet: they are standing at their own front door
 * because the street outside is full. `stau-sichtbar` is the whole finding —
 * `queued_edges` read 0 and the snapshot read one vehicle at free flow while the
 * mean car delay was sixty minutes. Drawing them along the edge would put the jam
 * in the wrong place, which is the specific lie the old heatmap told.
 */

import type { ReplayDot, ReplayTick } from "@/lib/replay/types";

export type EdgeFill = {
  /** Vehicles on the link. A car is one, a bus is one with forty people in it. */
  vehicles: number;
  /** People held at the link's front door — drawn at the node, never on the link. */
  waiting: number;
  /**
   * Mean speed over cars only, as the simulator measured it.
   *
   * Held rather than interpolated towards zero outside the recorded range: an
   * empty street is not a street at 0 km/h. Never drawn as a colour — congestion
   * is dots that have stopped.
   */
  speedKmh: number;
};

export type StreetFill = {
  /** Every link that ever carried anything, in the order the payload had them. */
  edgeIds: number[];
  /** The busiest single sample anywhere, for scaling stroke weight. */
  peakVehicles: number;
  /** The largest front-door crowd anywhere, for scaling the node marks. */
  peakWaiting: number;
  /** The minute the last row describes. */
  lastSampleMin: number;
  fillAt: (edgeId: number, simMinute: number) => EdgeFill;
};

const EMPTY: EdgeFill = { vehicles: 0, waiting: 0, speedKmh: 0 };

/** One link's dense per-tick samples, three numbers per tick. */
type EdgeSamples = {
  /** `vehicles, waiting, speedKmh` per tick, tick 0 first. */
  values: Float64Array;
  /** Whether tick `k` has a row at all — a zero row and a missing row differ for speed. */
  present: Uint8Array;
};

export function buildStreetFill(
  ticks: readonly ReplayTick[],
  tickDurationMin: number,
): StreetFill {
  const duration = tickDurationMin > 0 ? tickDurationMin : 1;

  let maxTick = 0;
  for (const tick of ticks) maxTick = Math.max(maxTick, tick.t);
  const tickCount = ticks.length === 0 ? 0 : maxTick + 1;

  const byEdge = new Map<number, EdgeSamples>();
  const edgeIds: number[] = [];
  let peakVehicles = 0;
  let peakWaiting = 0;

  for (const tick of ticks) {
    for (const [edgeId, vehicles, waiting, speedKmh] of tick.edges) {
      let samples = byEdge.get(edgeId);
      if (!samples) {
        samples = {
          values: new Float64Array(tickCount * 3),
          present: new Uint8Array(tickCount),
        };
        byEdge.set(edgeId, samples);
        edgeIds.push(edgeId);
      }
      const base = tick.t * 3;
      samples.values[base] = vehicles;
      samples.values[base + 1] = waiting;
      samples.values[base + 2] = speedKmh;
      samples.present[tick.t] = 1;
      if (vehicles > peakVehicles) peakVehicles = vehicles;
      if (waiting > peakWaiting) peakWaiting = waiting;
    }
  }

  /** A link's value at an integer tick, treating a missing row as empty. */
  function at(samples: EdgeSamples, tick: number, slot: number): number {
    if (tick < 0 || tick >= tickCount) return 0;
    return samples.values[tick * 3 + slot];
  }

  /** The nearest recorded speed, so an unsampled minute reports free flow, not a stop. */
  function speedNear(samples: EdgeSamples, rawTick: number): number {
    // Clamp before searching: a minute past the end of the recording is nearest
    // to the last tick, and an unclamped scan from there walks off the array.
    const tick = Math.min(Math.max(rawTick, 0), tickCount - 1);
    for (let offset = 0; offset <= tickCount; offset++) {
      const before = tick - offset;
      if (before >= 0 && before < tickCount && samples.present[before]) {
        return samples.values[before * 3 + 2];
      }
      const after = tick + offset;
      if (after >= 0 && after < tickCount && samples.present[after]) {
        return samples.values[after * 3 + 2];
      }
    }
    return 0;
  }

  function fillAt(edgeId: number, simMinute: number): EdgeFill {
    const samples = byEdge.get(edgeId);
    if (!samples || tickCount === 0) return EMPTY;

    // Fractional tick index. Tick k describes minute (k+1)·d, so minute 0 sits
    // one whole tick before the first row and the fill ramps up out of nothing.
    const position = simMinute / duration - 1;
    const lower = Math.floor(position);
    const within = position - lower;

    const vehicles =
      at(samples, lower, 0) +
      within * (at(samples, lower + 1, 0) - at(samples, lower, 0));
    const waiting =
      at(samples, lower, 1) +
      within * (at(samples, lower + 1, 1) - at(samples, lower, 1));

    return {
      vehicles: vehicles < 0 ? 0 : vehicles,
      waiting: waiting < 0 ? 0 : waiting,
      speedKmh: speedNear(samples, within < 0.5 ? lower : lower + 1),
    };
  }

  return {
    edgeIds,
    peakVehicles,
    peakWaiting,
    lastSampleMin: tickCount === 0 ? 0 : maxTick * duration + duration,
    fillAt,
  };
}

/**
 * Which node each link's front-door queue is standing at, learned from the dots.
 *
 * `waiting_count` is recorded per link and carries no direction — the simulator
 * holds a person at `route_segments[0].edge_id` and the graph stores that edge in
 * whichever direction it was drawn. But a dot's first leg names the node it left
 * from, so the sample tells us what the aggregate cannot.
 *
 * A street that is the first link of routes from both ends is genuinely ambiguous;
 * the majority wins, and the caller falls back to the edge's own `start_node` for
 * a link no dot ever left from.
 */
export function doorNodeByEdge(dots: readonly ReplayDot[]): Map<number, number> {
  const counts = new Map<number, Map<number, number>>();

  for (const dot of dots) {
    if (dot.line !== null) continue;
    const first = dot.legs[0];
    if (!first || first[0] !== "e" || first[4] === null) continue;

    let perNode = counts.get(first[1]);
    if (!perNode) {
      perNode = new Map<number, number>();
      counts.set(first[1], perNode);
    }
    perNode.set(first[4], (perNode.get(first[4]) ?? 0) + 1);
  }

  const doors = new Map<number, number>();
  for (const [edgeId, perNode] of counts) {
    let best = -1;
    let bestCount = -1;
    for (const [nodeId, count] of perNode) {
      if (count > bestCount) {
        best = nodeId;
        bestCount = count;
      }
    }
    doors.set(edgeId, best);
  }
  return doors;
}

/**
 * The front-door crowds, summed onto the nodes they are standing at.
 *
 * `doorNodeOf` returning null drops that link's crowd rather than guessing where
 * it is. Losing a mark is a smaller lie than drawing a jam on the wrong street.
 */
export function waitingByNode(
  fill: StreetFill,
  simMinute: number,
  doorNodeOf: (edgeId: number) => number | null | undefined,
): Map<number, number> {
  const byNode = new Map<number, number>();

  for (const edgeId of fill.edgeIds) {
    const waiting = fill.fillAt(edgeId, simMinute).waiting;
    if (waiting <= 0) continue;
    const nodeId = doorNodeOf(edgeId);
    if (nodeId === null || nodeId === undefined) continue;
    byNode.set(nodeId, (byNode.get(nodeId) ?? 0) + waiting);
  }

  return byNode;
}
