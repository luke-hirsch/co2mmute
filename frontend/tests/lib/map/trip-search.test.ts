import { beforeAll, describe, expect, it, vi } from "vitest";

import { routeCommutes, searchTrip, toLeg } from "@/lib/map/trip-search";
import { findPath } from "@/utils/pathfinding";
import type { Commute } from "@/lib/map/trip-search";
import type { Edge, Node } from "@/types/mapTypes";
import type { ExtendedMapGraph, RouteSubmissionLeg } from "@/types/routeTypes";

import { buildGraph, raw } from "../../utils/shipped-map";

/**
 * Every commute a map offers, found the way the round screen finds one.
 *
 * `scripts/routes.mjs` hands these to `manage.py calibrate_map`, which plays
 * them through the simulation. So the shape is the move endpoint's, and a
 * commute that has no route in some mode says so in its place.
 */

const BASE = Math.max(
  0,
  raw.versions.findIndex((v) => v.base_version),
);
const CHOICE = { carOptimization: "time", ptOptimization: "fastest" } as const;

function isLeg(leg: unknown): leg is RouteSubmissionLeg {
  return typeof leg === "object" && leg !== null && "segments" in leg;
}

describe("every commute on the shipped map", () => {
  let commutes: Commute[];
  const graph = buildGraph(raw, BASE);
  const homes = graph.nodes.filter((n) => n.node_type.some((t) => t.name === "home"));
  const work = graph.nodes.filter((n) => n.node_type.some((t) => t.name === "workplace"));

  beforeAll(async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    commutes = await routeCommutes(graph, CHOICE);
    vi.restoreAllMocks();
  });

  it("is every home to every workplace, homes outer, in id order", () => {
    expect(homes.length).toBeGreaterThan(1);
    expect(work.length).toBeGreaterThan(1);
    expect(commutes).toHaveLength(homes.length * work.length);

    const pairs = commutes.map((c) => [c.home, c.workplace]);
    const sorted = [...pairs].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    expect(pairs).toEqual(sorted);
  });

  it("drives there from the door and back to it", () => {
    for (const commute of commutes) {
      const there = commute.there.car;
      const back = commute.back.car;
      if (!isLeg(there) || !isLeg(back)) throw new Error("no car route");

      expect(there.segments[0].start_node).toBe(commute.home);
      expect(there.segments.at(-1)!.end_node).toBe(commute.workplace);
      expect(back.segments[0].start_node).toBe(commute.workplace);
      expect(back.segments.at(-1)!.end_node).toBe(commute.home);
      expect(there.total_distance_m).toBeGreaterThan(0);
      for (const segment of [...there.segments, ...back.segments]) {
        expect(segment.mode).toBe("car");
      }
    }
  });

  it("rides public transport where a line goes", () => {
    const rides = commutes.filter((c) => isLeg(c.there.public));
    expect(rides.length).toBe(commutes.length);
    for (const commute of rides) {
      const modes = (commute.there.public as RouteSubmissionLeg).segments.map((s) => s.mode);
      expect(modes.some((m) => m === "bus" || m === "train")).toBe(true);
      expect(modes.every((m) => m === "walk" || m === "bus" || m === "train")).toBe(true);
    }
  });

  it("answers a walk over the cap with its reason, in its place", () => {
    const refused = commutes.filter((c) => !isLeg(c.there.walk));
    expect(refused.length).toBeGreaterThan(0);
    expect(refused.length).toBeLessThan(commutes.length);
    for (const commute of refused) {
      expect(commute.there.walk).toEqual({ error: expect.any(String) });
    }
  });
});

describe("one trip", () => {
  const A: Node = { id: 1, name: "A", x_position: 0, y_position: 0, node_type: [] };
  const B: Node = { id: 2, name: "B", x_position: 1, y_position: 0, node_type: [] };
  const street: Edge = {
    id: 10,
    name: "E",
    start_node: 1,
    end_node: 2,
    biking: true,
    walking: true,
    street_edge: { id: 10, speed_limit: 50, lanes: 1, dedicated_bus_lane: false },
  };
  const graph = {
    nodes: [A, B],
    edges: [street],
    bus_lines: [],
    train_lines: [],
    scale: 1000,
  } as unknown as ExtendedMapGraph;

  it("is the router the screen calls, with the screen's options", async () => {
    const own = await findPath(graph, 1, 2, "car", { optimization: "time", scale: 1000 });
    const shared = await searchTrip(graph, 1, 2, "car", CHOICE);
    expect(shared).toEqual(own);
    expect(toLeg(shared).segments.map((s) => s.edgeId)).toEqual([10]);
  });
});
