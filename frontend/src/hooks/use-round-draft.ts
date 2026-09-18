/**
 * The turn, wired up: the pure draft reducer plus the pathfinding it needs.
 *
 * Replaces `useAgentRoutes` in `hooks/usePathfinding.ts`. What it does not
 * replace is the pathfinding itself — `findPath` and `findBestPTRoute` are pure
 * logic and stay exactly as they are (Roadmap.md F3).
 *
 * Parameterised by seat: give it a `seatId` and it plays that seat. F4's desk
 * hands it someone else's, and nothing here has to change.
 */

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";

import {
  draftComplete,
  draftPayload,
  draftProgress,
  draftRouting,
  initialRoundDraft,
  roundDraftReducer,
} from "@/lib/game/round-draft";
import { useMapGraph } from "@/lib/queries/map-graph";
import { useSeatGame } from "@/lib/queries/seat";
import { findPath } from "@/utils/pathfinding";
import { findBestPTRoute } from "@/utils/ptRouting";
import type {
  AgentRoute,
  CarOptimization,
  ExtendedMapGraph,
  PTOptimization,
  PTRoutingResult,
  RouteSegment,
  TransportMode,
} from "@/types/routeTypes";

export function useRoundDraft({
  gameId,
  seatId,
  roundNumber,
}: {
  gameId: string;
  seatId: string | null;
  roundNumber: number;
}) {
  const seat = useSeatGame(gameId, seatId);
  const graph = useMapGraph(seat.data?.game_map, seat.data?.active_map_version);
  const [draft, dispatch] = useReducer(
    roundDraftReducer,
    undefined,
    initialRoundDraft,
  );

  /**
   * One counter per agent. A result only counts while its token is still the
   * current one — otherwise a slow car search lands on top of the bike route
   * that was asked for after it. The old hook had no such guard.
   */
  const runs = useRef(new Map<number, number>());

  const assignments = seat.data?.agent_assignments ?? null;

  useEffect(() => {
    if (!seatId || !assignments?.agents?.length) return;
    dispatch({
      kind: "assign",
      seatId,
      roundNumber,
      homeNode: assignments.home_node,
      agents: assignments.agents,
    });
  }, [seatId, roundNumber, assignments]);

  // The graph as the pathfinders want it. They read `bus_lines`, `train_lines`
  // and `scale` unconditionally, and a map with no PT lines omits them.
  const extended = useMemo<ExtendedMapGraph | null>(() => {
    if (!graph.data) return null;
    return {
      ...graph.data,
      bus_lines: graph.data.bus_lines ?? [],
      train_lines: graph.data.train_lines ?? [],
      scale: graph.data.scale ?? 100,
    };
  }, [graph.data]);

  const findRoute = useCallback(
    async (agentId: number) => {
      const agent = draft.agents.find((a) => a.agentId === agentId);
      const home = draft.homeNode;
      if (!agent || !agent.mode || home === null || !extended) return;

      const token = (runs.current.get(agentId) ?? 0) + 1;
      runs.current.set(agentId, token);
      dispatch({ kind: "routing", agentId });

      try {
        const result =
          agent.mode === "public"
            ? await findBestPTRoute(extended, home, agent.destinationNode, {
                scale: extended.scale,
                ptOptimization: agent.ptOptimization,
              })
            : await findPath(extended, home, agent.destinationNode, agent.mode, {
                optimization: agent.carOptimization,
                scale: extended.scale,
              });

        if (runs.current.get(agentId) !== token) return;

        if (!result.success) {
          dispatch({ kind: "route-failed", agentId, error: result.error ?? "no-route" });
          return;
        }

        // The two routers answer in different shapes: the PT one splits the
        // walk to the stop, the ride and the walk off again.
        let segments: RouteSegment[];
        let totalDistanceM: number;
        let estimatedTimeMin: number;

        if ("ptSegments" in result) {
          const pt = result as PTRoutingResult;
          segments = [...pt.walkToStation, ...pt.ptSegments, ...pt.walkFromStation];
          totalDistanceM = pt.totalDistanceM;
          estimatedTimeMin = pt.totalTimeMin;
        } else {
          segments = result.segments;
          totalDistanceM = result.totalDistanceM;
          estimatedTimeMin = result.estimatedTimeMin;
        }

        const route: AgentRoute = {
          agentId,
          transportMode: agent.mode,
          optimization: agent.mode === "car" ? agent.carOptimization : undefined,
          totalDistanceM,
          estimatedTimeMin,
          segments,
        };
        dispatch({ kind: "routed", agentId, route });
      } catch (error) {
        if (runs.current.get(agentId) !== token) return;
        dispatch({
          kind: "route-failed",
          agentId,
          error: error instanceof Error ? error.message : "unknown",
        });
      }
    },
    [draft.agents, draft.homeNode, extended],
  );

  /**
   * Anyone with a mode but no route gets one.
   *
   * An effect rather than a `setTimeout` in the click handler, which is what
   * the old screen did: the handler does not see the state it just dispatched,
   * so it guessed with a 100 ms delay. The effect runs on the new state.
   */
  useEffect(() => {
    const next = draft.agents.find((a) => a.mode && a.status === "empty");
    if (next) void findRoute(next.agentId);
  }, [draft.agents, findRoute]);

  const pickMode = useCallback((agentId: number, mode: TransportMode) => {
    dispatch({ kind: "mode", agentId, mode });
  }, []);

  const pickCarOptimization = useCallback(
    (agentId: number, optimization: CarOptimization) => {
      dispatch({ kind: "car-optimization", agentId, optimization });
    },
    [],
  );

  const pickPtOptimization = useCallback(
    (agentId: number, optimization: PTOptimization) => {
      dispatch({ kind: "pt-optimization", agentId, optimization });
    },
    [],
  );

  const clearAgent = useCallback((agentId: number) => {
    dispatch({ kind: "clear", agentId });
  }, []);

  return {
    draft,
    graph: extended,
    /** The assignment or the map is still in flight; the turn cannot be drawn yet. */
    isLoading: seat.isLoading || graph.isLoading,
    error: seat.error ?? graph.error ?? null,
    /** The seat exists but was never dealt agents — a broken game, not an empty turn. */
    hasAssignment: !!assignments?.agents?.length,
    pickMode,
    pickCarOptimization,
    pickPtOptimization,
    clearAgent,
    retry: findRoute,
    complete: draftComplete(draft),
    routing: draftRouting(draft),
    progress: draftProgress(draft),
    payload: draftPayload(draft),
  };
}
