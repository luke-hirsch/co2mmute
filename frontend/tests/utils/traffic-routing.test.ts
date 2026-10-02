import { describe, expect, it } from "vitest";

import { calculateEdgeWeight, findPath } from "@/utils/pathfinding";
import type { Edge, MapGraph, Node } from "@/types/mapTypes";
import type { EdgeTrafficData } from "@/types/routeTypes";

/**
 * Last round's jam, and whether the router goes round it.
 *
 * "schnellste" read `previous_round_traffic` from the start. "klimafreundlichste"
 * took the speed from it only under `optimization === "time"`, so it always
 * routed at the speed limit — although the simulation's CO2 depends on the speed
 * a link actually ran at. The factors pinned below are the backend's curve
 * (`sim/constants.py:car_emissions_g_per_km`, relative to its value at 50 km/h),
 * not the old three-step function.
 */

function node(id: number, x: number, y: number): Node {
  return { id, name: `N${id}`, x_position: x, y_position: y, node_type: [] };
}

function street(id: number, start: number, end: number): Edge {
  return {
    id,
    name: `E${id}`,
    start_node: start,
    end_node: end,
    biking: true,
    walking: true,
    street_edge: { id, speed_limit: 50, lanes: 1, dedicated_bus_lane: false },
  };
}

function jam(edgeId: number, avgSpeedKmh: number): EdgeTrafficData {
  return { edgeId, avgSpeedKmh, congestionLevel: "high" };
}

// A → B direct is 1000 m. A → C → B is 1886 m: the way round that a jam on the
// direct street makes worth taking.
const A = node(1, 0, 0);
const B = node(2, 10, 0);
const C = node(3, 5, 8);
const direct = street(10, 1, 2);
const roundAbout = graphOf([street(11, 1, 3), street(12, 3, 2)]);

function graphOf(extra: Edge[]): MapGraph {
  return { nodes: [A, B, C], edges: [direct, ...extra] } as MapGraph;
}

describe("a jam changes the route", () => {
  it("for the fastest route", async () => {
    const result = await findPath(roundAbout, 1, 2, "car", {
      optimization: "time",
      trafficData: [jam(10, 8)],
    });

    expect(result.segments.map((s) => s.edgeId)).toEqual([11, 12]);
  });

  it("for the climate-friendliest route", async () => {
    const result = await findPath(roundAbout, 1, 2, "car", {
      optimization: "co2",
      trafficData: [jam(10, 8)],
    });

    expect(result.segments.map((s) => s.edgeId)).toEqual([11, 12]);
  });

  it("not for the shortest route, which never cared", async () => {
    const result = await findPath(roundAbout, 1, 2, "car", {
      optimization: "distance",
      trafficData: [jam(10, 8)],
    });

    expect(result.segments.map((s) => s.edgeId)).toEqual([10]);
  });

  it("not when the street ran at its limit", async () => {
    const result = await findPath(roundAbout, 1, 2, "car", {
      optimization: "co2",
      trafficData: [jam(10, 50)],
    });

    expect(result.segments.map((s) => s.edgeId)).toEqual([10]);
  });
});

describe("the CO2 weight is the simulation's curve", () => {
  const weightAt = (speed: number | undefined) =>
    calculateEdgeWeight(
      direct,
      A,
      B,
      "car",
      "co2",
      speed === undefined ? undefined : [jam(10, speed)],
    )! / 1000; // distance is 1000 m, so this is the factor

  it.each([
    [50, 1.0],
    [30, 1.1294],
    [20, 1.3169],
    [10, 1.9],
    [70, 0.9739],
  ])("at %i km/h the factor is %f", (speed, factor) => {
    expect(weightAt(speed)).toBeCloseTo(factor, 3);
  });

  it("is capped at twice the free-flow figure, like the backend's", () => {
    expect(weightAt(5)).toBeCloseTo(2.0, 6);
    expect(weightAt(1)).toBeCloseTo(2.0, 6);
  });

  it("is 1 on a street no traffic row mentions", () => {
    expect(weightAt(undefined)).toBeCloseTo(1.0, 6);
  });
});
