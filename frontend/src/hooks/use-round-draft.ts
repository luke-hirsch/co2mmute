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
  browserStorage,
  clearStoredDraft,
  pruneOtherGames,
  readStoredChoices,
  writeStoredChoices,
} from "@/lib/game/draft-storage";
import {
  draftChoices,
  draftComplete,
  draftPayload,
  draftProgress,
  draftRouting,
  initialRoundDraft,
  roundDraftReducer,
} from "@/lib/game/round-draft";
import { createTraceRecorder, type SearchTrace } from "@/lib/map/search-trace";
import { airDistanceM, exceedsModeLimit } from "@/lib/map/trip-limits";
import { useMapGraph } from "@/lib/queries/map-graph";
import { useSeatGame } from "@/lib/queries/seat";
import { findPath, NO_WAY_HOME } from "@/utils/pathfinding";
import { findBestPTRoute } from "@/utils/ptRouting";
import type {
  AgentRoute,
  CarOptimization,
  ExtendedMapGraph,
  PathfindingResult,
  PTOptimization,
  PTRoutingResult,
  RouteLeg,
  TransportMode,
} from "@/types/routeTypes";

/** What the straight line says about one passenger, before a mode is picked. */
export type AgentDistance = {
  agentId: number;
  /** Home → destination as the crow flies, in metres. */
  airM: number;
  /** Modes the straight line already rules out. A lower bound, so it is sound. */
  tooFar: TransportMode[];
};

/**
 * The two routers answer in different shapes: the PT one splits the walk to the
 * stop, the ride and the walk off again.
 */
function toLeg(result: PathfindingResult | PTRoutingResult): RouteLeg {
  if ("ptSegments" in result) {
    return {
      segments: [...result.walkToStation, ...result.ptSegments, ...result.walkFromStation],
      totalDistanceM: result.totalDistanceM,
      estimatedTimeMin: result.totalTimeMin,
    };
  }
  return {
    segments: result.segments,
    totalDistanceM: result.totalDistanceM,
    estimatedTimeMin: result.estimatedTimeMin,
  };
}

export function useRoundDraft({
  gameId,
  seatId,
  roundNumber,
  mapVersionId,
  submitted,
}: {
  gameId: string;
  seatId: string | null;
  roundNumber: number;
  /**
   * The version the game is on *now*, from the reducer (F5).
   *
   * Not `seat.data.active_map_version`: that row is read once and kept
   * (`staleTime: Infinity`), and this screen does not remount between rounds —
   * so after a vote it would still name the map the game started on and round 2
   * would be routed on round 1's graph. The socket knows better at every moment
   * the version can change, so it wins; the row is only the fallback for the
   * first render, before `game.state` has arrived.
   */
  mapVersionId: number | null;
  /**
   * Whether this seat's turn is already in (S7).
   *
   * From the roster, which is the only thing that knows it — the same fact the
   * screen switches on. It is here so the stored draft *follows* that answer
   * rather than being cleared by a side effect of the mutation: a turn that is
   * in has no unfinished draft to keep, and nothing can write one back.
   */
  submitted: boolean;
}) {
  const seat = useSeatGame(gameId, seatId);
  const graph = useMapGraph(
    seat.data?.game_map,
    mapVersionId ?? seat.data?.active_map_version,
    // Last round's observed speeds ride along with the graph, so "schnellste"
    // is computed on a network that has already been driven. The round is in
    // the key, not the URL — see `map-graph.ts`.
    { gameId, roundNumber },
  );
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

  /** Null in private mode or with site data blocked; every call below takes it. */
  const storage = useMemo(() => browserStorage(), []);

  /**
   * Shed other games' unfinished turns on the way into this one — the retention
   * rule from `draft-storage.ts`. Once per game, not on every keystroke of the
   * turn: it walks the whole of localStorage.
   */
  useEffect(() => {
    pruneOtherGames(storage, gameId);
  }, [storage, gameId]);

  useEffect(() => {
    if (!seatId || !assignments?.agents?.length) return;
    dispatch({
      kind: "assign",
      seatId,
      roundNumber,
      homeNode: assignments.home_node,
      agents: assignments.agents,
      // Read on every delivery rather than once: the reducer is what decides
      // whether a restore may happen, and it only lets one through when it
      // actually builds the agents. Doing the guard here as well would be a
      // second answer to one question.
      choices:
        readStoredChoices(storage, gameId, seatId, roundNumber) ?? undefined,
    });
  }, [seatId, roundNumber, assignments, storage, gameId]);

  /**
   * Keep the taps, so a locked phone does not cost the turn (S7).
   *
   * Runs again on every status change too, which rewrites the same few hundred
   * bytes a dozen times a turn. Deliberately not de-duplicated: the write is
   * cheap and a "has it really changed" cache would be state about state.
   */
  const choices = useMemo(() => draftChoices(draft), [draft]);

  useEffect(() => {
    if (!draft.seatId) return;
    if (submitted) {
      clearStoredDraft(storage, gameId, draft.seatId);
      return;
    }
    // `roundNumber` is the screen's, `draft.roundNumber` the draft's; they
    // disagree for a moment on every reload and every new round, and the write
    // refuses while they do. See `writeStoredChoices`.
    writeStoredChoices(storage, gameId, draft, choices, roundNumber);
  }, [storage, gameId, draft, choices, submitted, roundNumber]);

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

  /**
   * How far each passenger is going, before anything is chosen.
   *
   * The straight line is what real life hands you: you know roughly how far the
   * place is and nothing about the route. Until now the distance only appeared
   * *after* a mode had been picked and a route found, so the one number that
   * should inform the choice arrived as a consequence of it.
   *
   * It also gates the picker. The straight line is a lower bound on any route,
   * so a mode it already rules out could never have worked — the gate is sound,
   * and the routed distance in `findPath` catches the rest. On Berlin Mitte-West
   * that is 14 of the 33 walks the cap refuses; the other 19 only fail once the
   * detour is known, because the detour factor runs as high as 2.76.
   */
  const distances = useMemo(() => {
    const byAgent = new Map<number, AgentDistance>();
    if (!extended || draft.homeNode === null) return byAgent;

    const nodes = new Map(extended.nodes.map((node) => [node.id, node]));
    const home = nodes.get(draft.homeNode);
    if (!home) return byAgent;

    for (const agent of draft.agents) {
      const destination = nodes.get(agent.destinationNode);
      if (!destination) continue;
      const airM = airDistanceM(home, destination, extended.scale);
      byAgent.set(agent.agentId, {
        agentId: agent.agentId,
        airM,
        tooFar: (["walk", "bike"] as TransportMode[]).filter((mode) =>
          exceedsModeLimit(mode, airM),
        ),
      });
    }
    return byAgent;
  }, [draft.agents, draft.homeNode, extended]);

  /**
   * What the last search looked at, for the map to play back (S24). Only the
   * latest: it is a flourish on the route that was just found, not state the
   * turn depends on, so it is neither stored nor sent. Public transport has none
   * — its router is a search over lines and stops, not over links.
   */
  const [trace, setTrace] = useReducer(
    (_: SearchTrace | null, next: SearchTrace | null) => next,
    null,
  );

  const findRoute = useCallback(
    async (agentId: number) => {
      const agent = draft.agents.find((a) => a.agentId === agentId);
      const home = draft.homeNode;
      if (!agent || !agent.mode || home === null || !extended) return;

      const token = (runs.current.get(agentId) ?? 0) + 1;
      runs.current.set(agentId, token);
      dispatch({ kind: "routing", agentId });

      try {
        const recorder = createTraceRecorder(agentId);
        const mode = agent.mode;

        // The same router, mode and optimisation both ways. The way home is a
        // search of its own on the directed graph, never the way there turned
        // round: a one-way street has no reverse edge, so on such a map the
        // trip is a circle. Only the way there is traced — it is the flourish
        // on the route the player just asked for.
        const search = (from: number, to: number, trace: boolean) =>
          mode === "public"
            ? findBestPTRoute(extended, from, to, {
                scale: extended.scale,
                ptOptimization: agent.ptOptimization,
              })
            : findPath(extended, from, to, mode, {
                optimization: agent.carOptimization,
                scale: extended.scale,
                // "schnellste" and "klimafreundlichste" read it — a jam costs
                // time and, on the simulation's curve, CO2. Only "kürzeste"
                // ignores it: a jam does not change a distance.
                trafficData: extended.previous_round_traffic,
                onStateChange: trace ? recorder.onStateChange : undefined,
              });

        const there = await search(home, agent.destinationNode, true);
        if (runs.current.get(agentId) !== token) return;
        if (!there.success) {
          dispatch({ kind: "route-failed", agentId, error: there.error ?? "no-route" });
          return;
        }

        const back = await search(agent.destinationNode, home, false);
        if (runs.current.get(agentId) !== token) return;
        if (!back.success) {
          // They can get there and cannot get back: say that, not "no route".
          dispatch({ kind: "route-failed", agentId, error: NO_WAY_HOME });
          return;
        }

        const route: AgentRoute = {
          agentId,
          transportMode: mode,
          optimization: mode === "car" ? agent.carOptimization : undefined,
          ...toLeg(there),
          wayHome: toLeg(back),
        };
        dispatch({ kind: "routed", agentId, route });
        setTrace(mode === "public" ? null : recorder.trace());
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
    trace,
    /** Straight-line distance per passenger, and what it already rules out. */
    distances,
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
