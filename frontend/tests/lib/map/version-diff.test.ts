import { describe, expect, it } from "vitest";

import { diffGraphs, linkEntries } from "@/lib/map/version-diff";
import type { Edge, Node } from "@/types/mapTypes";
import type { ExtendedMapGraph, PTLine } from "@/types/routeTypes";

import { buildGraph, raw } from "../../utils/shipped-map";

/**
 * What one map version changes against another, read off the two graphs.
 *
 * A version is a filter over one shared graph, and a change to a street is
 * stored as a **clone**: `Busspuren` holds a second row for each of its streets
 * and leaves the original to base. So the edge ids of two versions differ on
 * every street a change touched, and a line's chain moves onto the clones with
 * them. Compared by id, `Busspuren` reads as thirty streets removed, thirty
 * added and four lines rerouted — none of which is what it does. The diff
 * compares links by their node pair and lines by the links they run over.
 */

const node = (id: number, x = id, y = 0): Node => ({
  id,
  name: `Knoten ${id}`,
  x_position: x,
  y_position: y,
  node_type: [],
});

type StreetFields = Partial<NonNullable<Edge["street_edge"]>>;

const street = (
  id: number,
  start: number,
  end: number,
  fields: StreetFields & Partial<Edge> = {},
): Edge => {
  const { speed_limit = 50, lanes = 2, dedicated_bus_lane = false, ...rest } =
    fields;
  return {
    id,
    name: "",
    start_node: start,
    end_node: end,
    biking: true,
    walking: true,
    bike_lane: false,
    street_edge: { id, speed_limit, lanes, dedicated_bus_lane },
    train_edge: null,
    ...rest,
  };
};

const rail = (id: number, start: number, end: number): Edge => ({
  id,
  name: "",
  start_node: start,
  end_node: end,
  biking: false,
  walking: false,
  bike_lane: false,
  street_edge: null,
  train_edge: { id },
});

const path = (id: number, start: number, end: number): Edge => ({
  id,
  name: "",
  start_node: start,
  end_node: end,
  biking: true,
  walking: true,
  bike_lane: false,
  street_edge: null,
  train_edge: null,
});

const bus = (id: number, name: string, edges: number[]): PTLine => ({
  id,
  name,
  type: "bus",
  interval: 10,
  capacity: 85,
  speed_kmh: 30,
  edges,
  stops: [],
});

const graph = (
  nodes: Node[],
  edges: Edge[],
  bus_lines: PTLine[] = [],
  train_lines: PTLine[] = [],
): ExtendedMapGraph => ({
  map_id: 1,
  version_id: 1,
  version_name: "",
  nodes,
  edges,
  node_count: nodes.length,
  edge_count: edges.length,
  bus_lines,
  train_lines,
  scale: 1,
});

const NODES = [node(1), node(2), node(3), node(4)];

describe("diffGraphs on a toy map", () => {
  it("finds nothing between a graph and itself", () => {
    const g = graph(NODES, [street(1, 1, 2), street(2, 2, 3)], [bus(1, "A", [1, 2])]);
    const diff = diffGraphs(g, g);
    expect(diff.links).toEqual([]);
    expect(diff.lines).toEqual([]);
    expect(diff.nodes).toEqual([]);
    expect(diff.empty).toBe(true);
  });

  it("reads a cloned street as the street it is, not as one removed and one added", () => {
    const before = graph(NODES, [street(1, 1, 2)]);
    const after = graph(NODES, [street(9, 1, 2, { dedicated_bus_lane: true })]);

    const diff = diffGraphs(before, after);

    expect(diff.links).toHaveLength(1);
    expect(diff.links[0]).toMatchObject({
      start: 1,
      end: 2,
      network: "pt",
      sense: "added",
      aspects: [{ kind: "busLane" }],
    });
  });

  it("calls a bus lane going away a removal, in the PT colour", () => {
    const before = graph(NODES, [street(9, 1, 2, { dedicated_bus_lane: true })]);
    const after = graph(NODES, [street(1, 1, 2)]);

    expect(diffGraphs(before, after).links).toEqual([
      expect.objectContaining({
        network: "pt",
        sense: "removed",
        aspects: [{ kind: "busLane" }],
      }),
    ]);
  });

  it("a new street is the street network's, with what it is", () => {
    const before = graph(NODES, [street(1, 1, 2)]);
    const after = graph(NODES, [
      street(1, 1, 2),
      street(2, 2, 3, { lanes: 1, speed_limit: 30 }),
    ]);

    expect(diffGraphs(before, after).links).toEqual([
      expect.objectContaining({
        start: 2,
        end: 3,
        network: "street",
        sense: "added",
        aspects: [{ kind: "street", lanes: 1, speedLimit: 30 }],
      }),
    ]);
  });

  it("a link that goes is drawn where the old graph had it", () => {
    const before = graph([node(1, 0, 0), node(2, 5, 7)], [street(1, 1, 2)]);
    const after = graph([node(1, 0, 0), node(2, 5, 7)], []);

    const [link] = diffGraphs(before, after).links;
    expect(link).toMatchObject({
      network: "street",
      sense: "removed",
      a: { x: 0, y: 0 },
      b: { x: 5, y: 7 },
    });
  });

  it("a new railway alignment is the PT network's", () => {
    const before = graph(NODES, []);
    const after = graph(NODES, [rail(1, 1, 2)]);

    expect(diffGraphs(before, after).links).toEqual([
      expect.objectContaining({ network: "pt", sense: "added", aspects: [{ kind: "rail" }] }),
    ]);
  });

  it("a new path says who may use it", () => {
    const before = graph(NODES, []);
    const after = graph(NODES, [path(1, 1, 2)]);

    expect(diffGraphs(before, after).links).toEqual([
      expect.objectContaining({
        network: "street",
        sense: "added",
        aspects: [{ kind: "path", biking: true, walking: true }],
      }),
    ]);
  });

  it("lanes and the speed limit are changes, with both values", () => {
    const before = graph(NODES, [street(1, 1, 2, { lanes: 2, speed_limit: 50 })]);
    const after = graph(NODES, [street(1, 1, 2, { lanes: 1, speed_limit: 30 })]);

    expect(diffGraphs(before, after).links).toEqual([
      expect.objectContaining({
        network: "street",
        sense: "changed",
        aspects: [
          { kind: "lanes", from: 2, to: 1 },
          { kind: "speed", from: 50, to: 30 },
        ],
      }),
    ]);
  });

  it("a bike lane and access rights are the street network's", () => {
    const before = graph(NODES, [street(1, 1, 2, { walking: true })]);
    const after = graph(NODES, [street(1, 1, 2, { bike_lane: true, walking: false })]);

    const links = diffGraphs(before, after).links;
    expect(links).toEqual([
      expect.objectContaining({
        network: "street",
        sense: "added",
        aspects: [{ kind: "bikeLane" }],
      }),
      expect.objectContaining({
        network: "street",
        sense: "removed",
        aspects: [{ kind: "walking" }],
      }),
    ]);
  });

  it("a street laid over a path is a street added, the path's access untouched", () => {
    const before = graph(NODES, [path(1, 1, 2)]);
    const after = graph(NODES, [street(1, 1, 2, { lanes: 1 })]);

    expect(diffGraphs(before, after).links).toEqual([
      expect.objectContaining({
        network: "street",
        sense: "added",
        aspects: [{ kind: "street", lanes: 1, speedLimit: 50 }],
      }),
    ]);
  });

  it("a line on the clones of its own streets has not changed", () => {
    const before = graph(
      NODES,
      [street(1, 1, 2), street(2, 2, 3)],
      [bus(5, "100", [1, 2])],
    );
    const after = graph(
      NODES,
      [
        street(11, 1, 2, { dedicated_bus_lane: true }),
        street(12, 2, 3, { dedicated_bus_lane: true }),
      ],
      [bus(5, "100", [11, 12])],
    );

    expect(diffGraphs(before, after).lines).toEqual([]);
  });

  it("a new line is added along its whole route", () => {
    const edges = [street(1, 1, 2), street(2, 2, 3)];
    const before = graph(NODES, edges);
    const after = graph(NODES, edges, [bus(7, "147", [1, 2])]);

    const [line] = diffGraphs(before, after).lines;
    expect(line).toMatchObject({ id: 7, name: "147", type: "bus", sense: "added" });
    expect(line.segments.map((s) => [s.start, s.end, s.sense])).toEqual([
      [1, 2, "added"],
      [2, 3, "added"],
    ]);
  });

  it("a line that goes is removed along its whole route", () => {
    const edges = [street(1, 1, 2)];
    const before = graph(NODES, edges, [bus(7, "147", [1])]);
    const after = graph(NODES, edges);

    const [line] = diffGraphs(before, after).lines;
    expect(line).toMatchObject({ sense: "removed" });
    expect(line.segments.map((s) => s.sense)).toEqual(["removed"]);
  });

  it("a rerouted line shows only the links it gains and loses", () => {
    const edges = [street(1, 1, 2), street(2, 2, 3), street(3, 2, 4)];
    const before = graph(NODES, edges, [bus(7, "147", [1, 2])]);
    const after = graph(NODES, edges, [bus(7, "147", [1, 3])]);

    const [line] = diffGraphs(before, after).lines;
    expect(line.sense).toBe("changed");
    expect(line.segments.map((s) => [s.start, s.end, s.sense])).toEqual([
      [2, 4, "added"],
      [2, 3, "removed"],
    ]);
  });

  it("finds nodes that come and go", () => {
    const before = graph([node(1), node(2)], []);
    const after = graph([node(1), node(3)], []);

    expect(diffGraphs(before, after).nodes).toEqual([
      expect.objectContaining({ id: 3, sense: "added" }),
      expect.objectContaining({ id: 2, sense: "removed" }),
    ]);
  });
});

describe("linkEntries", () => {
  it("folds the two directions of one street into one entry", () => {
    const before = graph(NODES, [street(1, 1, 2), street(2, 2, 1), street(3, 2, 3)]);
    const after = graph(NODES, [
      street(11, 1, 2, { dedicated_bus_lane: true }),
      street(12, 2, 1, { dedicated_bus_lane: true }),
      street(13, 2, 3, { dedicated_bus_lane: true }),
    ]);

    const entries = linkEntries(diffGraphs(before, after).links);

    expect(entries.map((e) => [e.start, e.end, e.bothWays])).toEqual([
      [1, 2, true],
      [2, 3, false],
    ]);
  });

  it("keeps two directions apart when they did not change alike", () => {
    const before = graph(NODES, [street(1, 1, 2), street(2, 2, 1)]);
    const after = graph(NODES, [
      street(1, 1, 2, { speed_limit: 30 }),
      street(2, 2, 1),
    ]);

    const entries = linkEntries(diffGraphs(before, after).links);
    expect(entries).toHaveLength(1);
    expect(entries[0].bothWays).toBe(false);
  });
});

describe("diffGraphs on Berlin Mitte-West", () => {
  const byName = (name: string) => raw.versions.findIndex((v) => v.name === name);
  const BASE = raw.versions.findIndex((v) => v.base_version);
  const BUSSPUREN = byName("Busspuren");
  const BUSLINIE = byName("Buslinie");
  const UMGEHUNG = byName("Umgehungsstraßen");
  const BUSSPUREN_UMGEHUNG = byName("Busspuren + Umgehungsstraßen");
  const ALL_THREE = byName("Buslinie + Busspuren + Umgehungsstraßen");
  const diff = (from: number, to: number) =>
    diffGraphs(buildGraph(raw, from), buildGraph(raw, to));

  it("knows the versions it is testing", () => {
    for (const version of [BASE, BUSSPUREN, BUSLINIE, UMGEHUNG, BUSSPUREN_UMGEHUNG, ALL_THREE]) {
      expect(version).toBeGreaterThanOrEqual(0);
    }
  });

  it("Busspuren is thirty links gaining a bus lane, and nothing else", () => {
    const d = diff(BASE, BUSSPUREN);

    expect(d.links).toHaveLength(30);
    for (const link of d.links) {
      expect(link).toMatchObject({
        network: "pt",
        sense: "added",
        aspects: [{ kind: "busLane" }],
      });
    }
    // Four lines moved onto the clones; none changed where it runs.
    expect(d.lines).toEqual([]);
    expect(d.nodes).toEqual([]);
    expect(linkEntries(d.links).every((e) => e.bothWays)).toBe(true);
    expect(linkEntries(d.links)).toHaveLength(15);
  });

  it("going back from Busspuren takes the same thirty bus lanes away", () => {
    const d = diff(BUSSPUREN, BASE);

    expect(d.links).toHaveLength(30);
    expect(d.links.every((l) => l.sense === "removed" && l.network === "pt")).toBe(true);
  });

  it("Buslinie is line 147, both ways, and no street", () => {
    const d = diff(BASE, BUSLINIE);

    expect(d.links).toEqual([]);
    expect(d.lines.map((l) => [l.name, l.type, l.sense])).toEqual([
      ["147", "bus", "added"],
      ["147 reverse", "bus", "added"],
    ]);
    expect(d.lines[0].segments.length).toBeGreaterThan(5);
    expect(d.lines[0].segments.every((s) => s.sense === "added")).toBe(true);
  });

  it("Umgehungsstraßen is two streets, both ways, one of them over a path", () => {
    const d = diff(BASE, UMGEHUNG);
    const names = new Map(raw.nodes.map((n) => [Number(n.id), n.name]));

    expect(d.lines).toEqual([]);
    expect(d.links.every((l) => l.network === "street" && l.sense === "added")).toBe(true);
    expect(
      linkEntries(d.links).map((e) => [names.get(e.start), names.get(e.end), e.bothWays]),
    ).toEqual([
      ["Bundestag", "Wohnort 2", true],
      ["Botschaftsviertel", "Philarmonie", true],
    ]);
  });

  it("a combination against one of its changes is the other change", () => {
    const fromBusspuren = diff(BUSSPUREN, BUSSPUREN_UMGEHUNG);
    const fromBase = diff(BASE, UMGEHUNG);

    const shape = (d: typeof fromBase) =>
      d.links.map((l) => [l.start, l.end, l.network, l.sense, l.aspects]);
    expect(shape(fromBusspuren)).toEqual(shape(fromBase));
    expect(fromBusspuren.lines).toEqual([]);
  });

  it("all three changes against base hold each of them", () => {
    const d = diff(BASE, ALL_THREE);

    expect(d.links.filter((l) => l.network === "pt")).toHaveLength(30);
    expect(d.links.filter((l) => l.network === "street")).toHaveLength(4);
    expect(d.lines.map((l) => l.name)).toEqual(["147", "147 reverse"]);
  });
});
