/**
 * One trip, searched the way the round screen searches it — and every
 * commute a map offers, searched that way too.
 *
 * The round screen (`use-round-draft.ts`) and `scripts/routes.mjs` both route
 * through here, so a map is measured with the routes a class would actually
 * be handed. Two copies of "which router, which options" would be two answers
 * to one question, and the calibration would be measuring a game nobody plays.
 */

import { legPayload } from "@/lib/game/round-draft";
import { findPath } from "@/utils/pathfinding";
import { findBestPTRoute } from "@/utils/ptRouting";
import type {
  CarOptimization,
  ExtendedMapGraph,
  PathfindingResult,
  PathfindingState,
  PTOptimization,
  PTRoutingResult,
  RouteLeg,
  RouteSubmissionLeg,
  TransportMode,
} from "@/types/routeTypes";

/**
 * The graph as the pathfinders want it. They read `bus_lines`, `train_lines`
 * and `scale` unconditionally, and a map with no PT lines omits them.
 */
export function withLines(graph: ExtendedMapGraph): ExtendedMapGraph {
  return {
    ...graph,
    bus_lines: graph.bus_lines ?? [],
    train_lines: graph.train_lines ?? [],
    scale: graph.scale ?? 100,
  };
}

/** How a passenger wants to travel, beyond the mode itself. */
export type TripChoice = {
  carOptimization: CarOptimization;
  ptOptimization: PTOptimization;
};

/**
 * One trip from `from` to `to`.
 *
 * Bike and walk go through `findPath` with the car's optimisation, exactly as
 * the screen always sent it. "schnellste" and "klimafreundlichste" read last
 * round's speeds — a jam costs time and, on the simulation's curve, CO2. Only
 * "kürzeste" ignores them: a jam does not change a distance.
 */
export function searchTrip(
  graph: ExtendedMapGraph,
  from: number,
  to: number,
  mode: TransportMode,
  choice: TripChoice,
  onStateChange?: (state: PathfindingState) => void,
): Promise<PathfindingResult | PTRoutingResult> {
  return mode === "public"
    ? findBestPTRoute(graph, from, to, {
        scale: graph.scale,
        ptOptimization: choice.ptOptimization,
      })
    : findPath(graph, from, to, mode, {
        optimization: choice.carOptimization,
        scale: graph.scale,
        trafficData: graph.previous_round_traffic,
        onStateChange,
      });
}

/**
 * The two routers answer in different shapes: the PT one splits the walk to
 * the stop, the ride and the walk off again.
 */
export function toLeg(result: PathfindingResult | PTRoutingResult): RouteLeg {
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

/** A leg as `POST .../move/` takes it, or why there is none. */
export type CommuteLeg = RouteSubmissionLeg | { error: string };

/** One home and one workplace, every mode, both ways. */
export type Commute = {
  home: number;
  workplace: number;
  there: Partial<Record<TransportMode, CommuteLeg>>;
  back: Partial<Record<TransportMode, CommuteLeg>>;
};

export const ALL_MODES: TransportMode[] = ["car", "public", "bike", "walk"];

/** The node types a game hands out (`game/signals.py:assign_agent_nodes`). */
function nodesOfType(graph: ExtendedMapGraph, type: string): number[] {
  return graph.nodes
    .filter((node) => node.node_type.some((t) => t.name === type))
    .map((node) => node.id)
    .sort((a, b) => a - b);
}

/**
 * Every home to every workplace and back, in every mode asked for.
 *
 * Homes and workplaces in id order, homes outer, so the list comes out the
 * same every run. A mode with no route — a walk over the cap, PT where no line
 * goes — is an `{ error }` in its place rather than a missing pair: the
 * caller decides what a class with no way to work does, not this.
 */
export async function routeCommutes(
  graph: ExtendedMapGraph,
  choice: TripChoice,
  modes: TransportMode[] = ALL_MODES,
): Promise<Commute[]> {
  const full = withLines(graph);
  const leg = async (from: number, to: number, mode: TransportMode) => {
    const result = await searchTrip(full, from, to, mode, choice);
    return result.success
      ? legPayload(toLeg(result))
      : { error: result.error ?? "no-route" };
  };

  const commutes: Commute[] = [];
  for (const home of nodesOfType(full, "home")) {
    for (const workplace of nodesOfType(full, "workplace")) {
      const commute: Commute = { home, workplace, there: {}, back: {} };
      for (const mode of modes) {
        commute.there[mode] = await leg(home, workplace, mode);
        commute.back[mode] = await leg(workplace, home, mode);
      }
      commutes.push(commute);
    }
  }
  return commutes;
}
