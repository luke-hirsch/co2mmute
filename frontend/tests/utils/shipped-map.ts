import { readFileSync } from "node:fs";

import type { Edge, Node, NodeType } from "@/types/mapTypes";
import type { ExtendedMapGraph, PTLine } from "@/types/routeTypes";

/**
 * The shipped map file, cut into the graph `MapVersionGraphView` would serve
 * for one of its versions.
 *
 * Moved out of `pt-routing.test.ts` when the version diff needed the same
 * graphs: the file carries all eight versions and the diff is tested on what
 * the three changes really do to it, not on a toy copy that would go stale.
 * Not a test file (no `.test.ts`), so vitest does not collect it.
 */

export const MAP_FILE = new URL(
  "../../../map_examples/Berlin_Mitte-West.json",
  import.meta.url,
);

export interface RawNode {
  id: string;
  name: string;
  x: number;
  y: number;
  types?: string[];
  versions: number[];
}

export interface RawEdge {
  start_node: string;
  end_node: string;
  name: string | null;
  type?: "street" | "train" | "both" | "path";
  biking?: boolean;
  bike_lane?: boolean;
  walking?: boolean;
  max_lanes?: number;
  speed_limit?: number;
  lanes?: number;
  dedicated_bus_lane?: boolean;
  versions: number[];
}

export interface RawChain {
  versions: number[];
  /** Indices into the file's global `edges` array, in travel order. */
  edges: number[];
}

export interface RawLine {
  name: string;
  interval: number;
  capacity: number;
  speed_kmh: number;
  versions: number[];
  chains: RawChain[];
}

export interface RawVersion {
  name: string;
  base_version?: boolean;
}

export interface RawMap {
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
export function nodeChain(ends: [number, number][]): number[] {
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

export function buildGraph(raw: RawMap, version: number): ExtendedMapGraph {
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
    // Ids per table, as the database hands them out: bus 2 and train 2 are
    // two different lines. Numbering the trains from 101 here is what hid the
    // router taking one for the other.
    bus_lines: lines(raw.bus_lines, 1, "bus"),
    train_lines: lines(raw.train_lines, 1, "train"),
    scale: raw.scale,
  };
}

/** The file itself, parsed once. */
export const raw = JSON.parse(readFileSync(MAP_FILE, "utf-8")) as RawMap;
