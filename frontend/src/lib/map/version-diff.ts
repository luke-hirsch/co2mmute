/**
 * What one map version changes against another, read off the two graphs.
 *
 * The editor's version list and the ballot both have to answer "what does this
 * version actually do to the map?", and until now neither could: the poll text
 * is enough to vote on and not enough to know, and the change picture is a PNG
 * somebody has to draw. Both graphs are already a fetch away
 * (`useMapGraph(map, version)`), so the answer is computed here, once, and the
 * three renderers draw it.
 *
 * ### Links are compared by their node pair, never by id
 *
 * A version is a filter over one shared graph, and a change to a street is
 * stored as a **clone**: `Busspuren` holds a second `Edge` row for each street
 * it gives a bus lane and leaves the original to base, and every line that ran
 * over the original moves its chain row onto the clone (S15). Compared by id,
 * `Busspuren` reads as thirty streets removed, thirty added and four lines
 * rerouted. What it does is give thirty links a bus lane. So a link is its
 * `start → end` pair — the editor allows one link per direction per node pair
 * per version (`edge-exists`, pinned on the shipped file by `test_example_map`)
 * — and a line is the set of pairs it runs over.
 *
 * ### Two networks, three senses
 *
 * Every change belongs to the street network (what a car, a bike or a
 * pedestrian meets: the street itself, its lanes and limit, a bike lane, a path,
 * who may use it) or to public transport (a railway alignment, a bus lane, a
 * line's route). That is the colour it is drawn in — primary and accent, the
 * game's two. **A bus lane is public transport's** although it is painted on a
 * street: it is there for the bus, which is what the class votes it in for, and
 * the car losing a lane to it is the trade the discussion is about.
 *
 * The sense is whether the thing arrives (`added`), goes (`removed`) or is
 * still there with different numbers (`changed` — lanes, a speed limit). A link
 * can carry more than one change of different kinds; they are grouped by
 * network and sense, so each group is one stroke on the map.
 *
 * A line row is shared by every version it runs in, so its timetable cannot
 * differ between two versions of one map — only where it runs can.
 */

import type { Edge, Node } from "@/types/mapTypes";
import type { ExtendedMapGraph, PTLine } from "@/types/routeTypes";

/** A position in the map's own units (`x_position`, not the SVG's ×100). */
export type Point = { x: number; y: number };

export type Network = "street" | "pt";
export type Sense = "added" | "removed" | "changed";

/** One thing that differs on a link. */
export type LinkAspect =
  /** The street itself, with what it is — present on one side only. */
  | { kind: "street"; lanes: number; speedLimit: number }
  /** A railway alignment. */
  | { kind: "rail" }
  /** A link with neither street nor railway under it: a way for bikes and feet. */
  | { kind: "path"; biking: boolean; walking: boolean }
  | { kind: "busLane" }
  | { kind: "bikeLane" }
  /** Whether a bike may use the link at all. */
  | { kind: "biking" }
  /** Whether a pedestrian may use the link at all. */
  | { kind: "walking" }
  | { kind: "lanes"; from: number; to: number }
  | { kind: "speed"; from: number; to: number };

export type LinkChange = {
  start: number;
  end: number;
  a: Point;
  b: Point;
  network: Network;
  sense: Sense;
  aspects: LinkAspect[];
};

export type LineSegment = {
  start: number;
  end: number;
  a: Point;
  b: Point;
  sense: "added" | "removed";
};

export type LineChange = {
  id: number;
  type: "bus" | "train";
  name: string;
  /** `added`: a new line; `removed`: a line that goes; `changed`: rerouted. */
  sense: Sense;
  /** Only the links the line gains or loses — all of them for a new line. */
  segments: LineSegment[];
  /** The line's stops, first to last, on whichever side it runs. */
  stops: number[];
};

export type NodeChange = {
  id: number;
  name: string;
  at: Point;
  sense: "added" | "removed";
};

export type VersionDiff = {
  links: LinkChange[];
  lines: LineChange[];
  nodes: NodeChange[];
  /** True when the two versions draw the same map. */
  empty: boolean;
};

/** Just what the diff reads, so a caller can hand over any graph payload. */
export type DiffableGraph = Pick<
  ExtendedMapGraph,
  "nodes" | "edges" | "bus_lines" | "train_lines"
>;

const pairKey = (start: number, end: number) => `${start}-${end}`;

/** What a link is, read once so the comparison below is over plain values. */
type LinkShape = {
  street: { lanes: number; speedLimit: number; busLane: boolean } | null;
  rail: boolean;
  bikeLane: boolean;
  biking: boolean;
  walking: boolean;
};

function shapeOf(edge: Edge): LinkShape {
  const street = edge.street_edge
    ? {
        lanes: edge.street_edge.lanes,
        speedLimit: edge.street_edge.speed_limit,
        busLane: edge.street_edge.dedicated_bus_lane,
      }
    : null;
  return {
    street,
    rail: edge.train_edge != null,
    bikeLane: !!edge.bike_lane,
    biking: !!edge.biking,
    walking: !!edge.walking,
  };
}

/** Everything a link is, as the changes it would take to draw it from nothing. */
function wholeLink(shape: LinkShape): { network: Network; aspect: LinkAspect }[] {
  const out: { network: Network; aspect: LinkAspect }[] = [];
  if (shape.street) {
    out.push({
      network: "street",
      aspect: {
        kind: "street",
        lanes: shape.street.lanes,
        speedLimit: shape.street.speedLimit,
      },
    });
    if (shape.street.busLane) out.push({ network: "pt", aspect: { kind: "busLane" } });
    if (shape.bikeLane) out.push({ network: "street", aspect: { kind: "bikeLane" } });
  }
  if (shape.rail) out.push({ network: "pt", aspect: { kind: "rail" } });
  if (!shape.street && !shape.rail) {
    out.push({
      network: "street",
      aspect: { kind: "path", biking: shape.biking, walking: shape.walking },
    });
  }
  return out;
}

/** What differs between two shapes of one link, each with its network and sense. */
function linkDelta(
  before: LinkShape,
  after: LinkShape,
): { network: Network; sense: Sense; aspect: LinkAspect }[] {
  const out: { network: Network; sense: Sense; aspect: LinkAspect }[] = [];
  const presence = (
    was: boolean,
    is: boolean,
    network: Network,
    aspect: LinkAspect,
  ) => {
    if (was !== is) out.push({ network, sense: is ? "added" : "removed", aspect });
  };

  const { street: s0 } = before;
  const { street: s1 } = after;
  if (!s0 !== !s1) {
    const street = (s1 ?? s0)!;
    out.push({
      network: "street",
      sense: s1 ? "added" : "removed",
      aspect: { kind: "street", lanes: street.lanes, speedLimit: street.speedLimit },
    });
  }
  presence(before.rail, after.rail, "pt", { kind: "rail" });
  presence(!!s0?.busLane, !!s1?.busLane, "pt", { kind: "busLane" });
  presence(before.bikeLane, after.bikeLane, "street", { kind: "bikeLane" });
  // Access is the street network's question only where a link stayed: a street
  // appearing over a path keeps the path's bikes and feet, and a street with no
  // street on either side is a path whose access *is* what it is.
  presence(before.biking, after.biking, "street", { kind: "biking" });
  presence(before.walking, after.walking, "street", { kind: "walking" });
  if (s0 && s1 && s0.lanes !== s1.lanes) {
    out.push({
      network: "street",
      sense: "changed",
      aspect: { kind: "lanes", from: s0.lanes, to: s1.lanes },
    });
  }
  if (s0 && s1 && s0.speedLimit !== s1.speedLimit) {
    out.push({
      network: "street",
      sense: "changed",
      aspect: { kind: "speed", from: s0.speedLimit, to: s1.speedLimit },
    });
  }
  return out;
}

/** Grouped by network and sense, in the order each group first appears. */
function grouped(
  start: number,
  end: number,
  a: Point,
  b: Point,
  items: { network: Network; sense: Sense; aspect: LinkAspect }[],
): LinkChange[] {
  const groups = new Map<string, LinkChange>();
  for (const { network, sense, aspect } of items) {
    const key = `${network}:${sense}`;
    let group = groups.get(key);
    if (!group) {
      group = { start, end, a, b, network, sense, aspects: [] };
      groups.set(key, group);
    }
    group.aspects.push(aspect);
  }
  return [...groups.values()];
}

/** The pairs a line runs over, in its own order, as `key → [start, end]`. */
function lineLinks(line: PTLine, edges: Map<number, Edge>): Map<string, [number, number]> {
  const out = new Map<string, [number, number]>();
  for (const id of line.edges) {
    const edge = edges.get(id);
    if (edge) out.set(pairKey(edge.start_node, edge.end_node), [edge.start_node, edge.end_node]);
  }
  return out;
}

export function diffGraphs(from: DiffableGraph, to: DiffableGraph): VersionDiff {
  // Positions from the new graph where a node is in it, else from the old one:
  // what goes is drawn where it was.
  const nodesAt = new Map<number, Node>();
  for (const node of from.nodes) nodesAt.set(node.id, node);
  for (const node of to.nodes) nodesAt.set(node.id, node);
  const at = (id: number): Point => {
    const node = nodesAt.get(id);
    return node ? { x: node.x_position, y: node.y_position } : { x: 0, y: 0 };
  };

  // ── links ──────────────────────────────────────────────────────────────
  const before = new Map(from.edges.map((e) => [pairKey(e.start_node, e.end_node), e]));
  const after = new Map(to.edges.map((e) => [pairKey(e.start_node, e.end_node), e]));

  const links: LinkChange[] = [];
  for (const [key, edge] of after) {
    const was = before.get(key);
    const { start_node: s, end_node: e } = edge;
    const items = was
      ? linkDelta(shapeOf(was), shapeOf(edge))
      : wholeLink(shapeOf(edge)).map((i) => ({ ...i, sense: "added" as const }));
    links.push(...grouped(s, e, at(s), at(e), items));
  }
  for (const [key, edge] of before) {
    if (after.has(key)) continue;
    const { start_node: s, end_node: e } = edge;
    const items = wholeLink(shapeOf(edge)).map((i) => ({
      ...i,
      sense: "removed" as const,
    }));
    links.push(...grouped(s, e, at(s), at(e), items));
  }

  // ── lines ──────────────────────────────────────────────────────────────
  const edgesBefore = new Map(from.edges.map((e) => [e.id, e]));
  const edgesAfter = new Map(to.edges.map((e) => [e.id, e]));
  const linesBefore = new Map(
    [...from.bus_lines, ...from.train_lines].map((l) => [`${l.type}:${l.id}`, l]),
  );
  const linesAfter = new Map(
    [...to.bus_lines, ...to.train_lines].map((l) => [`${l.type}:${l.id}`, l]),
  );

  const segment = (
    [start, end]: [number, number],
    sense: "added" | "removed",
  ): LineSegment => ({ start, end, a: at(start), b: at(end), sense });

  const lines: LineChange[] = [];
  for (const [key, line] of linesAfter) {
    const runs = lineLinks(line, edgesAfter);
    const was = linesBefore.get(key);
    if (!was) {
      lines.push({
        id: line.id,
        type: line.type,
        name: line.name,
        sense: "added",
        segments: [...runs.values()].map((pair) => segment(pair, "added")),
        stops: line.stops,
      });
      continue;
    }
    const ran = lineLinks(was, edgesBefore);
    const gained = [...runs].filter(([k]) => !ran.has(k));
    const lost = [...ran].filter(([k]) => !runs.has(k));
    if (gained.length === 0 && lost.length === 0) continue;
    lines.push({
      id: line.id,
      type: line.type,
      name: line.name,
      sense: "changed",
      segments: [
        ...gained.map(([, pair]) => segment(pair, "added")),
        ...lost.map(([, pair]) => segment(pair, "removed")),
      ],
      stops: line.stops,
    });
  }
  for (const [key, line] of linesBefore) {
    if (linesAfter.has(key)) continue;
    lines.push({
      id: line.id,
      type: line.type,
      name: line.name,
      sense: "removed",
      segments: [...lineLinks(line, edgesBefore).values()].map((pair) =>
        segment(pair, "removed"),
      ),
      stops: line.stops,
    });
  }

  // ── nodes ──────────────────────────────────────────────────────────────
  const idsBefore = new Set(from.nodes.map((n) => n.id));
  const idsAfter = new Set(to.nodes.map((n) => n.id));
  const nodes: NodeChange[] = [
    ...to.nodes
      .filter((n) => !idsBefore.has(n.id))
      .map((n) => ({ id: n.id, name: n.name, at: at(n.id), sense: "added" as const })),
    ...from.nodes
      .filter((n) => !idsAfter.has(n.id))
      .map((n) => ({ id: n.id, name: n.name, at: at(n.id), sense: "removed" as const })),
  ];

  return {
    links,
    lines,
    nodes,
    empty: links.length === 0 && lines.length === 0 && nodes.length === 0,
  };
}

/** One line of the editor's list: a link, or a street's two directions together. */
export type LinkEntry = {
  start: number;
  end: number;
  network: Network;
  sense: Sense;
  aspects: LinkAspect[];
  /** The reverse direction changed in exactly the same way. */
  bothWays: boolean;
};

/**
 * The link changes as a reader wants them listed: a street whose two directions
 * changed alike is one entry, not two. A one-way change stays one-way — on a
 * map with one-way streets that difference is the point.
 */
export function linkEntries(links: LinkChange[]): LinkEntry[] {
  const same = (x: LinkChange, y: LinkChange) =>
    x.network === y.network &&
    x.sense === y.sense &&
    JSON.stringify(x.aspects) === JSON.stringify(y.aspects);

  const used = new Set<LinkChange>();
  const entries: LinkEntry[] = [];
  for (const link of links) {
    if (used.has(link)) continue;
    used.add(link);
    const reverse = links.find(
      (other) =>
        !used.has(other) &&
        other.start === link.end &&
        other.end === link.start &&
        same(link, other),
    );
    if (reverse) used.add(reverse);
    entries.push({
      start: link.start,
      end: link.end,
      network: link.network,
      sense: link.sense,
      aspects: link.aspects,
      bothWays: !!reverse,
    });
  }
  return entries;
}
