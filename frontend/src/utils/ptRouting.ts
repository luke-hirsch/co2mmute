/**
 * Public Transport Routing
 *
 * Direction-aware multi-modal routing:
 *   walk to station -> PT route (with optional transfer) -> walk to destination
 *
 * Key rule: PT lines only travel FORWARD through their stops array.
 * stops[i] -> stops[j] is only valid when i < j.
 * To go "backwards," use a different line (e.g., S42 instead of S41).
 */

import type { Node, Edge } from "../types/mapTypes";
import type {
  PTLine,
  RouteSegment,
  PTRoutingResult,
  ExtendedMapGraph,
  PathfindingState,
  StationLineInfo,
  PTRouteCandidate,
} from "../types/routeTypes";
import { dijkstra, calculateDistance } from "./pathfinding";

const WALK_SPEED_KMH = 5;
const MAX_WALK_DISTANCE_M = 2000;
const TRANSFER_PENALTY_MIN = 5;

interface StationWithDistance {
  nodeId: number;
  walkDistanceM: number;
  walkTimeMin: number;
}

// ---------------------------------------------------------------------------
// 1. Find nearby stations within walking distance
// ---------------------------------------------------------------------------

function findNearbyStations(
  fromNode: Node,
  nodes: Node[],
  scale: number,
  maxDistanceM: number = MAX_WALK_DISTANCE_M
): StationWithDistance[] {
  const stations: StationWithDistance[] = [];

  for (const node of nodes) {
    const nodeTypes = node.node_type.map((t) => t.name);
    if (!nodeTypes.includes("station") && !nodeTypes.includes("bus_stop")) {
      continue;
    }

    const distance = calculateDistance(fromNode, node, scale);
    if (distance <= maxDistanceM) {
      stations.push({
        nodeId: node.id,
        walkDistanceM: distance,
        walkTimeMin: (distance / 1000 / WALK_SPEED_KMH) * 60,
      });
    }
  }

  stations.sort((a, b) => a.walkDistanceM - b.walkDistanceM);
  return stations;
}

// ---------------------------------------------------------------------------
// 2. Build station index: Map<nodeId, StationLineInfo[]>
// ---------------------------------------------------------------------------

function buildStationIndex(
  busLines: PTLine[],
  trainLines: PTLine[]
): Map<number, StationLineInfo[]> {
  const index = new Map<number, StationLineInfo[]>();

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

// ---------------------------------------------------------------------------
// 3. Calculate travel time along a PT line (direction-aware)
// ---------------------------------------------------------------------------

function calculateLegTravelTime(
  line: PTLine,
  fromStopIdx: number,
  toStopIdx: number,
  edgeMap: Map<number, Edge>,
  nodeMap: Map<number, Node>,
  scale: number
): { timeMin: number; distanceM: number; edgeIds: number[] } {
  // Direction check: only forward travel
  if (fromStopIdx >= toStopIdx) {
    return { timeMin: Infinity, distanceM: Infinity, edgeIds: [] };
  }

  let totalDistance = 0;
  const usedEdgeIds: number[] = [];

  // edges[i] connects stops[i] to stops[i+1], so slice [fromStopIdx, toStopIdx)
  const edgeSlice = line.edges.slice(fromStopIdx, toStopIdx);

  if (edgeSlice.length > 0) {
    for (const edgeId of edgeSlice) {
      const edge = edgeMap.get(edgeId);
      if (edge) {
        if (edge.distance_m) {
          totalDistance += edge.distance_m;
        } else {
          const start = nodeMap.get(edge.start_node);
          const end = nodeMap.get(edge.end_node);
          if (start && end) {
            totalDistance += calculateDistance(start, end, scale);
          }
        }
        usedEdgeIds.push(edgeId);
      }
    }
  } else {
    // Fallback: estimate from stop positions
    for (let i = fromStopIdx; i < toStopIdx; i++) {
      const from = nodeMap.get(line.stops[i]);
      const to = nodeMap.get(line.stops[i + 1]);
      if (from && to) {
        totalDistance += calculateDistance(from, to, scale);
      }
    }
  }

  // Use line-type-specific speed
  const speedKmh = line.type === "train" ? 40 : 30;
  const timeMin = (totalDistance / 1000 / speedKmh) * 60;

  return { timeMin, distanceM: totalDistance, edgeIds: usedEdgeIds };
}

// ---------------------------------------------------------------------------
// 4. Find direct routes (single line, forward direction only)
// ---------------------------------------------------------------------------

function findDirectRoutes(
  fromStationId: number,
  toStationId: number,
  stationIndex: Map<number, StationLineInfo[]>
): { line: PTLine; fromStopIdx: number; toStopIdx: number }[] {
  const fromEntries = stationIndex.get(fromStationId) ?? [];
  const toEntries = stationIndex.get(toStationId) ?? [];
  const routes: { line: PTLine; fromStopIdx: number; toStopIdx: number }[] = [];

  for (const from of fromEntries) {
    for (const to of toEntries) {
      // Same line, same type, AND forward direction
      if (
        from.line.id === to.line.id &&
        from.line.type === to.line.type &&
        from.stopIndex < to.stopIndex
      ) {
        routes.push({
          line: from.line,
          fromStopIdx: from.stopIndex,
          toStopIdx: to.stopIndex,
        });
      }
    }
  }

  return routes;
}

// ---------------------------------------------------------------------------
// 5. Find transfer routes (two lines, one transfer station)
// ---------------------------------------------------------------------------

function findTransferRoutes(
  fromStationId: number,
  toStationId: number,
  stationIndex: Map<number, StationLineInfo[]>
): {
  leg1: { line: PTLine; fromStopIdx: number; toStopIdx: number };
  leg2: { line: PTLine; fromStopIdx: number; toStopIdx: number };
  transferStationId: number;
}[] {
  const routes: ReturnType<typeof findTransferRoutes> = [];

  // Check every station as a potential transfer point
  for (const [transferNodeId, transferEntries] of stationIndex) {
    if (transferNodeId === fromStationId || transferNodeId === toStationId) {
      continue;
    }

    // Only consider stations with 2+ lines (actual transfer points)
    if (transferEntries.length < 2) continue;

    // Find leg1: fromStation -> transferStation (forward)
    const leg1Options = findDirectRoutes(fromStationId, transferNodeId, stationIndex);
    if (leg1Options.length === 0) continue;

    // Find leg2: transferStation -> toStation (forward)
    const leg2Options = findDirectRoutes(transferNodeId, toStationId, stationIndex);
    if (leg2Options.length === 0) continue;

    for (const leg1 of leg1Options) {
      for (const leg2 of leg2Options) {
        // Skip if same line (that's a direct route, not a transfer)
        if (leg1.line.id === leg2.line.id && leg1.line.type === leg2.line.type) {
          continue;
        }

        routes.push({
          leg1,
          leg2,
          transferStationId: transferNodeId,
        });
      }
    }
  }

  return routes;
}

// ---------------------------------------------------------------------------
// 6. Build PT segments from edge IDs (trust edge direction)
// ---------------------------------------------------------------------------

function buildPTSegments(
  line: PTLine,
  fromStopIdx: number,
  toStopIdx: number,
  edgeMap: Map<number, Edge>,
  nodeMap: Map<number, Node>,
  scale: number
): RouteSegment[] {
  const segments: RouteSegment[] = [];
  const edgeSlice = line.edges.slice(fromStopIdx, toStopIdx);
  const mode = line.type === "bus" ? "bus" : "train";
  const speedKmh = line.type === "train" ? 40 : 30;

  if (edgeSlice.length > 0) {
    for (const edgeId of edgeSlice) {
      const edge = edgeMap.get(edgeId);
      if (!edge) continue;

      let dist = edge.distance_m;
      if (!dist) {
        const s = nodeMap.get(edge.start_node);
        const e = nodeMap.get(edge.end_node);
        dist = s && e ? calculateDistance(s, e, scale) : 0;
      }

      segments.push({
        edgeId: edge.id,
        startNode: edge.start_node,
        endNode: edge.end_node,
        mode,
        ptLineId: line.id,
        distanceM: dist,
        estimatedTimeMin: (dist / 1000 / speedKmh) * 60,
      });
    }
  } else {
    // No edges available — single segment placeholder
    const fromNode = nodeMap.get(line.stops[fromStopIdx]);
    const toNode = nodeMap.get(line.stops[toStopIdx]);
    const dist = fromNode && toNode ? calculateDistance(fromNode, toNode, scale) : 0;

    segments.push({
      edgeId: -1,
      startNode: line.stops[fromStopIdx],
      endNode: line.stops[toStopIdx],
      mode,
      ptLineId: line.id,
      distanceM: dist,
      estimatedTimeMin: (dist / 1000 / speedKmh) * 60,
    });
  }

  return segments;
}

// ---------------------------------------------------------------------------
// 7. Main PT routing function
// ---------------------------------------------------------------------------

export async function findPTRoute(
  graph: ExtendedMapGraph,
  startNodeId: number,
  endNodeId: number,
  options: {
    scale?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  } = {}
): Promise<PTRoutingResult> {
  const { scale = 100 } = options;

  const nodeMap = new Map<number, Node>();
  for (const node of graph.nodes) {
    nodeMap.set(node.id, node);
  }

  const edgeMap = new Map<number, Edge>();
  for (const edge of graph.edges) {
    edgeMap.set(edge.id, edge);
  }

  const startNode = nodeMap.get(startNodeId);
  const endNode = nodeMap.get(endNodeId);

  if (!startNode || !endNode) {
    return failResult("Start or end node not found");
  }

  // 1. Find nearby stations
  const startStations = findNearbyStations(startNode, graph.nodes, scale);
  const endStations = findNearbyStations(endNode, graph.nodes, scale);

  if (startStations.length === 0 || endStations.length === 0) {
    console.log("[ptRouting] No stations within 2km, PT not available");
    return failResult("No public transport stations within walking distance (2km)");
  }

  // 2. Build station index
  const busLines = graph.bus_lines ?? [];
  const trainLines = graph.train_lines ?? [];
  const stationIndex = buildStationIndex(busLines, trainLines);

  // 3. Evaluate all route candidates
  const candidates: PTRouteCandidate[] = [];

  for (const startStation of startStations) {
    for (const endStation of endStations) {
      if (startStation.nodeId === endStation.nodeId) continue;

      // 3a. Direct routes
      const directRoutes = findDirectRoutes(
        startStation.nodeId,
        endStation.nodeId,
        stationIndex
      );

      for (const route of directRoutes) {
        const travel = calculateLegTravelTime(
          route.line,
          route.fromStopIdx,
          route.toStopIdx,
          edgeMap,
          nodeMap,
          scale
        );
        if (!isFinite(travel.timeMin)) continue;

        const waitTime = route.line.interval / 2;
        const totalTime =
          startStation.walkTimeMin + waitTime + travel.timeMin + endStation.walkTimeMin;
        const totalDist =
          startStation.walkDistanceM + travel.distanceM + endStation.walkDistanceM;

        candidates.push({
          type: "direct",
          startStation: {
            nodeId: startStation.nodeId,
            walkTimeMin: startStation.walkTimeMin,
            walkDistanceM: startStation.walkDistanceM,
          },
          endStation: {
            nodeId: endStation.nodeId,
            walkTimeMin: endStation.walkTimeMin,
            walkDistanceM: endStation.walkDistanceM,
          },
          legs: [route],
          totalTimeMin: totalTime,
          totalDistanceM: totalDist,
          waitTimeMin: waitTime,
        });
      }

      // 3b. Transfer routes
      const transferRoutes = findTransferRoutes(
        startStation.nodeId,
        endStation.nodeId,
        stationIndex
      );

      for (const route of transferRoutes) {
        const travel1 = calculateLegTravelTime(
          route.leg1.line,
          route.leg1.fromStopIdx,
          route.leg1.toStopIdx,
          edgeMap,
          nodeMap,
          scale
        );
        const travel2 = calculateLegTravelTime(
          route.leg2.line,
          route.leg2.fromStopIdx,
          route.leg2.toStopIdx,
          edgeMap,
          nodeMap,
          scale
        );
        if (!isFinite(travel1.timeMin) || !isFinite(travel2.timeMin)) continue;

        const wait1 = route.leg1.line.interval / 2;
        const wait2 = route.leg2.line.interval / 2;
        const totalWait = wait1 + TRANSFER_PENALTY_MIN + wait2;

        const totalTime =
          startStation.walkTimeMin +
          wait1 +
          travel1.timeMin +
          TRANSFER_PENALTY_MIN +
          wait2 +
          travel2.timeMin +
          endStation.walkTimeMin;

        const totalDist =
          startStation.walkDistanceM +
          travel1.distanceM +
          travel2.distanceM +
          endStation.walkDistanceM;

        candidates.push({
          type: "transfer",
          startStation: {
            nodeId: startStation.nodeId,
            walkTimeMin: startStation.walkTimeMin,
            walkDistanceM: startStation.walkDistanceM,
          },
          endStation: {
            nodeId: endStation.nodeId,
            walkTimeMin: endStation.walkTimeMin,
            walkDistanceM: endStation.walkDistanceM,
          },
          legs: [route.leg1, route.leg2],
          totalTimeMin: totalTime,
          totalDistanceM: totalDist,
          waitTimeMin: totalWait,
        });
      }
    }
  }

  // 4. Sort candidates by total time and try each until walking works
  if (candidates.length === 0) {
    console.log("[ptRouting] No PT route found, falling back to walking");
    return fallbackToWalking(graph, startNodeId, endNodeId, options);
  }

  candidates.sort((a, b) => a.totalTimeMin - b.totalTimeMin);

  const noWalkResult = { success: true, path: [] as number[], segments: [] as RouteSegment[], totalDistanceM: 0, estimatedTimeMin: 0 };

  for (const candidate of candidates) {
    console.log("[ptRouting] Trying route:", {
      type: candidate.type,
      lines: candidate.legs.map((l) => l.line.name),
      startStation: candidate.startStation.nodeId,
      endStation: candidate.endStation.nodeId,
      totalTime: candidate.totalTimeMin.toFixed(1),
    });

    // Build walking segments (skip dijkstra if already at the station)
    const walkToResult = startNodeId === candidate.startStation.nodeId
      ? noWalkResult
      : await dijkstra(graph, startNodeId, candidate.startStation.nodeId, "walk", { scale });

    if (!walkToResult.success) {
      console.log(`[ptRouting] Can't walk to station ${candidate.startStation.nodeId}, trying next`);
      continue;
    }

    const walkFromResult = candidate.endStation.nodeId === endNodeId
      ? noWalkResult
      : await dijkstra(graph, candidate.endStation.nodeId, endNodeId, "walk", { scale });

    if (!walkFromResult.success) {
      console.log(`[ptRouting] Can't walk from station ${candidate.endStation.nodeId}, trying next`);
      continue;
    }

    // Walking works — build PT segments
    const ptSegments: RouteSegment[] = [];
    for (const leg of candidate.legs) {
      const legSegments = buildPTSegments(
        leg.line,
        leg.fromStopIdx,
        leg.toStopIdx,
        edgeMap,
        nodeMap,
        scale
      );
      ptSegments.push(...legSegments);
    }

    const ptDist = ptSegments.reduce((sum, s) => sum + s.distanceM, 0);
    const totalDistanceM = walkToResult.totalDistanceM + ptDist + walkFromResult.totalDistanceM;

    // Recompute total time using actual walk distances
    const walkToTimeMin = walkToResult.estimatedTimeMin;
    const walkFromTimeMin = walkFromResult.estimatedTimeMin;
    const ptTimeMin = candidate.totalTimeMin
      - candidate.startStation.walkTimeMin
      - candidate.endStation.walkTimeMin;
    const totalTimeMin = walkToTimeMin + ptTimeMin + walkFromTimeMin;

    return {
      success: true,
      walkToStation: walkToResult.segments,
      ptSegments,
      walkFromStation: walkFromResult.segments,
      totalDistanceM,
      totalTimeMin,
      waitTimeMin: candidate.waitTimeMin,
    };
  }

  // All candidates had unreachable walking segments
  console.log("[ptRouting] No candidate with walkable stations, falling back to walking");
  return fallbackToWalking(graph, startNodeId, endNodeId, options);
}

// ---------------------------------------------------------------------------
// 8. Compare PT route with direct walking
// ---------------------------------------------------------------------------

export async function findBestPTRoute(
  graph: ExtendedMapGraph,
  startNodeId: number,
  endNodeId: number,
  options: {
    scale?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  } = {}
): Promise<PTRoutingResult> {
  const ptResult = await findPTRoute(graph, startNodeId, endNodeId, options);

  // Also get direct walking route for comparison
  const walkResult = await dijkstra(graph, startNodeId, endNodeId, "walk", {
    scale: options.scale,
  });

  // If PT failed or walking is faster, return walking
  if (
    !ptResult.success ||
    (walkResult.success && walkResult.estimatedTimeMin < ptResult.totalTimeMin)
  ) {
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
