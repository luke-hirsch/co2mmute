/**
 * Public Transport Routing — Product-Graph Dijkstra
 *
 * Models the routing state as (nodeId, travelMode) where travelMode is either
 * "walk" or a specific PT line. This allows Dijkstra to naturally handle:
 *   - Unlimited transfers
 *   - Direction constraints (PT lines are directed)
 *   - Topology-aware walking (no straight-line radius heuristic)
 *   - 2km walking limit for first/last mile
 *   - PT optimization options
 */

import type { Node, Edge } from "../types/mapTypes";
import type {
  PTLine,
  RouteSegment,
  PTRoutingResult,
  ExtendedMapGraph,
  PathfindingState,
  PTOptimization,
} from "../types/routeTypes";
import {
  buildAdjacencyList,
  canUseEdge,
  calculateDistance,
  dijkstra,
} from "./pathfinding";

const WALK_SPEED_KMH = 5;
const MAX_WALK_DISTANCE_M = 2000;
// Extra penalty per boarding for "fewest_transfers" optimization (minutes)
const FEWEST_TRANSFERS_PENALTY_MIN = 30;

// ---------------------------------------------------------------------------
// Internal product-graph types
// ---------------------------------------------------------------------------

type ProductMode =
  | { tag: "walk"; hasBoarded: false } // pre-first-boarding walk
  | { tag: "walk"; hasBoarded: true } // post-alighting / transfer walk
  | { tag: "pt"; lineId: number; lineType: "bus" | "train" };

interface ProductNode {
  nodeId: number;
  mode: ProductMode;
}

type StateKey = string;

function stateKey(n: ProductNode): StateKey {
  const m = n.mode;
  if (m.tag === "walk") return `w${m.hasBoarded ? "1" : "0"}:${n.nodeId}`;
  return `pt:${n.nodeId}:${m.lineType}:${m.lineId}`;
}

interface CameFromEntry {
  fromState: ProductNode;
  edgeId: number | null; // null = boarding wait or alighting
  distanceM: number;
  costMin: number; // cost of this single step
}

interface ProductGraphResult {
  cameFrom: Map<StateKey, CameFromEntry>;
  finalState: ProductNode;
  totalCostMin: number;
}

// ---------------------------------------------------------------------------
// Min-heap for Dijkstra priority queue
// ---------------------------------------------------------------------------

interface HeapItem {
  state: ProductNode;
  key: StateKey;
  cost: number;
}

class MinHeap {
  private data: HeapItem[] = [];

  push(item: HeapItem): void {
    this.data.push(item);
    this.bubbleUp(this.data.length - 1);
  }

  pop(): HeapItem | undefined {
    if (this.data.length === 0) return undefined;
    const top = this.data[0];
    const last = this.data.pop()!;
    if (this.data.length > 0) {
      this.data[0] = last;
      this.sinkDown(0);
    }
    return top;
  }

  get size(): number {
    return this.data.length;
  }

  private bubbleUp(i: number): void {
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (this.data[parent].cost <= this.data[i].cost) break;
      [this.data[parent], this.data[i]] = [this.data[i], this.data[parent]];
      i = parent;
    }
  }

  private sinkDown(i: number): void {
    const n = this.data.length;
    while (true) {
      let smallest = i;
      const l = 2 * i + 1;
      const r = 2 * i + 2;
      if (l < n && this.data[l].cost < this.data[smallest].cost) smallest = l;
      if (r < n && this.data[r].cost < this.data[smallest].cost) smallest = r;
      if (smallest === i) break;
      [this.data[smallest], this.data[i]] = [this.data[i], this.data[smallest]];
      i = smallest;
    }
  }
}

// ---------------------------------------------------------------------------
// Pre-computation helpers
// ---------------------------------------------------------------------------

function buildStopIndex(
  busLines: PTLine[],
  trainLines: PTLine[]
): Map<number, { line: PTLine; stopIndex: number }[]> {
  const index = new Map<number, { line: PTLine; stopIndex: number }[]>();
  for (const line of [...busLines, ...trainLines]) {
    for (let i = 0; i < line.stops.length; i++) {
      const nodeId = line.stops[i];
      let entries = index.get(nodeId);
      if (!entries) {
        entries = [];
        index.set(nodeId, entries);
      }
      entries.push({ line, stopIndex: i });
    }
  }
  return index;
}

function buildDesignatedStopSet(nodes: Node[]): Set<number> {
  const set = new Set<number>();
  for (const node of nodes) {
    const types = node.node_type.map((t) => t.name);
    if (types.includes("station") || types.includes("bus_stop")) {
      set.add(node.id);
    }
  }
  return set;
}

/**
 * Build a reverse walk adjacency list (edges point from end_node → start_node).
 * Used to find which stops can REACH a given node (vs. nodes reachable FROM it).
 */
function buildReverseWalkAdjacency(
  edges: Edge[],
  nodes: Node[]
): Map<number, { edge: Edge; neighbor: number }[]> {
  const adjacency = new Map<number, { edge: Edge; neighbor: number }[]>();
  for (const node of nodes) adjacency.set(node.id, []);
  for (const edge of edges) {
    if (!canUseEdge(edge, "walk")) continue;
    adjacency.get(edge.end_node)?.push({ edge, neighbor: edge.start_node });
  }
  return adjacency;
}

/**
 * Run a walk-only Dijkstra from a start node, capping at maxDistanceM.
 * Returns a map of nodeId → walk distance in meters for all reachable nodes.
 */
function walkReachabilitySet(
  startNodeId: number,
  walkAdj: Map<number, { edge: Edge; neighbor: number }[]>,
  nodeMap: Map<number, Node>,
  scale: number,
  maxDistanceM: number
): Map<number, number> {
  const dist = new Map<number, number>();
  dist.set(startNodeId, 0);
  const heap = new MinHeap();
  heap.push({
    state: { nodeId: startNodeId, mode: { tag: "walk", hasBoarded: false } },
    key: `wr:${startNodeId}`,
    cost: 0,
  });
  const visited = new Set<number>();

  while (heap.size > 0) {
    const item = heap.pop()!;
    const { nodeId } = item.state;
    if (visited.has(nodeId)) continue;
    visited.add(nodeId);

    const currentDist = dist.get(nodeId) ?? Infinity;
    if (currentDist > maxDistanceM) continue;

    for (const { edge, neighbor } of walkAdj.get(nodeId) ?? []) {
      if (!canUseEdge(edge, "walk")) continue;
      const startNode = nodeMap.get(nodeId);
      const endNode = nodeMap.get(neighbor);
      if (!startNode || !endNode) continue;
      const edgeDist = edge.distance_m ?? calculateDistance(startNode, endNode, scale);
      const newDist = currentDist + edgeDist;
      if (newDist <= maxDistanceM && newDist < (dist.get(neighbor) ?? Infinity)) {
        dist.set(neighbor, newDist);
        heap.push({
          state: { nodeId: neighbor, mode: { tag: "walk", hasBoarded: false } },
          key: `wr:${neighbor}`,
          cost: newDist,
        });
      }
    }
  }

  return dist;
}

// ---------------------------------------------------------------------------
// Product-graph neighbour expansion
// ---------------------------------------------------------------------------

interface Transition {
  nextState: ProductNode;
  nextKey: StateKey;
  costMin: number;
  edgeId: number | null;
  distanceM: number;
}

function getNeighbours(
  state: ProductNode,
  walkAdj: Map<number, { edge: Edge; neighbor: number }[]>,
  stopIndex: Map<number, { line: PTLine; stopIndex: number }[]>,
  designatedStops: Set<number>,
  boardableStops: Set<number>,
  nodeMap: Map<number, Node>,
  scale: number,
  ptOptimization: PTOptimization
): Transition[] {
  const transitions: Transition[] = [];
  const { nodeId, mode } = state;

  if (mode.tag === "walk") {
    // --- Walk edges ---
    for (const { edge, neighbor } of walkAdj.get(nodeId) ?? []) {
      if (!canUseEdge(edge, "walk")) continue;
      const startNode = nodeMap.get(nodeId);
      const endNode = nodeMap.get(neighbor);
      if (!startNode || !endNode) continue;
      const distM = edge.distance_m ?? calculateDistance(startNode, endNode, scale);
      const costMin = (distM / 1000 / WALK_SPEED_KMH) * 60;
      const nextMode: ProductMode = { tag: "walk", hasBoarded: mode.hasBoarded };
      const nextState: ProductNode = { nodeId: neighbor, mode: nextMode };
      transitions.push({
        nextState,
        nextKey: stateKey(nextState),
        costMin,
        edgeId: edge.id,
        distanceM: distM,
      });
    }

    // --- Board a PT line ---
    if (designatedStops.has(nodeId)) {
      // First boarding: only at stops within 2km of start
      const canBoard = mode.hasBoarded || boardableStops.has(nodeId);
      if (canBoard) {
        for (const { line } of stopIndex.get(nodeId) ?? []) {
          // Apply "no_bus" optimization
          if (ptOptimization === "no_bus" && line.type === "bus") continue;

          const waitCost = line.interval / 2;
          const transferPenalty =
            ptOptimization === "fewest_transfers" && mode.hasBoarded
              ? FEWEST_TRANSFERS_PENALTY_MIN
              : 0;
          const nextMode: ProductMode = {
            tag: "pt",
            lineId: line.id,
            lineType: line.type,
          };
          const nextState: ProductNode = { nodeId, mode: nextMode };
          transitions.push({
            nextState,
            nextKey: stateKey(nextState),
            costMin: waitCost + transferPenalty,
            edgeId: null,
            distanceM: 0,
          });
        }
      }
    }
  } else {
    // mode.tag === "pt"
    const lineEntries = stopIndex.get(nodeId) ?? [];
    const lineId = mode.lineId;

    // Find this node's position(s) on the line
    for (const { line, stopIndex: idx } of lineEntries) {
      if (line.id !== lineId) continue;

      // --- Ride forward one stop ---
      if (idx + 1 < line.stops.length) {
        const nextNodeId = line.stops[idx + 1];
        const edgeId = line.edges[idx] ?? null;
        const startNode = nodeMap.get(nodeId);
        const endNode = nodeMap.get(nextNodeId);
        let distM = 0;
        if (edgeId !== null) {
          // Use edge distance if available via nodeMap lookup — we approximate from nodes
          if (startNode && endNode) {
            distM = calculateDistance(startNode, endNode, scale);
          }
        } else if (startNode && endNode) {
          distM = calculateDistance(startNode, endNode, scale);
        }
        const costMin = (distM / 1000 / line.speed_kmh) * 60;
        const nextState: ProductNode = { nodeId: nextNodeId, mode };
        transitions.push({
          nextState,
          nextKey: stateKey(nextState),
          costMin,
          edgeId,
          distanceM: distM,
        });
      }

      // --- Alight (at any designated stop; 2km final-walk limit enforced post-hoc) ---
      if (designatedStops.has(nodeId)) {
        const nextMode: ProductMode = { tag: "walk", hasBoarded: true };
        const nextState: ProductNode = { nodeId, mode: nextMode };
        transitions.push({
          nextState,
          nextKey: stateKey(nextState),
          costMin: 0,
          edgeId: null,
          distanceM: 0,
        });
      }
    }
  }

  return transitions;
}

// ---------------------------------------------------------------------------
// Product-graph Dijkstra
// ---------------------------------------------------------------------------

function productGraphDijkstra(
  startNodeId: number,
  endNodeId: number,
  walkAdj: Map<number, { edge: Edge; neighbor: number }[]>,
  stopIndex: Map<number, { line: PTLine; stopIndex: number }[]>,
  designatedStops: Set<number>,
  boardableStops: Set<number>,
  nodeMap: Map<number, Node>,
  scale: number,
  ptOptimization: PTOptimization
): ProductGraphResult | null {
  const startMode: ProductMode = { tag: "walk", hasBoarded: false };
  const startState: ProductNode = { nodeId: startNodeId, mode: startMode };
  const startKey = stateKey(startState);

  const dist = new Map<StateKey, number>();
  dist.set(startKey, 0);

  const cameFrom = new Map<StateKey, CameFromEntry>();
  const visited = new Set<StateKey>();

  const heap = new MinHeap();
  heap.push({ state: startState, key: startKey, cost: 0 });

  while (heap.size > 0) {
    const item = heap.pop()!;
    const { state, key, cost } = item;

    if (visited.has(key)) continue;
    visited.add(key);

    // Check termination: reached end node in post-boarding walk mode
    if (
      state.nodeId === endNodeId &&
      state.mode.tag === "walk" &&
      state.mode.hasBoarded
    ) {
      return { cameFrom, finalState: state, totalCostMin: cost };
    }

    const neighbours = getNeighbours(
      state,
      walkAdj,
      stopIndex,
      designatedStops,
      boardableStops,
      nodeMap,
      scale,
      ptOptimization
    );

    for (const t of neighbours) {
      if (visited.has(t.nextKey)) continue;
      const newCost = cost + t.costMin;
      if (newCost < (dist.get(t.nextKey) ?? Infinity)) {
        dist.set(t.nextKey, newCost);
        cameFrom.set(t.nextKey, {
          fromState: state,
          edgeId: t.edgeId,
          distanceM: t.distanceM,
          costMin: t.costMin,
        });
        heap.push({ state: t.nextState, key: t.nextKey, cost: newCost });
      }
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Path reconstruction
// ---------------------------------------------------------------------------

interface ReconstructedPath {
  walkToStation: RouteSegment[];
  ptSegments: RouteSegment[];
  walkFromStation: RouteSegment[];
  totalWaitTimeMin: number;
}

function reconstructPath(
  result: ProductGraphResult,
  startNodeId: number,
  edgeMap: Map<number, Edge>,
  stopIndex: Map<number, { line: PTLine; stopIndex: number }[]>
): ReconstructedPath {
  // Trace backwards from finalState to start
  const steps: {
    fromState: ProductNode;
    toState: ProductNode;
    entry: CameFromEntry;
  }[] = [];

  let current = result.finalState;
  let currentKey = stateKey(current);

  while (currentKey !== stateKey({ nodeId: startNodeId, mode: { tag: "walk", hasBoarded: false } })) {
    const entry = result.cameFrom.get(currentKey);
    if (!entry) break;
    steps.push({ fromState: entry.fromState, toState: current, entry });
    current = entry.fromState;
    currentKey = stateKey(current);
  }
  steps.reverse();

  // State machine to categorise steps
  type Phase = "PRE_BOARD" | "ON_PT" | "POST_ALIGHT";
  let phase: Phase = "PRE_BOARD";

  const walkToStation: RouteSegment[] = [];
  const ptSegments: RouteSegment[] = [];
  const walkFromStation: RouteSegment[] = [];
  let totalWaitTimeMin = 0;

  // Buffer for walk segments between PT legs (transfer walks or final walk)
  let pendingWalkSegments: RouteSegment[] = [];

  function buildWalkSegment(
    edgeId: number | null,
    fromNodeId: number,
    toNodeId: number,
    distM: number,
    timeMin: number
  ): RouteSegment {
    return {
      edgeId: edgeId ?? -1,
      // Always use actual travel direction
      startNode: fromNodeId,
      endNode: toNodeId,
      mode: "walk",
      distanceM: distM,
      estimatedTimeMin: timeMin,
    };
  }

  function findLineForState(state: ProductNode): PTLine | null {
    if (state.mode.tag !== "pt") return null;
    const entries = stopIndex.get(state.nodeId) ?? [];
    for (const { line } of entries) {
      if (line.id === state.mode.lineId) return line;
    }
    return null;
  }

  for (const { fromState, toState, entry } of steps) {
    const { edgeId, distanceM, costMin } = entry;

    if (phase === "PRE_BOARD") {
      if (fromState.mode.tag === "walk" && toState.mode.tag === "walk") {
        // Walking before first boarding
        const seg = buildWalkSegment(
          edgeId,
          fromState.nodeId,
          toState.nodeId,
          distanceM,
          costMin
        );
        walkToStation.push(seg);
      } else if (fromState.mode.tag === "walk" && toState.mode.tag === "pt") {
        // Boarding (wait cost)
        totalWaitTimeMin += costMin;
        phase = "ON_PT";
      }
    } else if (phase === "ON_PT") {
      if (fromState.mode.tag === "pt" && toState.mode.tag === "pt") {
        // Riding on PT
        const line = findLineForState(fromState);
        const edge = edgeId !== null ? edgeMap.get(edgeId) : null;
        let actualDist = distanceM;
        if (edge?.distance_m) actualDist = edge.distance_m;

        const seg: RouteSegment = {
          edgeId: edgeId ?? -1,
          // Use actual travel direction (fromState → toState), not the stored edge direction
          startNode: fromState.nodeId,
          endNode: toState.nodeId,
          mode: fromState.mode.lineType === "bus" ? "bus" : "train",
          ptLineId: fromState.mode.lineId,
          ptLineName: line?.name,
          distanceM: actualDist,
          estimatedTimeMin: costMin,
        };
        ptSegments.push(seg);
      } else if (fromState.mode.tag === "pt" && toState.mode.tag === "walk") {
        // Alighting (zero cost) — switch to POST_ALIGHT
        phase = "POST_ALIGHT";
        pendingWalkSegments = [];
      }
    } else {
      // POST_ALIGHT
      if (fromState.mode.tag === "walk" && toState.mode.tag === "walk") {
        // Walking after alighting (transfer walk or final walk)
        const seg = buildWalkSegment(
          edgeId,
          fromState.nodeId,
          toState.nodeId,
          distanceM,
          costMin
        );
        pendingWalkSegments.push(seg);
      } else if (fromState.mode.tag === "walk" && toState.mode.tag === "pt") {
        // Transfer boarding — flush pending walk into ptSegments, restart ON_PT
        ptSegments.push(...pendingWalkSegments);
        pendingWalkSegments = [];
        totalWaitTimeMin += costMin;
        phase = "ON_PT";
      }
    }
  }

  // Flush any remaining pending walk segments as the final walk
  walkFromStation.push(...pendingWalkSegments);

  return { walkToStation, ptSegments, walkFromStation, totalWaitTimeMin };
}

// ---------------------------------------------------------------------------
// Main PT routing function
// ---------------------------------------------------------------------------

export async function findPTRoute(
  graph: ExtendedMapGraph,
  startNodeId: number,
  endNodeId: number,
  options: {
    scale?: number;
    ptOptimization?: PTOptimization;
    maxWalkDistanceM?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  } = {}
): Promise<PTRoutingResult> {
  const {
    scale = 100,
    ptOptimization = "fastest",
    maxWalkDistanceM = MAX_WALK_DISTANCE_M,
  } = options;

  const nodeMap = new Map<number, Node>();
  for (const node of graph.nodes) nodeMap.set(node.id, node);

  const edgeMap = new Map<number, Edge>();
  for (const edge of graph.edges) edgeMap.set(edge.id, edge);

  const startNode = nodeMap.get(startNodeId);
  const endNode = nodeMap.get(endNodeId);
  if (!startNode || !endNode) return failResult("Start or end node not found");

  const busLines = graph.bus_lines ?? [];
  const trainLines = graph.train_lines ?? [];

  const walkAdj = buildAdjacencyList(graph.edges, graph.nodes);
  const reverseWalkAdj = buildReverseWalkAdjacency(graph.edges, graph.nodes);
  const stopIndex = buildStopIndex(busLines, trainLines);
  const designatedStops = buildDesignatedStopSet(graph.nodes);

  // Pre-compute 2km walk-reachability sets.
  // boardableStops: stops reachable FROM start (forward walk from startNodeId).
  // alightableStops: stops that can REACH endNode (reverse walk from endNodeId).
  const startReach = walkReachabilitySet(startNodeId, walkAdj, nodeMap, scale, maxWalkDistanceM);
  const endReach = walkReachabilitySet(endNodeId, reverseWalkAdj, nodeMap, scale, maxWalkDistanceM);

  const boardableStops = new Set<number>();
  for (const [nodeId] of startReach) {
    if (designatedStops.has(nodeId)) boardableStops.add(nodeId);
  }

  const alightableStops = new Set<number>();
  for (const [nodeId] of endReach) {
    if (designatedStops.has(nodeId)) alightableStops.add(nodeId);
  }

  // Check how many boardable stops are actually on a PT line
  const boardableOnLine = [...boardableStops].filter((id) => stopIndex.has(id));
  const alightableOnLine = [...alightableStops].filter((id) => stopIndex.has(id));

  console.log(
    `[ptRouting] start=${startNodeId} end=${endNodeId}` +
    `\n  boardableStops(${boardableStops.size}): [${[...boardableStops].join(",")}]` +
    `\n  boardableOnLine(${boardableOnLine.length}): [${boardableOnLine.join(",")}]` +
    `\n  alightableStops(${alightableStops.size}): [${[...alightableStops].join(",")}]` +
    `\n  alightableOnLine(${alightableOnLine.length}): [${alightableOnLine.join(",")}]` +
    `\n  stopIndex covers ${stopIndex.size} nodes, designatedStops: ${designatedStops.size}` +
    `\n  optimization: ${ptOptimization}`
  );

  if (boardableStops.size === 0 || alightableStops.size === 0) {
    console.log("[ptRouting] FAIL: no designated stops within 2km of start or end");
    return failResult("No public transport stations within 2km of start or destination");
  }

  if (boardableOnLine.length === 0) {
    console.log("[ptRouting] FAIL: boardable stops exist but none are on any PT line");
    return failResult("Nearby stops are not served by any public transport line");
  }

  if (alightableOnLine.length === 0) {
    console.log("[ptRouting] FAIL: alightable stops exist but none are on any PT line");
    return failResult("No public transport stops near the destination");
  }

  // Run product-graph Dijkstra
  const result = productGraphDijkstra(
    startNodeId,
    endNodeId,
    walkAdj,
    stopIndex,
    designatedStops,
    boardableStops,
    nodeMap,
    scale,
    ptOptimization
  );

  if (!result) {
    console.log("[ptRouting] No PT route found");
    return failResult("No public transport connection between these locations");
  }

  const { walkToStation, ptSegments, walkFromStation, totalWaitTimeMin } =
    reconstructPath(result, startNodeId, edgeMap, stopIndex);

  // Enforce 2km final-walk limit: the last walk leg (station → destination) must
  // have come from an alightable stop. If the alight stop is not in alightableStops,
  // the walk from there exceeds 2km.
  const finalWalkDistM = walkFromStation.reduce((s, seg) => s + seg.distanceM, 0);
  if (finalWalkDistM > maxWalkDistanceM) {
    console.log(`[ptRouting] Final walk ${finalWalkDistM.toFixed(0)}m exceeds ${maxWalkDistanceM}m limit`);
    return failResult(`Walk from PT stop to destination is ${(finalWalkDistM / 1000).toFixed(1)}km — exceeds 2km limit`);
  }

  const allSegments = [...walkToStation, ...ptSegments, ...walkFromStation];
  const totalDistanceM = allSegments.reduce((s, seg) => s + seg.distanceM, 0);
  const totalTimeMin = allSegments.reduce((s, seg) => s + seg.estimatedTimeMin, 0) + totalWaitTimeMin;

  console.log(`[ptRouting] Route found: ${walkToStation.length} walk-to + ${ptSegments.length} PT + ${walkFromStation.length} walk-from segments, ${totalTimeMin.toFixed(1)} min`);

  return {
    success: true,
    walkToStation,
    ptSegments,
    walkFromStation,
    totalDistanceM,
    totalTimeMin,
    waitTimeMin: totalWaitTimeMin,
  };
}

// ---------------------------------------------------------------------------
// Compare PT route with direct walking
// ---------------------------------------------------------------------------

export async function findBestPTRoute(
  graph: ExtendedMapGraph,
  startNodeId: number,
  endNodeId: number,
  options: {
    scale?: number;
    ptOptimization?: PTOptimization;
    maxWalkDistanceM?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  } = {}
): Promise<PTRoutingResult> {
  const ptResult = await findPTRoute(graph, startNodeId, endNodeId, options);

  // Also get direct walking route for comparison
  const walkResult = await dijkstra(graph, startNodeId, endNodeId, "walk", {
    scale: options.scale,
  });

  // If no PT route could be found at all, report failure — do not silently
  // fall back to walking (the player explicitly chose a PT mode).
  if (!ptResult.success) {
    console.log(`[ptRouting] PT failed (${ptResult.error ?? "no route"}), reporting no path found`);
    return failResult(ptResult.error ?? "No public transport route found");
  }

  // If walking is faster than the PT route, still prefer PT — the player
  // explicitly chose a PT mode, so we honour that choice.
  if (walkResult.success && walkResult.estimatedTimeMin < ptResult.totalTimeMin) {
    console.log(`[ptRouting] Walking (${walkResult.estimatedTimeMin.toFixed(1)}min) would be faster than PT (${ptResult.totalTimeMin.toFixed(1)}min), but PT was requested — returning PT route`);
  }

  return ptResult;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function failResult(error: string): PTRoutingResult {
  return {
    success: false,
    walkToStation: [],
    ptSegments: [],
    walkFromStation: [],
    totalDistanceM: 0,
    totalTimeMin: 0,
    waitTimeMin: 0,
    error,
  };
}

async function fallbackToWalking(
  graph: ExtendedMapGraph,
  startNodeId: number,
  endNodeId: number,
  options: {
    scale?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  }
): Promise<PTRoutingResult> {
  const walkResult = await dijkstra(graph, startNodeId, endNodeId, "walk", {
    scale: options.scale,
    onStateChange: options.onStateChange,
    animationDelayMs: options.animationDelayMs,
  });

  if (walkResult.success) {
    return {
      success: true,
      walkToStation: [],
      ptSegments: [],
      walkFromStation: walkResult.segments,
      totalDistanceM: walkResult.totalDistanceM,
      totalTimeMin: walkResult.estimatedTimeMin,
      waitTimeMin: 0,
    };
  }

  return failResult("No public transport or walking route found");
}
