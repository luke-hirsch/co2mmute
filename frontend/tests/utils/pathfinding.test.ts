import { describe, expect, it } from "vitest";

import { findPath } from "@/utils/pathfinding";
import type { Edge, MapGraph, Node } from "@/types/mapTypes";

/**
 * The way home is a search of its own, and the graph it searches is directed.
 *
 * A two-way street is two edges; a one-way street is one, and nothing in the
 * router turns it round. That is what makes the way back from work something
 * other than the way there reversed — the case the round trip was built for, a
 * circle on a map with one-way streets, which the shipped Berlin map (every
 * edge has its reverse) never produces.
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

function graph(nodes: Node[], edges: Edge[]): MapGraph {
  return { nodes, edges } as MapGraph;
}

const A = node(1, 0, 0);
const B = node(2, 10, 0);
const C = node(3, 5, 8);

describe("the way home on a directed graph", () => {
  it("is a different route when the streets are one-way", async () => {
    // A → B → C → A, a ring. Home is A, work is C.
    const ring = graph(
      [A, B, C],
      [street(10, 1, 2), street(11, 2, 3), street(12, 3, 1)],
    );

    const there = await findPath(ring, 1, 3, "car");
    const back = await findPath(ring, 3, 1, "car");

    expect(there.success).toBe(true);
    expect(there.segments.map((s) => s.edgeId)).toEqual([10, 11]);
    expect(back.success).toBe(true);
    expect(back.segments.map((s) => s.edgeId)).toEqual([12]);
  });

  it("has no way home when the street only leads in", async () => {
    const deadEnd = graph([A, B], [street(10, 1, 2)]);

    const there = await findPath(deadEnd, 1, 2, "car");
    const back = await findPath(deadEnd, 2, 1, "car");

    expect(there.success).toBe(true);
    expect(back.success).toBe(false);
  });

  it("is the same streets the other way when every edge has its reverse", async () => {
    const twoWay = graph(
      [A, B],
      [street(10, 1, 2), street(11, 2, 1)],
    );

    const back = await findPath(twoWay, 2, 1, "car");

    expect(back.segments.map((s) => s.edgeId)).toEqual([11]);
  });
});
