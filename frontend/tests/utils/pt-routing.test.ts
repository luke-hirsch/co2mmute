import { readFileSync } from "node:fs";
import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";

import { findPTRoute } from "@/utils/ptRouting";
import type { Edge, Node, NodeType } from "@/types/mapTypes";
import type { ExtendedMapGraph, PTLine } from "@/types/routeTypes";

/**
 * "Bus & Bahn" on the map people actually play.
 *
 * `ptRouting.ts` is the router a student meets: pick a Fahrgast, pick a mode,
 * and this is what decides whether the answer is a route or "keine Verbindung
 * gefunden". Every other test in this tree builds a toy graph, so nothing ever
 * asked the question that matters — can you get from this map's homes to this
 * map's workplaces by public transport at all?
 *
 * On the shipped file before the S5 data pass, six of thirty-six pairs could
 * not: bus line `100` had no edges, so nothing served Brandenburger Tor, and
 * U Potsdamer Platz — the only other station within two kilometres — has no
 * street edge at all, so it cannot be walked to either. `101` broke mid-chain
 * and lost four of its nine stops the same way.
 *
 * The graph is assembled here the way `MapVersionGraphView` assembles it, stop
 * lists included, because the file is the thing under test: a fixture copied
 * out of it would go stale the first time the map changed.
 *
 * ### One version at a time
 *
 * Since S14 the file carries **all eight** versions of the map, and a line's
 * route is written per route rather than per version (`chains`). So a graph is
 * a filter over the file and this builder needs to be told which version to
 * cut: nodes, edges and lines each carry their own `versions`, and a line takes
 * the one chain that names the version being built.
 *
 * This file stopped running entirely when that format landed — `raw_line.edges`
 * became `undefined` and the `.map` over it threw at import, so vitest reported
 * a failed *suite* and every assertion below silently left the count. That is
 * the failure mode CLAUDE.md names: read the test count, not OK/FAILED.
 */

const MAP_FILE = new URL(
  "../../../map_examples/Berlin_Mitte-West.json",
  import.meta.url,
);

interface RawNode {
  id: string;
  name: string;
  x: number;
  y: number;
  types?: string[];
  versions: number[];
}

interface RawEdge {
  start_node: string;
  end_node: string;
  name: string | null;
  type?: "street" | "train" | "both";
  biking?: boolean;
  bike_lane?: boolean;
  walking?: boolean;
  max_lanes?: number;
  speed_limit?: number;
  lanes?: number;
  dedicated_bus_lane?: boolean;
  versions: number[];
}

interface RawChain {
  versions: number[];
  /** Indices into the file's global `edges` array, in travel order. */
  edges: number[];
}

interface RawLine {
  name: string;
  interval: number;
  capacity: number;
  speed_kmh: number;
  versions: number[];
  chains: RawChain[];
}

interface RawVersion {
  name: string;
  base_version?: boolean;
}

interface RawMap {
  scale: number;
  versions: RawVersion[];
  nodes: RawNode[];
  edges: RawEdge[];
  bus_lines: RawLine[];
  train_lines: RawLine[];
}

/**
 * The node ids a run of edges visits, in travel order.
 *
 * A port of `sim/state.py:node_chain`, which is also what
 * `maps/serializer.py` puts in the `stops` list this router reads. An edge may
 * be stored either way round, so the chain is followed by matching node ids;
 * the first edge is oriented by whichever of its ends the second one touches.
 */
function nodeChain(ends: [number, number][]): number[] {
  if (ends.length === 0) return [];
  const [firstStart, firstEnd] = ends[0];
  if (ends.length === 1) return [firstStart, firstEnd];

  const second = new Set(ends[1]);
  let chain: number[];
  if (second.has(firstEnd)) chain = [firstStart, firstEnd];
  else if (second.has(firstStart)) chain = [firstEnd, firstStart];
  else return [firstStart, firstEnd];

  for (const [start, end] of ends.slice(1)) {
    const prev = chain[chain.length - 1];
    if (prev === start) chain.push(end);
    else if (prev === end) chain.push(start);
    else break;
  }
  return chain;
}

function buildGraph(raw: RawMap, version: number): ExtendedMapGraph {
  const typeIds = new Map<string, number>();
  const nodeType = (name: string): NodeType => {
    if (!typeIds.has(name)) typeIds.set(name, typeIds.size + 1);
    return { id: typeIds.get(name)!, name, short: name.slice(0, 2) };
  };

  const nodes: Node[] = raw.nodes
    .filter((node) => node.versions.includes(version))
    .map((node) => ({
      id: Number(node.id),
      name: node.name,
      x_position: node.x,
      y_position: node.y,
      node_type: (node.types ?? []).map(nodeType),
    }));

  // The edge's index in the file is its id, exactly as the importer maps them
  // (`_create_edges` keys `edge_mapping` by index) — the lines address their
  // edges that way, so the index is kept as the id and the version is a filter
  // over the list rather than a renumbering of it.
  const edges: Edge[] = raw.edges
    .map((edge, index) => ({ edge, index }))
    .filter(({ edge }) => edge.versions.includes(version))
    .map(({ edge, index }) => {
      // `"path"` is a link with neither a street nor a railway under it — a way
      // for bikes and pedestrians. It needed its own name because the export
      // used to write one as `"street"` and the importer invented a 50 km/h
      // lane under it.
      const type = edge.type ?? "both";
      return {
        id: index,
        name: edge.name ?? "",
        start_node: Number(edge.start_node),
        end_node: Number(edge.end_node),
        biking: edge.biking ?? type !== "train",
        bike_lane: edge.bike_lane ?? false,
        walking: edge.walking ?? type !== "train",
        max_lanes: edge.max_lanes ?? 1,
        street_edge:
          type === "street" || type === "both"
            ? {
                id: index,
                speed_limit: edge.speed_limit ?? 50,
                lanes: edge.lanes ?? 1,
                dedicated_bus_lane: edge.dedicated_bus_lane ?? false,
              }
            : null,
        train_edge: type === "train" || type === "both" ? { id: index } : null,
      };
    });

  /**
   * The chain this version runs the line on, or none.
   *
   * A line can be in a version and still have no route in it — that is the
   * shape of the damage S15 repaired, where a cloned street took a line's
   * through-row with it and left the base version reaching none of its edges.
   */
  const chainFor = (line: RawLine): number[] | null =>
    line.chains.find((chain) => chain.versions.includes(version))?.edges ?? null;

  const line = (
    raw_line: RawLine,
    id: number,
    type: "bus" | "train",
  ): PTLine | null => {
    const chain = chainFor(raw_line);
    if (!chain) return null;
    return {
      id,
      name: raw_line.name,
      type,
      interval: raw_line.interval,
      capacity: raw_line.capacity,
      speed_kmh: raw_line.speed_kmh,
      edges: chain,
      stops: nodeChain(
        chain.map(
          (index) =>
            [
              Number(raw.edges[index].start_node),
              Number(raw.edges[index].end_node),
            ] as [number, number],
        ),
      ),
    };
  };

  const lines = (raws: RawLine[], offset: number, type: "bus" | "train") =>
    raws
      .map((raw_line, i) =>
        raw_line.versions.includes(version)
          ? line(raw_line, i + offset, type)
          : null,
      )
      .filter((l): l is PTLine => l !== null);

  return {
    map_id: 1,
    version_id: version,
    version_name: raw.versions[version].name,
    nodes,
    edges,
    node_count: nodes.length,
    edge_count: edges.length,
    bus_lines: lines(raw.bus_lines, 1, "bus"),
    train_lines: lines(raw.train_lines, 101, "train"),
    scale: raw.scale,
  };
}

const raw = JSON.parse(readFileSync(MAP_FILE, "utf-8")) as RawMap;

/** The base version — the one a game starts on before the class votes. */
const BASE = raw.versions.findIndex((v) => v.base_version) >= 0
  ? raw.versions.findIndex((v) => v.base_version)
  : 0;
const graph = buildGraph(raw, BASE);

/** The six `home` nodes and the six `workplace` nodes, by name. */
const HOMES = Object.fromEntries(
  raw.nodes
    .filter((n) => (n.types ?? []).includes("home"))
    .map((n) => [n.name, Number(n.id)]),
);
const WORKPLACES = Object.fromEntries(
  raw.nodes
    .filter((n) => (n.types ?? []).includes("workplace"))
    .map((n) => [n.name, Number(n.id)]),
);

describe("bus & bahn on Berlin Mitte-West", () => {
  // The router narrates itself to the console on every call, and 36 of them
  // bury the run. Silenced here rather than in the source: a student's browser
  // console is the one place those lines are worth something.
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
    quiet.push(vi.spyOn(console, "warn").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  it("knows the map it is testing", () => {
    expect(Object.keys(HOMES)).toHaveLength(6);
    expect(Object.keys(WORKPLACES)).toHaveLength(6);
    expect(graph.bus_lines.map((l) => l.name)).toEqual([
      "100",
      "100 reverse",
      "101",
      "101 reverse",
    ]);
  });

  it("finds a route from every home to every workplace", async () => {
    const failures: string[] = [];
    for (const [home, from] of Object.entries(HOMES)) {
      for (const [work, to] of Object.entries(WORKPLACES)) {
        const result = await findPTRoute(graph, from, to, { scale: graph.scale });
        if (!result.success) failures.push(`${home} → ${work}: ${result.error}`);
      }
    }

    expect(failures).toEqual([]);
  });

  it("puts a bus on the road, not just trains", async () => {
    // Brandenburger Tor is the case the empty `100` cost: a bus stop, a
    // workplace beside it, and no rail within walking distance.
    const result = await findPTRoute(
      graph,
      HOMES["Wohnort 1"],
      WORKPLACES["Arbeit Brandenburger Tor"],
      { scale: graph.scale },
    );

    expect(result.success).toBe(true);
    const lines = result.ptSegments
      .map((segment) => segment.ptLineId)
      .filter((id): id is number => id != null);
    const bus = graph.bus_lines.find((l) => lines.includes(l.id));
    expect(bus?.name).toBe("100");
  });
});

/**
 * The same question, asked of every version the class can vote its way into.
 *
 * Until S16 the box's map had one version in the repo and the other seven only
 * in a database, so this could not be asked at all — and the two bugs S15 fixed
 * are exactly the ones it catches. A line's chain was not version-scoped, so
 * drawing `Busspuren` moved buslinie `100` onto the cloned street in *every*
 * version and left the base one reaching 0 of its 7 edges; and
 * `GenerateCombinationsView` never copied `TrainLine`, so a generated
 * combination had no rail at all.
 *
 * Both are the kind of damage a player meets as "keine Verbindung gefunden" on
 * a map that looks right on screen. Per version, so a failure names the ballot
 * option that broke rather than the map.
 */
describe("every version of the map keeps its public transport", () => {
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
    quiet.push(vi.spyOn(console, "warn").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  it("has the eight versions S16 put in the repo", () => {
    expect(raw.versions.map((v) => v.name)).toEqual([
      "Berlin Mitte-West - Base",
      "Busspuren",
      "Buslinie",
      "Umgehungsstraßen",
      "Buslinie + Umgehungsstraßen",
      "Busspuren + Umgehungsstraßen",
      "Buslinie + Busspuren",
      "Buslinie + Busspuren + Umgehungsstraßen",
    ]);
  });

  it.each(raw.versions.map((v, index) => [index, v.name] as const))(
    "connects every home to every workplace in version %i (%s)",
    async (version) => {
      const versionGraph = buildGraph(raw, version);

      // A line in the version must have a route in it. This is the assertion
      // that fails on a chain the cloning moved somewhere else.
      const routeless = [
        ...versionGraph.bus_lines,
        ...versionGraph.train_lines,
      ].filter((line) => line.edges.length === 0);
      expect(routeless.map((l) => l.name)).toEqual([]);

      // And rail has to survive a generated combination, which is the second
      // bug: `Buslinie + Busspuren` and friends were built without any.
      expect(versionGraph.train_lines.length).toBeGreaterThan(0);

      const failures: string[] = [];
      for (const [home, from] of Object.entries(HOMES)) {
        for (const [work, to] of Object.entries(WORKPLACES)) {
          const result = await findPTRoute(versionGraph, from, to, {
            scale: versionGraph.scale,
          });
          if (!result.success) failures.push(`${home} → ${work}: ${result.error}`);
        }
      }
      expect(failures).toEqual([]);
    },
  );
});
