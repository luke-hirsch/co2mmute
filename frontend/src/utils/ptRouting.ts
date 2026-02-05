/**
 * Public Transport Routing
 *
 * Handles multi-modal routing: walk to station -> PT route -> walk to destination
 */

import type { Node } from "../types/mapTypes";
import type {
  PTLine,
  RouteSegment,
  PTRoutingResult,
  ExtendedMapGraph,
  PathfindingState,
} from "../types/routeTypes";
import { dijkstra, calculateDistance } from "./pathfinding";

const WALK_SPEED_KMH = 5;
const MAX_WALK_DISTANCE_M = 2000; // Max walking distance to/from station

interface StationWithDistance {
  nodeId: number;
  walkDistanceM: number;
  walkTimeMin: number;
  nodeTypes: string[];
}

/**
 * Find nearby stations (bus_stop or station) within walking distance
 */
function findNearbyStations(
  fromNode: Node,
  nodes: Node[],
  maxDistanceM: number = MAX_WALK_DISTANCE_M,
  scale: number = 100
): StationWithDistance[] {
  const stations: StationWithDistance[] = [];

  for (const node of nodes) {
    const nodeTypes = node.node_type.map((t) => t.name);
    const isStation = nodeTypes.includes("station") || nodeTypes.includes("bus_stop");

    if (!isStation) continue;

    const distance = calculateDistance(fromNode, node, scale);
    if (distance <= maxDistanceM) {
      stations.push({
        nodeId: node.id,
        walkDistanceM: distance,
        walkTimeMin: (distance / 1000 / WALK_SPEED_KMH) * 60,
        nodeTypes,
      });
    }
  }

  // Sort by walking distance
  stations.sort((a, b) => a.walkDistanceM - b.walkDistanceM);

  return stations;
}

/**
 * Find which PT lines serve a given station
 */
function getLinesAtStation(
  stationNodeId: number,
  busLines: PTLine[],
  trainLines: PTLine[]
): { line: PTLine; stopIndex: number }[] {
  const result: { line: PTLine; stopIndex: number }[] = [];

  for (const line of busLines) {
    const stopIndex = line.stops.indexOf(stationNodeId);
    if (stopIndex !== -1) {
      result.push({ line, stopIndex });
    }
  }

  for (const line of trainLines) {
    const stopIndex = line.stops.indexOf(stationNodeId);
    if (stopIndex !== -1) {
      result.push({ line, stopIndex });
    }
  }

  return result;
}

/**
 * Calculate travel time on a PT line between two stops
 */
function calculatePTTravelTime(
  line: PTLine,
  fromStopIndex: number,
  toStopIndex: number,
  nodes: Node[],
  edges: { id: number; start_node: number; end_node: number; distance_m?: number }[],
  scale: number
): { timeMin: number; distanceM: number; edgeIds: number[] } {
  // Build node map
  const nodeMap = new Map<number, Node>();
  for (const node of nodes) {
    nodeMap.set(node.id, node);
  }

  // Build edge map
  const edgeMap = new Map<number, typeof edges[0]>();
  for (const edge of edges) {
    edgeMap.set(edge.id, edge);
  }

  let totalDistance = 0;
  const usedEdgeIds: number[] = [];

  // PT lines travel at approximately 30 km/h average (accounting for stops)
  const ptSpeedKmh = 30;

  // Calculate distance along the line
  const startIdx = Math.min(fromStopIndex, toStopIndex);
  const endIdx = Math.max(fromStopIndex, toStopIndex);

  // Use edges if available, otherwise estimate from stop positions
  if (line.edges.length > 0) {
    // Use actual edge distances
    const relevantEdgeIds = line.edges.slice(startIdx, endIdx);
    for (const edgeId of relevantEdgeIds) {
      const edge = edgeMap.get(edgeId);
      if (edge) {
        if (edge.distance_m) {
          totalDistance += edge.distance_m;
        } else {
          // Calculate from nodes
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
    // Estimate from stop positions
    for (let i = startIdx; i < endIdx; i++) {
      const from = nodeMap.get(line.stops[i]);
      const to = nodeMap.get(line.stops[i + 1]);
      if (from && to) {
        totalDistance += calculateDistance(from, to, scale);
      }
    }
  }

  const timeMin = (totalDistance / 1000 / ptSpeedKmh) * 60;

  return {
    timeMin,
    distanceM: totalDistance,
    edgeIds: usedEdgeIds,
  };
}

/**
 * Find best PT route between two stations using the same line
 */
function findDirectPTRoute(
  fromStation: number,
  toStation: number,
  busLines: PTLine[],
  trainLines: PTLine[],
  nodes: Node[],
  edges: { id: number; start_node: number; end_node: number; distance_m?: number }[],
  scale: number
): {
  line: PTLine;
  fromStopIndex: number;
  toStopIndex: number;
  travelTimeMin: number;
  distanceM: number;
  edgeIds: number[];
} | null {
  const fromLines = getLinesAtStation(fromStation, busLines, trainLines);
  const toLines = getLinesAtStation(toStation, busLines, trainLines);

  let bestRoute: ReturnType<typeof findDirectPTRoute> = null;
  let bestTime = Infinity;

  // Find lines that serve both stations
  for (const { line: fromLine, stopIndex: fromIdx } of fromLines) {
    for (const { line: toLine, stopIndex: toIdx } of toLines) {
      if (fromLine.id === toLine.id && fromLine.type === toLine.type) {
        // Same line serves both stations
        const { timeMin, distanceM, edgeIds } = calculatePTTravelTime(
          fromLine,
          fromIdx,
          toIdx,
          nodes,
          edges,
          scale
        );

        if (timeMin < bestTime) {
          bestTime = timeMin;
          bestRoute = {
            line: fromLine,
            fromStopIndex: fromIdx,
            toStopIndex: toIdx,
            travelTimeMin: timeMin,
            distanceM,
            edgeIds,
          };
        }
      }
    }
  }

  return bestRoute;
}

/**
 * Main public transport routing function
 */
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
  const { scale = 100, onStateChange, animationDelayMs = 0 } = options;

  console.log("[ptRouting] Starting PT route search:", {
    from: startNodeId,
    to: endNodeId,
    scale,
    busLines: graph.bus_lines?.length ?? 0,
    trainLines: graph.train_lines?.length ?? 0,
  });

  // Debug: Log all nodes with station/bus_stop type
  const stationNodes = graph.nodes.filter((n) => {
    const types = n.node_type?.map((t) => t.name) ?? [];
    return types.includes("station") || types.includes("bus_stop");
  });
  console.log("[ptRouting] Station nodes in graph:", stationNodes.length,
    stationNodes.map(n => ({ id: n.id, types: n.node_type?.map(t => t.name) })));

  // Build node map
  const nodeMap = new Map<number, Node>();
  for (const node of graph.nodes) {
    nodeMap.set(node.id, node);
  }

  const startNode = nodeMap.get(startNodeId);
  const endNode = nodeMap.get(endNodeId);

  if (!startNode || !endNode) {
    console.error("[ptRouting] Start or end node not found:", { startNodeId, endNodeId });
    return {
      success: false,
      walkToStation: [],
      ptSegments: [],
      walkFromStation: [],
      totalDistanceM: 0,
      totalTimeMin: 0,
      waitTimeMin: 0,
      error: "Start or end node not found",
    };
  }

  // Find nearby stations from start
  const startStations = findNearbyStations(startNode, graph.nodes, MAX_WALK_DISTANCE_M, scale);
  console.log("[ptRouting] Stations near start:", startStations.length, startStations);

  // Find nearby stations from end
  const endStations = findNearbyStations(endNode, graph.nodes, MAX_WALK_DISTANCE_M, scale);
  console.log("[ptRouting] Stations near end:", endStations.length, endStations);

  if (startStations.length === 0 || endStations.length === 0) {
    console.log("[ptRouting] No stations nearby, falling back to walking");
    // No stations nearby, fall back to walking
    const walkResult = await dijkstra(graph, startNodeId, endNodeId, "walk", {
      scale,
      onStateChange,
      animationDelayMs,
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

    return {
      success: false,
      walkToStation: [],
      ptSegments: [],
      walkFromStation: [],
      totalDistanceM: 0,
      totalTimeMin: 0,
      waitTimeMin: 0,
      error: "No path found",
    };
  }

  const busLines = graph.bus_lines ?? [];
  const trainLines = graph.train_lines ?? [];

  console.log("[ptRouting] Available PT lines:", {
    busLines: busLines.map(l => ({ id: l.id, name: l.name, stops: l.stops })),
    trainLines: trainLines.map(l => ({ id: l.id, name: l.name, stops: l.stops })),
  });

  // Try all combinations of start/end stations
  let bestRoute: PTRoutingResult | null = null;
  let bestTotalTime = Infinity;
  let routesChecked = 0;

  for (const startStation of startStations) {
    for (const endStation of endStations) {
      // Skip if same station
      if (startStation.nodeId === endStation.nodeId) continue;

      routesChecked++;

      // Find direct PT route between stations
      const ptRoute = findDirectPTRoute(
        startStation.nodeId,
        endStation.nodeId,
        busLines,
        trainLines,
        graph.nodes,
        graph.edges,
        scale
      );

      if (!ptRoute) {
        console.log(`[ptRouting] No direct PT route from station ${startStation.nodeId} to ${endStation.nodeId}`);
        continue;
      }

      console.log(`[ptRouting] Found PT route via ${ptRoute.line.name}:`, ptRoute);

      // Calculate wait time (average half the interval)
      const waitTimeMin = ptRoute.line.interval / 2;

      // Total time: walk to station + wait + PT travel + walk from station
      const totalTime =
        startStation.walkTimeMin +
        waitTimeMin +
        ptRoute.travelTimeMin +
        endStation.walkTimeMin;

      if (totalTime < bestTotalTime) {
        bestTotalTime = totalTime;

        // Build walk to station segments
        const walkToResult = await dijkstra(graph, startNodeId, startStation.nodeId, "walk", {
          scale,
        });

        // Build walk from station segments
        const walkFromResult = await dijkstra(graph, endStation.nodeId, endNodeId, "walk", {
          scale,
        });

        // Build PT segments
        const ptSegments: RouteSegment[] = [];
        const mode = ptRoute.line.type;

        // For now, create one segment per edge or one segment for whole trip
        if (ptRoute.edgeIds.length > 0) {
          let prevNode = startStation.nodeId;
          for (let i = 0; i < ptRoute.edgeIds.length; i++) {
            const edgeId = ptRoute.edgeIds[i];
            const edge = graph.edges.find((e) => e.id === edgeId);
            if (edge) {
              const nextNode = edge.start_node === prevNode ? edge.end_node : edge.start_node;
              const startN = nodeMap.get(prevNode);
              const endN = nodeMap.get(nextNode);
              const dist = edge.distance_m ?? (startN && endN ? calculateDistance(startN, endN, scale) : 0);

              ptSegments.push({
                edgeId: edge.id,
                startNode: prevNode,
                endNode: nextNode,
                mode,
                ptLineId: ptRoute.line.id,
                distanceM: dist,
                estimatedTimeMin: (dist / 1000 / 30) * 60, // 30 km/h average
              });
              prevNode = nextNode;
            }
          }
        } else {
          // Create single segment for whole PT trip
          ptSegments.push({
            edgeId: -1, // Placeholder for PT without specific edges
            startNode: startStation.nodeId,
            endNode: endStation.nodeId,
            mode,
            ptLineId: ptRoute.line.id,
            distanceM: ptRoute.distanceM,
            estimatedTimeMin: ptRoute.travelTimeMin,
          });
        }

        const totalDistanceM =
          (walkToResult.success ? walkToResult.totalDistanceM : startStation.walkDistanceM) +
          ptRoute.distanceM +
          (walkFromResult.success ? walkFromResult.totalDistanceM : endStation.walkDistanceM);

        bestRoute = {
          success: true,
          walkToStation: walkToResult.success ? walkToResult.segments : [],
          ptSegments,
          walkFromStation: walkFromResult.success ? walkFromResult.segments : [],
          totalDistanceM,
          totalTimeMin: totalTime,
          waitTimeMin,
        };
      }
    }
  }

  if (bestRoute) {
    console.log("[ptRouting] Best PT route found:", bestRoute);
    return bestRoute;
  }

  console.log(`[ptRouting] No PT route found after checking ${routesChecked} station combinations. Falling back to walking.`);

  // No PT route found, try walking directly
  const walkResult = await dijkstra(graph, startNodeId, endNodeId, "walk", {
    scale,
    onStateChange,
    animationDelayMs,
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

  return {
    success: false,
    walkToStation: [],
    ptSegments: [],
    walkFromStation: [],
    totalDistanceM: 0,
    totalTimeMin: 0,
    waitTimeMin: 0,
    error: "No public transport or walking route found",
  };
}

/**
 * Compare PT route with direct walking and return the better option
 */
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
  // Get PT route
  const ptResult = await findPTRoute(graph, startNodeId, endNodeId, options);

  // Get direct walking route for comparison
  const walkResult = await dijkstra(graph, startNodeId, endNodeId, "walk", {
    scale: options.scale,
  });

  // If PT routing failed or walking is faster, return walking
  if (!ptResult.success || (walkResult.success && walkResult.estimatedTimeMin < ptResult.totalTimeMin)) {
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
