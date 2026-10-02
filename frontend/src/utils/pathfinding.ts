/**
 * Dijkstra pathfinding implementation for traffic simulation
 */

import { carEmissionFactor } from "@/lib/map/car-emissions";
import { canUseEdge } from "@/lib/map/edge-rules";
import { exceedsModeLimit, modeLimitM } from "@/lib/map/trip-limits";
import type { Edge, Node, MapGraph } from "../types/mapTypes";
import type {
  TransportMode,
  CarOptimization,
  EdgeTrafficData,
  PathfindingResult,
  RouteSegment,
  PathfindingState,
  SegmentMode,
} from "../types/routeTypes";

// Default speeds in km/h
const WALK_SPEED_KMH = 5;
const BIKE_SPEED_KMH = 20;
const DEFAULT_CAR_SPEED_KMH = 50;

/**
 * Calculate Euclidean distance between two nodes in meters
 */
export function calculateDistance(
  node1: Node,
  node2: Node,
  scale: number = 100,
): number {
  const dx = node2.x_position - node1.x_position;
  const dy = node2.y_position - node1.y_position;
  return Math.sqrt(dx * dx + dy * dy) * scale;
}

/**
 * Build adjacency list from edges
 */
export function buildAdjacencyList(
  edges: Edge[],
  nodes: Node[],
): Map<number, { edge: Edge; neighbor: number }[]> {
  const adjacency = new Map<number, { edge: Edge; neighbor: number }[]>();

  // Initialize all nodes
  for (const node of nodes) {
    adjacency.set(node.id, []);
  }

  // Add edges in forward direction only (directed graph)
  // Maps have explicit reverse edges for bidirectional streets
  for (const edge of edges) {
    adjacency.get(edge.start_node)?.push({
      edge,
      neighbor: edge.end_node,
    });
  }

  return adjacency;
}

/**
 * Who may use a link. The rule itself lives in `lib/map/edge-rules.ts` — it is
 * the simulation's, and a car is refused on a gate as well as on a path.
 * Re-exported here because `ptRouting.ts` has always taken it from this module.
 */
export { canUseEdge };

/**
 * Calculate edge weight based on transport mode and optimization
 */
export function calculateEdgeWeight(
  edge: Edge,
  startNode: Node,
  endNode: Node,
  mode: TransportMode,
  optimization: CarOptimization = "time",
  trafficData?: EdgeTrafficData[],
  scale: number = 100,
): number | null {
  // Check if edge can be used
  if (!canUseEdge(edge, mode)) {
    return null;
  }

  // Calculate distance
  const distanceM =
    edge.distance_m ?? calculateDistance(startNode, endNode, scale);
  const distanceKm = distanceM / 1000;

  switch (mode) {
    case "walk":
      // Weight = time in minutes
      return (distanceKm / WALK_SPEED_KMH) * 60;

    case "bike":
      // Weight = time in minutes
      return (distanceKm / BIKE_SPEED_KMH) * 60;

    case "car": {
      const speedLimit = edge.street_edge?.speed_limit ?? DEFAULT_CAR_SPEED_KMH;

      // The speed the link actually ran at last round. Time and CO2 both
      // depend on it — the simulation's CO2 is a curve over the link's
      // observed speed — so both read it; only the shortest route does not.
      let actualSpeed = speedLimit;
      if (trafficData) {
        const traffic = trafficData.find((t) => t.edgeId === edge.id);
        if (traffic) {
          actualSpeed = traffic.avgSpeedKmh;
        }
      }

      switch (optimization) {
        case "distance":
          return distanceM; // Pure distance in meters

        case "co2":
          // Worse in a jam and a little worse above ~70 km/h: the simulation's
          // own curve, see lib/map/car-emissions.ts.
          return distanceM * carEmissionFactor(actualSpeed);

        case "time":
        default:
          // Time in minutes
          return (distanceKm / actualSpeed) * 60;
      }
    }

    default:
      return null;
  }
}

/**
 * Dijkstra pathfinding with animation support
 */
export async function dijkstra(
  graph: MapGraph,
  startNodeId: number,
  endNodeId: number,
  mode: TransportMode,
  options: {
    optimization?: CarOptimization;
    trafficData?: EdgeTrafficData[];
    scale?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  } = {},
): Promise<PathfindingResult> {
  const {
    optimization = "time",
    trafficData,
    scale = 100,
    onStateChange,
    animationDelayMs = 0,
  } = options;

  console.log(`[dijkstra] Starting pathfinding:`, {
    mode,
    optimization,
    from: startNodeId,
    to: endNodeId,
    nodes: graph.nodes.length,
    edges: graph.edges.length,
  });

  // Build node map for quick lookup
  const nodeMap = new Map<number, Node>();
  for (const node of graph.nodes) {
    nodeMap.set(node.id, node);
  }

  // Build adjacency list
  const adjacency = buildAdjacencyList(graph.edges, graph.nodes);

  // Log usable edges for this mode
  const usableEdges = graph.edges.filter((e) => canUseEdge(e, mode));
  console.log(
    `[dijkstra] Found ${usableEdges.length}/${graph.edges.length} usable edges for mode ${mode}`,
  );

  if (usableEdges.length === 0) {
    console.error(`[dijkstra] No usable edges found for mode ${mode}!`);
    console.log("[dijkstra] Sample edges:", graph.edges.slice(0, 3));
  }

  // Initialize Dijkstra data structures
  const distances = new Map<number, number>();
  const previous = new Map<number, { nodeId: number; edge: Edge }>();
  const visited = new Set<number>();
  const unvisited = new Set<number>(graph.nodes.map((n) => n.id));
  const exploredEdges = new Set<number>();
  const previousEdges = new Map<number, number>(); // nodeId -> edgeId
  let relaxedEdge: number | null = null;

  // Set initial distances
  for (const node of graph.nodes) {
    distances.set(node.id, node.id === startNodeId ? 0 : Infinity);
  }

  // Helper to update state for animation
  const updateState = async (
    currentNode: number | null,
    isComplete: boolean,
  ) => {
    if (onStateChange) {
      onStateChange({
        isRunning: !isComplete,
        visitedNodes: new Set(visited),
        currentNode,
        tentativeDistances: new Map(distances),
        previousNodes: new Map(
          Array.from(previous.entries()).map(([k, v]) => [k, v.nodeId]),
        ),
        finalPath: null,
        isComplete,
        exploredEdges: new Set(exploredEdges),
        relaxedEdge,
        previousEdges: new Map(previousEdges),
      });
      // Clear transient relaxedEdge after emitting
      relaxedEdge = null;

      if (animationDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, animationDelayMs));
      }
    }
  };

  // Main Dijkstra loop
  while (unvisited.size > 0) {
    // Find unvisited node with minimum distance
    let currentNode: number | null = null;
    let minDistance = Infinity;

    for (const nodeId of unvisited) {
      const dist = distances.get(nodeId) ?? Infinity;
      if (dist < minDistance) {
        minDistance = dist;
        currentNode = nodeId;
      }
    }

    // No reachable nodes left
    if (currentNode === null || minDistance === Infinity) {
      console.warn(
        `[dijkstra] No path found from ${startNodeId} to ${endNodeId} (mode: ${mode}, visited: ${visited.size}/${graph.nodes.length})`,
      );
      if (onStateChange) {
        onStateChange({
          isRunning: false,
          visitedNodes: new Set(visited),
          currentNode: null,
          tentativeDistances: new Map(distances),
          previousNodes: new Map(
            Array.from(previous.entries()).map(([k, v]) => [k, v.nodeId]),
          ),
          finalPath: null,
          isComplete: true,
          exploredEdges: new Set(exploredEdges),
          relaxedEdge: null,
          previousEdges: new Map(previousEdges),
        });
      }
      return {
        success: false,
        path: [],
        segments: [],
        totalDistanceM: 0,
        estimatedTimeMin: 0,
        error: "No path found - destination unreachable",
      };
    }

    // Found destination
    if (currentNode === endNodeId) {
      break;
    }

    // Mark as visited
    unvisited.delete(currentNode);
    visited.add(currentNode);

    await updateState(currentNode, false);

    // Process neighbors
    const neighbors = adjacency.get(currentNode) ?? [];
    const currentNodeData = nodeMap.get(currentNode);

    if (!currentNodeData) continue;

    for (const { edge, neighbor } of neighbors) {
      if (visited.has(neighbor)) continue;

      const neighborNode = nodeMap.get(neighbor);
      if (!neighborNode) continue;

      // Determine correct start/end for weight calculation
      const isForward = edge.start_node === currentNode;
      const edgeStart = isForward ? currentNodeData : neighborNode;
      const edgeEnd = isForward ? neighborNode : currentNodeData;

      const weight = calculateEdgeWeight(
        edge,
        edgeStart,
        edgeEnd,
        mode,
        optimization,
        trafficData,
        scale,
      );

      if (weight === null) continue; // Edge not usable for this mode

      exploredEdges.add(edge.id);

      const newDistance = (distances.get(currentNode) ?? Infinity) + weight;
      const currentDistance = distances.get(neighbor) ?? Infinity;

      if (newDistance < currentDistance) {
        distances.set(neighbor, newDistance);
        previous.set(neighbor, { nodeId: currentNode, edge });
        previousEdges.set(neighbor, edge.id);
        relaxedEdge = edge.id;
      }
    }
  }

  // Reconstruct path
  const path: number[] = [];
  const segments: RouteSegment[] = [];
  let current = endNodeId;

  while (current !== startNodeId) {
    const prev = previous.get(current);
    if (!prev) {
      if (onStateChange) {
        onStateChange({
          isRunning: false,
          visitedNodes: new Set(visited),
          currentNode: null,
          tentativeDistances: new Map(distances),
          previousNodes: new Map(
            Array.from(previous.entries()).map(([k, v]) => [k, v.nodeId]),
          ),
          finalPath: null,
          isComplete: true,
          exploredEdges: new Set(exploredEdges),
          relaxedEdge: null,
          previousEdges: new Map(previousEdges),
        });
      }
      return {
        success: false,
        path: [],
        segments: [],
        totalDistanceM: 0,
        estimatedTimeMin: 0,
        error: "Path reconstruction failed",
      };
    }

    path.unshift(current);

    // Build segment
    const edge = prev.edge;
    const startNode = nodeMap.get(prev.nodeId);
    const endNode = nodeMap.get(current);

    if (startNode && endNode) {
      const distanceM =
        edge.distance_m ?? calculateDistance(startNode, endNode, scale);
      let timeMin: number;

      switch (mode) {
        case "walk":
          timeMin = (distanceM / 1000 / WALK_SPEED_KMH) * 60;
          break;
        case "bike":
          timeMin = (distanceM / 1000 / BIKE_SPEED_KMH) * 60;
          break;
        case "car": {
          const speed = edge.street_edge?.speed_limit ?? DEFAULT_CAR_SPEED_KMH;
          timeMin = (distanceM / 1000 / speed) * 60;
          break;
        }
        default:
          timeMin = 0;
      }

      // Convert TransportMode to SegmentMode (public transport handled separately)
      const segmentMode: SegmentMode = mode === "public" ? "walk" : mode;

      segments.unshift({
        edgeId: edge.id,
        startNode: edge.start_node,
        endNode: edge.end_node,
        mode: segmentMode,
        distanceM,
        estimatedTimeMin: timeMin,
      });
    }

    current = prev.nodeId;
  }
  path.unshift(startNodeId);

  // Calculate totals
  const totalDistanceM = segments.reduce((sum, s) => sum + s.distanceM, 0);
  const estimatedTimeMin = segments.reduce(
    (sum, s) => sum + s.estimatedTimeMin,
    0,
  );

  console.log(`[dijkstra] Path found:`, {
    pathNodes: path.length,
    segments: segments.length,
    totalDistanceM,
    estimatedTimeMin,
    segmentSample: segments.slice(0, 2),
  });

  // Final state update with path
  if (onStateChange) {
    onStateChange({
      isRunning: false,
      visitedNodes: new Set(visited),
      currentNode: null,
      tentativeDistances: new Map(distances),
      previousNodes: new Map(
        Array.from(previous.entries()).map(([k, v]) => [k, v.nodeId]),
      ),
      finalPath: path,
      isComplete: true,
      exploredEdges: new Set(exploredEdges),
      relaxedEdge: null,
      previousEdges: new Map(previousEdges),
    });
  }

  return {
    success: true,
    path,
    segments,
    totalDistanceM,
    estimatedTimeMin,
  };
}

/**
 * A route the player has asked for, capped.
 *
 * The cap is the one thing this wrapper adds over `dijkstra`: a route may come
 * back perfectly well and still be one nobody would walk. `TOO_FAR` is a
 * distinct failure from "no route" because the two want different sentences on
 * screen — one says take another line, the other says it is too far on foot.
 *
 * Deliberately **not** inside `dijkstra`: `ptRouting` runs its own walking
 * searches through it for the first and last mile, and those are capped at 2 km
 * by the PT router itself. A cap here would be a second, looser opinion about
 * the same leg.
 */
export const TOO_FAR = "too-far";

/**
 * Found a way to work and none back. A refusal of its own, because it needs its
 * own sentence: the graph is directed, so a one-way street can make the
 * destination a place you can reach and not leave.
 */
export const NO_WAY_HOME = "no-way-home";

export async function findPath(
  graph: MapGraph,
  startNodeId: number,
  endNodeId: number,
  mode: TransportMode,
  options: {
    optimization?: CarOptimization;
    trafficData?: EdgeTrafficData[];
    scale?: number;
    onStateChange?: (state: PathfindingState) => void;
    animationDelayMs?: number;
  } = {},
): Promise<PathfindingResult> {
  if (mode === "public") {
    // Public transport routing is handled separately in ptRouting.ts
    return {
      success: false,
      path: [],
      segments: [],
      totalDistanceM: 0,
      estimatedTimeMin: 0,
      error: "Use ptRouting for public transport",
    };
  }

  const result = await dijkstra(graph, startNodeId, endNodeId, mode, options);

  if (result.success && exceedsModeLimit(mode, result.totalDistanceM)) {
    console.log(
      `[findPath] ${(result.totalDistanceM / 1000).toFixed(1)} km by ${mode} is past the ` +
        `${(modeLimitM(mode)! / 1000).toFixed(0)} km limit — refusing the route`,
    );
    return {
      success: false,
      path: [],
      segments: [],
      totalDistanceM: result.totalDistanceM,
      estimatedTimeMin: result.estimatedTimeMin,
      error: TOO_FAR,
    };
  }

  return result;
}
