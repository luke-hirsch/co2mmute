import { describe, expect, it } from "vitest";

import { edgeLoads, jamTint } from "@/lib/map/traffic";
import type { Edge } from "@/types/mapTypes";
import type { EdgeTrafficData } from "@/types/routeTypes";

/**
 * Last round's traffic, turned into something drawable.
 *
 * One source, deliberately: `previous_round_traffic` is what "schnellste" routes
 * on, so the overlay is computed from the same numbers rather than from
 * `RoundTrafficHeatmapView`. Two endpoints answering "how bad was this street"
 * is the two-sources-of-truth shape this project has been bitten by, and the
 * aggregate one averages snapshots — which is the thing `_update_street_speeds`
 * was changed to stop doing.
 */

const edge = (id: number, speedLimit: number | null): Edge => ({
  id,
  name: "",
  start_node: 1,
  end_node: 2,
  biking: true,
  walking: true,
  bike_lane: false,
  street_edge:
    speedLimit === null
      ? null
      : { id, speed_limit: speedLimit, lanes: 2, dedicated_bus_lane: false },
  train_edge: null,
});

const traffic = (edgeId: number, avgSpeedKmh: number): EdgeTrafficData => ({
  edgeId,
  avgSpeedKmh,
  congestionLevel: "low",
});

describe("edgeLoads", () => {
  it("is zero on a street that ran at its limit", () => {
    expect(edgeLoads([edge(1, 50)], [traffic(1, 50)])).toEqual([
      { edgeId: 1, congestionRatio: 0 },
    ]);
  });

  it("is the share of the limit that was lost", () => {
    // 20 km/h in a 50 zone: three fifths of the speed gone.
    const [load] = edgeLoads([edge(1, 50)], [traffic(1, 20)]);
    expect(load.congestionRatio).toBeCloseTo(0.6, 5);
  });

  it("measures a Tempo-30 street against 30, not against 50", () => {
    // `berlin_base_v2` has 36 edges at 30. Scoring them against a network-wide
    // 50 would paint every one of them as congested while empty.
    const [load] = edgeLoads([edge(1, 30)], [traffic(1, 30)]);
    expect(load.congestionRatio).toBe(0);
  });

  it("clamps a street that ran faster than its limit", () => {
    // The measured mean is over drivers whose desired speed is drawn per person,
    // so somebody doing 55 in a 50 is ordinary and must not read as -0.1.
    const [load] = edgeLoads([edge(1, 50)], [traffic(1, 60)]);
    expect(load.congestionRatio).toBe(0);
  });

  it("clamps a stopped street at one", () => {
    const [load] = edgeLoads([edge(1, 50)], [traffic(1, 0)]);
    expect(load.congestionRatio).toBe(1);
  });

  it("skips a link with no street under it", () => {
    // A path carries no speed limit, so there is nothing to be slow against.
    expect(edgeLoads([edge(1, null)], [traffic(1, 4)])).toEqual([]);
  });

  it("skips a street the round never reported", () => {
    // `_update_street_speeds` writes a row only for a link something drove on,
    // and a link nobody used is not a link that was empty-and-fast — it is a
    // link with nothing to say.
    expect(edgeLoads([edge(1, 50), edge(2, 50)], [traffic(1, 25)])).toHaveLength(1);
  });

  it("skips traffic for an edge that is not in this version of the map", () => {
    // The graph is one version; the traffic is the last round's, which may have
    // been driven on another. An edge the vote removed has nowhere to be drawn.
    expect(edgeLoads([edge(1, 50)], [traffic(99, 10)])).toEqual([]);
  });

  it("is empty when there is no traffic at all — round one", () => {
    expect(edgeLoads([edge(1, 50)], [])).toEqual([]);
    expect(edgeLoads([edge(1, 50)], undefined)).toEqual([]);
  });
});

describe("jamTint", () => {
  it("leaves a free street in ink", () => {
    expect(jamTint(0)).toBe(0);
    expect(jamTint(0.1)).toBe(0);
  });

  it("is the full accent on a standstill", () => {
    expect(jamTint(1)).toBe(1);
  });

  it("only ever rises", () => {
    let last = -1;
    for (let r = 0; r <= 1.0001; r += 0.05) {
      const tint = jamTint(r);
      expect(tint).toBeGreaterThanOrEqual(last);
      last = tint;
    }
  });

  it("is not linear: half the loss is already mostly accent", () => {
    // A street at half speed is a street people should see. A linear ramp
    // would leave it half ink.
    expect(jamTint(0.5)).toBeGreaterThan(0.6);
  });

  it("clamps what the ratio cannot be", () => {
    expect(jamTint(-1)).toBe(0);
    expect(jamTint(3)).toBe(1);
  });
});
