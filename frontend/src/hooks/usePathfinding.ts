/**
 * Pathfinding hook with animation support
 */

import { useState, useCallback, useRef, useEffect } from "react";
import type { MapGraph } from "../types/mapTypes";
import type {
  TransportMode,
  CarOptimization,
  PathfindingState,
  PathfindingResult,
  PTRoutingResult,
  AgentRoute,
  RouteSegment,
  EdgeTrafficData,
  ExtendedMapGraph,
} from "../types/routeTypes";
import { findPath } from "../utils/pathfinding";
import { findBestPTRoute } from "../utils/ptRouting";

interface UsePathfindingOptions {
  animationSpeed?: number; // ms per step, 0 = instant
  scale?: number;
  enableAnimation?: boolean; // whether to animate Dijkstra (default false)
}

interface UsePathfindingResult {
  // State
  isPathfinding: boolean;
  pathfindingState: PathfindingState | null;
  result: PathfindingResult | PTRoutingResult | null;
  error: string | null;

  // Actions
  findRoute: (
    graph: MapGraph | ExtendedMapGraph,
    startNode: number,
    endNode: number,
    mode: TransportMode,
    optimization?: CarOptimization,
    trafficData?: EdgeTrafficData[]
  ) => Promise<AgentRoute | null>;
  cancelPathfinding: () => void;
  reset: () => void;
}

const initialPathfindingState: PathfindingState = {
  isRunning: false,
  visitedNodes: new Set(),
  currentNode: null,
  tentativeDistances: new Map(),
  previousNodes: new Map(),
  finalPath: null,
  isComplete: false,
  exploredEdges: new Set(),
  relaxedEdge: null,
  previousEdges: new Map(),
};

export function usePathfinding(
  options: UsePathfindingOptions = {}
): UsePathfindingResult {
  const { animationSpeed = 50, scale = 100 } = options;

  const [isPathfinding, setIsPathfinding] = useState(false);
  const [pathfindingState, setPathfindingState] = useState<PathfindingState | null>(null);
  const [result, setResult] = useState<PathfindingResult | PTRoutingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cancelledRef = useRef(false);

  const reset = useCallback(() => {
    setIsPathfinding(false);
    setPathfindingState(null);
    setResult(null);
    setError(null);
    cancelledRef.current = false;
  }, []);

  const cancelPathfinding = useCallback(() => {
    cancelledRef.current = true;
    setIsPathfinding(false);
  }, []);

  const findRoute = useCallback(
    async (
      graph: MapGraph | ExtendedMapGraph,
      startNode: number,
      endNode: number,
      mode: TransportMode,
      optimization?: CarOptimization,
      trafficData?: EdgeTrafficData[]
    ): Promise<AgentRoute | null> => {
      // Reset state
      reset();
      cancelledRef.current = false;
      setIsPathfinding(true);
      setPathfindingState({ ...initialPathfindingState, isRunning: true });

      try {
        let pathResult: PathfindingResult | PTRoutingResult;

        if (mode === "public") {
          // Use PT routing for public transport
          const extendedGraph = graph as ExtendedMapGraph;
          pathResult = await findBestPTRoute(extendedGraph, startNode, endNode, {
            scale,
            animationDelayMs: animationSpeed,
            onStateChange: (state) => {
              if (!cancelledRef.current) {
                setPathfindingState(state);
              }
            },
          });
        } else {
          // Use standard Dijkstra for other modes
          pathResult = await findPath(graph, startNode, endNode, mode, {
            optimization,
            trafficData,
            scale,
            animationDelayMs: animationSpeed,
            onStateChange: (state) => {
              if (!cancelledRef.current) {
                setPathfindingState(state);
              }
            },
          });
        }

        if (cancelledRef.current) {
          return null;
        }

        setResult(pathResult);
        setIsPathfinding(false);

        if (!pathResult.success) {
          setError(pathResult.error || "Pathfinding failed");
          return null;
        }

        // Convert result to AgentRoute format
        let segments: RouteSegment[];
        let totalDistanceM: number;
        let estimatedTimeMin: number;

        if ("ptSegments" in pathResult) {
          // PT routing result
          const ptResult = pathResult as PTRoutingResult;
          segments = [
            ...ptResult.walkToStation,
            ...ptResult.ptSegments,
            ...ptResult.walkFromStation,
          ];
          totalDistanceM = ptResult.totalDistanceM;
          estimatedTimeMin = ptResult.totalTimeMin;
        } else {
          // Standard pathfinding result
          segments = pathResult.segments;
          totalDistanceM = pathResult.totalDistanceM;
          estimatedTimeMin = pathResult.estimatedTimeMin;
        }

        const agentRoute: AgentRoute = {
          agentId: 0, // Will be set by caller
          transportMode: mode,
          optimization,
          totalDistanceM,
          estimatedTimeMin,
          segments,
        };

        return agentRoute;
      } catch (err) {
        if (!cancelledRef.current) {
          const errorMessage = err instanceof Error ? err.message : "Unknown error";
          setError(errorMessage);
          setIsPathfinding(false);
        }
        return null;
      }
    },
    [animationSpeed, scale, reset]
  );

  return {
    isPathfinding,
    pathfindingState,
    result,
    error,
    findRoute,
    cancelPathfinding,
    reset,
  };
}

/**
 * Hook for managing multiple agent routes
 */
interface AgentRouteState {
  agentId: number;
  destinationNode: number;
  selectedMode: TransportMode | null;
  selectedOptimization?: CarOptimization;
  route: AgentRoute | null;
  isPathfinding: boolean;
  error: string | null;
  pathfindingState: PathfindingState | null;
}

interface UseAgentRoutesResult {
  agents: AgentRouteState[];
  setAgentMode: (
    agentId: number,
    mode: TransportMode,
    optimization?: CarOptimization
  ) => void;
  findAgentRoute: (
    agentId: number,
    graph: MapGraph | ExtendedMapGraph,
    homeNode: number,
    trafficData?: EdgeTrafficData[]
  ) => Promise<void>;
  clearAgentRoute: (agentId: number) => void;
  allRoutesComplete: boolean;
  getSubmissionPayload: () => import("../types/routeTypes").RouteSubmissionPayload | null;
  activePathfindingState: PathfindingState | null;
  animatingAgentId: number | null;
}

export function useAgentRoutes(
  agentAssignments: { id: number; destination_node: number }[],
  options: UsePathfindingOptions = {}
): UseAgentRoutesResult {
  const { scale = 100, enableAnimation = false, animationSpeed = 100 } = options;

  const [agents, setAgents] = useState<AgentRouteState[]>([]);

  // Keep a ref to the latest agents to avoid stale closure issues
  const agentsRef = useRef<AgentRouteState[]>(agents);
  useEffect(() => {
    agentsRef.current = agents;
  }, [agents]);

  // Update agents when assignments change (e.g., from async fetch)
  useEffect(() => {
    console.log("[useAgentRoutes] agentAssignments changed:", agentAssignments);
    if (agentAssignments.length > 0) {
      setAgents((prev) => {
        // Only update if assignments actually changed
        const prevIds = prev.map((a) => a.agentId).join(",");
        const newIds = agentAssignments.map((a) => a.id).join(",");
        if (prevIds === newIds) {
          console.log("[useAgentRoutes] Assignments unchanged, keeping previous state");
          return prev;
        }

        console.log("[useAgentRoutes] Initializing agents:", agentAssignments.length);
        return agentAssignments.map((a) => ({
          agentId: a.id,
          destinationNode: a.destination_node,
          selectedMode: null,
          selectedOptimization: undefined,
          route: null,
          isPathfinding: false,
          error: null,
          pathfindingState: null,
        }));
      });
    }
  }, [agentAssignments]);

  const setAgentMode = useCallback(
    (agentId: number, mode: TransportMode, optimization?: CarOptimization) => {
      console.log(`[useAgentRoutes] Setting mode for agent ${agentId}:`, mode, optimization);
      setAgents((prev) =>
        prev.map((a) =>
          a.agentId === agentId
            ? {
                ...a,
                selectedMode: mode,
                selectedOptimization: optimization,
                route: null, // Clear route when mode changes
                error: null,
                pathfindingState: null,
              }
            : a
        )
      );
    },
    []
  );

  const findAgentRoute = useCallback(
    async (
      agentId: number,
      graph: MapGraph | ExtendedMapGraph,
      homeNode: number,
      trafficData?: EdgeTrafficData[]
    ) => {
      // Use ref to get latest agents state (avoids stale closure)
      const currentAgents = agentsRef.current;
      const agent = currentAgents.find((a) => a.agentId === agentId);
      console.log(`[useAgentRoutes] findAgentRoute called for agent ${agentId}`, {
        agent,
        homeNode,
        destination: agent?.destinationNode,
        mode: agent?.selectedMode,
        graphNodes: graph.nodes.length,
        graphEdges: graph.edges.length,
        allAgents: currentAgents.map(a => ({ id: a.agentId, mode: a.selectedMode })),
      });

      if (!agent || !agent.selectedMode) {
        console.warn(`[useAgentRoutes] Agent ${agentId} not found or no mode selected`);
        return;
      }

      setAgents((prev) =>
        prev.map((a) =>
          a.agentId === agentId ? { ...a, isPathfinding: true, error: null, pathfindingState: null } : a
        )
      );

      try {
        let result: PathfindingResult | PTRoutingResult;

        console.log(`[useAgentRoutes] Starting pathfinding for agent ${agentId}`, {
          mode: agent.selectedMode,
          from: homeNode,
          to: agent.destinationNode,
          animated: enableAnimation,
        });

        // Build animation options when enabled
        const animOpts = enableAnimation ? {
          animationDelayMs: animationSpeed,
          onStateChange: (state: PathfindingState) => {
            setAgents((prev) =>
              prev.map((a) =>
                a.agentId === agentId ? { ...a, pathfindingState: state } : a
              )
            );
          },
        } : {};

        if (agent.selectedMode === "public") {
          const extendedGraph = graph as ExtendedMapGraph;
          result = await findBestPTRoute(extendedGraph, homeNode, agent.destinationNode, {
            scale,
            ...animOpts,
          });
        } else {
          result = await findPath(graph, homeNode, agent.destinationNode, agent.selectedMode, {
            optimization: agent.selectedOptimization,
            trafficData,
            scale,
            ...animOpts,
          });
        }

        console.log(`[useAgentRoutes] Pathfinding result for agent ${agentId}:`, result);

        if (!result.success) {
          console.error(`[useAgentRoutes] Pathfinding failed for agent ${agentId}:`, result.error);
          setAgents((prev) =>
            prev.map((a) =>
              a.agentId === agentId
                ? { ...a, isPathfinding: false, error: result.error || "No route found", pathfindingState: null }
                : a
            )
          );
          return;
        }

        // Build AgentRoute
        let segments: RouteSegment[];
        let totalDistanceM: number;
        let estimatedTimeMin: number;

        if ("ptSegments" in result) {
          const ptResult = result as PTRoutingResult;
          segments = [
            ...ptResult.walkToStation,
            ...ptResult.ptSegments,
            ...ptResult.walkFromStation,
          ];
          totalDistanceM = ptResult.totalDistanceM;
          estimatedTimeMin = ptResult.totalTimeMin;
        } else {
          segments = result.segments;
          totalDistanceM = result.totalDistanceM;
          estimatedTimeMin = result.estimatedTimeMin;
        }

        const route: AgentRoute = {
          agentId,
          transportMode: agent.selectedMode,
          optimization: agent.selectedOptimization,
          totalDistanceM,
          estimatedTimeMin,
          segments,
        };

        console.log(`[useAgentRoutes] Created route for agent ${agentId}:`, {
          segments: route.segments.length,
          distance: route.totalDistanceM,
          time: route.estimatedTimeMin,
          firstSegment: route.segments[0],
          lastSegment: route.segments[route.segments.length - 1],
        });

        setAgents((prev) =>
          prev.map((a) =>
            a.agentId === agentId ? { ...a, isPathfinding: false, route, error: null, pathfindingState: null } : a
          )
        );
      } catch (err) {
        console.error(`[useAgentRoutes] Exception in findAgentRoute for agent ${agentId}:`, err);
        const errorMessage = err instanceof Error ? err.message : "Unknown error";
        setAgents((prev) =>
          prev.map((a) =>
            a.agentId === agentId ? { ...a, isPathfinding: false, error: errorMessage, pathfindingState: null } : a
          )
        );
      }
    },
    [scale, enableAnimation, animationSpeed] // Using agentsRef to avoid stale closure
  );

  const clearAgentRoute = useCallback((agentId: number) => {
    setAgents((prev) =>
      prev.map((a) =>
        a.agentId === agentId
          ? { ...a, route: null, selectedMode: null, selectedOptimization: undefined, error: null, pathfindingState: null }
          : a
      )
    );
  }, []);

  const allRoutesComplete = agents.every((a) => a.route !== null);

  // Find the currently animating agent's pathfinding state
  const animatingAgent = agents.find((a) => a.isPathfinding && a.pathfindingState);
  const activePathfindingState = animatingAgent?.pathfindingState ?? null;
  const animatingAgentId = animatingAgent?.agentId ?? null;

  const getSubmissionPayload = useCallback(() => {
    if (!allRoutesComplete) return null;

    return {
      agents: agents.map((a) => ({
        id: a.agentId,
        transport_mode: a.selectedMode!,
        optimization: a.selectedOptimization,
        route: {
          total_distance_m: a.route!.totalDistanceM,
          estimated_time_min: a.route!.estimatedTimeMin,
          segments: a.route!.segments.map((s) => ({
            edge_id: s.edgeId,
            start_node: s.startNode,
            end_node: s.endNode,
            mode: s.mode,
            pt_line_id: s.ptLineId,
          })),
        },
      })),
    };
  }, [agents, allRoutesComplete]);

  return {
    agents,
    setAgentMode,
    findAgentRoute,
    clearAgentRoute,
    allRoutesComplete,
    getSubmissionPayload,
    activePathfindingState,
    animatingAgentId,
  };
}
