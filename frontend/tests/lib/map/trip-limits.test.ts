import { describe, expect, it } from "vitest";

import {
  MAX_BIKE_M,
  MAX_WALK_M,
  airDistanceM,
  exceedsModeLimit,
  modeLimitM,
} from "@/lib/map/trip-limits";
import type { Node } from "@/types/mapTypes";

/**
 * How far anybody is willing to go under their own power.
 *
 * Lukas, 2026-09-28: "5 km walking and 15 km bike, that is with both about one
 * hour. Anything beyond that is lunacy." Stored as two distances rather than as
 * the hour, so the numbers are the ones he named; at Berlin Mitte-West's own
 * speeds that is 60 minutes on foot and 45 on a bike.
 *
 * The same idea as `ptRouting`'s 2 km cap on the first and last mile, but on the
 * whole trip rather than one leg.
 */

const node = (id: number, x: number, y: number): Node => ({
  id,
  name: `n${id}`,
  x_position: x,
  y_position: y,
  node_type: [],
});

describe("the caps", () => {
  it("is 5 km on foot and 15 km on a bike", () => {
    expect(MAX_WALK_M).toBe(5000);
    expect(MAX_BIKE_M).toBe(15000);
  });

  it("is about an hour at the shipped map's own speeds", () => {
    // Berlin Mitte-West: walk_speed_kmh 5, bike_speed_kmh 20. The two are not
    // the same hour and are not meant to be — nobody holds 20 km/h door to
    // door, so the bike cap is deliberately the tighter of the two.
    expect((MAX_WALK_M / 1000 / 5) * 60).toBe(60);
    expect((MAX_BIKE_M / 1000 / 20) * 60).toBe(45);
  });

  it("caps nothing that carries its own price", () => {
    // A car and a PT trip are already priced in CO2, euros and minutes. The cap
    // exists for the two modes where the only argument against a three-hour
    // trip is that nobody would make it.
    expect(modeLimitM("car")).toBeNull();
    expect(modeLimitM("public")).toBeNull();
    expect(modeLimitM("walk")).toBe(MAX_WALK_M);
    expect(modeLimitM("bike")).toBe(MAX_BIKE_M);
  });
});

describe("exceedsModeLimit", () => {
  it("allows a trip exactly at the cap", () => {
    expect(exceedsModeLimit("walk", 5000)).toBe(false);
    expect(exceedsModeLimit("bike", 15000)).toBe(false);
  });

  it("refuses a metre past it", () => {
    expect(exceedsModeLimit("walk", 5001)).toBe(true);
    expect(exceedsModeLimit("bike", 15001)).toBe(true);
  });

  it("refuses the shipped map's median walk, which is 8.4 km", () => {
    // Measured over all 36 home/workplace pairs: shortest routed walk 4.8 km,
    // median 8.4, longest 11.5. So the cap refuses walking on 33 of 36 pairs —
    // this map has no walkable commute, and the game now says so instead of
    // offering a 101-minute walk.
    expect(exceedsModeLimit("walk", 8393)).toBe(true);
  });

  it("refuses nothing on a bike on this map, where the longest trip is 11.5 km", () => {
    expect(exceedsModeLimit("bike", 11516)).toBe(false);
  });

  it("never refuses a car or a PT trip, however long", () => {
    expect(exceedsModeLimit("car", 500_000)).toBe(false);
    expect(exceedsModeLimit("public", 500_000)).toBe(false);
  });
});

describe("airDistanceM", () => {
  it("is the straight line between two nodes, in metres", () => {
    // 3-4-5, times the map's metres-per-unit.
    expect(airDistanceM(node(1, 0, 0), node(2, 3, 4), 1000)).toBe(5000);
  });

  it("is zero between a node and itself", () => {
    expect(airDistanceM(node(1, 2, 2), node(1, 2, 2), 1000)).toBe(0);
  });

  it("is a lower bound on the routed distance, so it can gate before the pick", () => {
    // The gate has to be sound: it may only refuse a mode that could not have
    // worked. Berlin Mitte-West's detour factor runs 1.24 to 2.76 (median
    // 1.54), so air distance is well under the routed distance everywhere and
    // a mode refused on it was never reachable.
    const home = node(1, 0, 0);
    const work = node(2, 6, 0);
    expect(airDistanceM(home, work, 1000)).toBe(6000);
    expect(exceedsModeLimit("walk", airDistanceM(home, work, 1000))).toBe(true);
  });
});
