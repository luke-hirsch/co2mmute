/**
 * What a seat intends to do this round — up until it is submitted.
 *
 * Pure: no React, no fetch, no pathfinding. `use-round-draft.ts` hangs the side
 * effects off it; this file only records which passenger travels how, and what
 * route came out of it.
 *
 * What deliberately is **not** here: whether the turn was submitted. The roster
 * says that (`seat.status === "waiting"`, `game/roster.py:build`), and it keeps
 * saying it after a reload, after a reconnect, and when another device
 * submitted the seat (F4). A local `isSubmitted` would be the second source of
 * truth that Roadmap.md 2.2 exists to remove.
 *
 * The draft itself does not survive a reload, and that is the deliberate other
 * half of the same rule: half-made choices live here and nowhere else. Mirroring
 * them into storage would put routes in two places, which is the pattern the old
 * screens died of. Re-picking costs four taps; *that* it was submitted is a fact
 * the server owns and hands back.
 */

import type {
  AgentRoute,
  CarOptimization,
  PTOptimization,
  RouteSubmissionPayload,
  TransportMode,
} from "@/types/routeTypes";

export type AgentDraftStatus = "empty" | "routing" | "ready" | "failed";

export type AgentDraft = {
  agentId: number;
  destinationNode: number;
  mode: TransportMode | null;
  /**
   * Only meaningful for `car`, but kept across a mode switch: going car → PT →
   * car should not forget that this passenger drives the greenest way.
   */
  carOptimization: CarOptimization;
  /** The same, for `public`. */
  ptOptimization: PTOptimization;
  status: AgentDraftStatus;
  route: AgentRoute | null;
  error: string | null;
};

export type RoundDraft = {
  /** Whose turn this is. F4 plays other people's seats through the same screen. */
  seatId: string | null;
  /** Which round. A new round drops the choices, not the assignment. */
  roundNumber: number;
  homeNode: number | null;
  agents: AgentDraft[];
};

export type RoundDraftAction =
  | {
      kind: "assign";
      seatId: string;
      roundNumber: number;
      homeNode: number;
      agents: { id: number; destination_node: number }[];
    }
  | { kind: "mode"; agentId: number; mode: TransportMode }
  | { kind: "car-optimization"; agentId: number; optimization: CarOptimization }
  | { kind: "pt-optimization"; agentId: number; optimization: PTOptimization }
  | { kind: "routing"; agentId: number }
  | { kind: "routed"; agentId: number; route: AgentRoute }
  | { kind: "route-failed"; agentId: number; error: string }
  | { kind: "clear"; agentId: number };

export const DEFAULT_CAR_OPTIMIZATION: CarOptimization = "time";
export const DEFAULT_PT_OPTIMIZATION: PTOptimization = "fastest";

export function initialRoundDraft(): RoundDraft {
  return { seatId: null, roundNumber: 0, homeNode: null, agents: [] };
}

function freshAgent(agentId: number, destinationNode: number): AgentDraft {
  return {
    agentId,
    destinationNode,
    mode: null,
    carOptimization: DEFAULT_CAR_OPTIMIZATION,
    ptOptimization: DEFAULT_PT_OPTIMIZATION,
    status: "empty",
    route: null,
    error: null,
  };
}

/** Change one agent, leave the rest — and the draft itself — identical. */
function mapAgent(
  draft: RoundDraft,
  agentId: number,
  change: (agent: AgentDraft) => AgentDraft,
): RoundDraft {
  let touched = false;
  const agents = draft.agents.map((agent) => {
    if (agent.agentId !== agentId) return agent;
    touched = true;
    return change(agent);
  });
  return touched ? { ...draft, agents } : draft;
}

export function roundDraftReducer(
  draft: RoundDraft,
  action: RoundDraftAction,
): RoundDraft {
  switch (action.kind) {
    /**
     * The assignment from `GET api/game/<id>/<player_id>/`.
     *
     * Idempotent, and that is the point: React Query hands back the same
     * assignment on every remount, and the old hook nearly wiped a half-made
     * turn each time — it worked around that by comparing joined agent ids at
     * the call site. Here the rule is the reducer's: same seat, same round,
     * same agents means nothing happens. A different seat or round starts over.
     */
    case "assign": {
      const sameShape =
        draft.seatId === action.seatId &&
        draft.roundNumber === action.roundNumber &&
        draft.homeNode === action.homeNode &&
        draft.agents.length === action.agents.length &&
        draft.agents.every(
          (agent, i) =>
            agent.agentId === action.agents[i].id &&
            agent.destinationNode === action.agents[i].destination_node,
        );
      if (sameShape) return draft;

      return {
        seatId: action.seatId,
        roundNumber: action.roundNumber,
        homeNode: action.homeNode,
        agents: action.agents.map((a) => freshAgent(a.id, a.destination_node)),
      };
    }

    // A different mode means a different route. Drop the old one rather than
    // leave it standing until the new one arrives, or the screen shows a car
    // route under a bicycle for as long as the search takes.
    case "mode":
      return mapAgent(draft, action.agentId, (agent) => ({
        ...agent,
        mode: action.mode,
        status: "empty",
        route: null,
        error: null,
      }));

    case "car-optimization":
      return mapAgent(draft, action.agentId, (agent) => ({
        ...agent,
        carOptimization: action.optimization,
        status: "empty",
        route: null,
        error: null,
      }));

    case "pt-optimization":
      return mapAgent(draft, action.agentId, (agent) => ({
        ...agent,
        ptOptimization: action.optimization,
        status: "empty",
        route: null,
        error: null,
      }));

    case "routing":
      return mapAgent(draft, action.agentId, (agent) => ({
        ...agent,
        status: "routing",
        error: null,
      }));

    case "routed":
      return mapAgent(draft, action.agentId, (agent) => ({
        ...agent,
        status: "ready",
        route: action.route,
        error: null,
      }));

    case "route-failed":
      return mapAgent(draft, action.agentId, (agent) => ({
        ...agent,
        status: "failed",
        route: null,
        error: action.error,
      }));

    case "clear":
      return mapAgent(draft, action.agentId, (agent) =>
        freshAgent(agent.agentId, agent.destinationNode),
      );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Selectors
// ─────────────────────────────────────────────────────────────────────────────

/** Submitting needs every passenger routed. An empty draft is not "done". */
export function draftComplete(draft: RoundDraft): boolean {
  return draft.agents.length > 0 && draft.agents.every((a) => a.status === "ready");
}

export function draftProgress(draft: RoundDraft): { done: number; total: number } {
  return {
    done: draft.agents.filter((a) => a.status === "ready").length,
    total: draft.agents.length,
  };
}

export function draftRouting(draft: RoundDraft): boolean {
  return draft.agents.some((a) => a.status === "routing");
}

/**
 * What `POST .../move/` wants as its `payload` — snake_case, because this end
 * is a DRF serializer (`PlayerMoveWithRoutesInputSerializer`) and not the
 * hand-built camelCase of `game.state`.
 *
 * Null until everything is ready: better to keep the button disabled than to
 * send a subset the backend answers with a 400.
 */
export function draftPayload(draft: RoundDraft): RouteSubmissionPayload | null {
  if (!draftComplete(draft)) return null;

  return {
    agents: draft.agents.map((agent) => ({
      id: agent.agentId,
      transport_mode: agent.mode as TransportMode,
      // `optimization` is a ChoiceField over the car's options. Sending the PT
      // one — or one for a bike — is a 400.
      optimization: agent.mode === "car" ? agent.carOptimization : undefined,
      route: {
        total_distance_m: agent.route!.totalDistanceM,
        estimated_time_min: agent.route!.estimatedTimeMin,
        segments: agent.route!.segments.map((segment) => ({
          edge_id: segment.edgeId,
          start_node: segment.startNode,
          end_node: segment.endNode,
          mode: segment.mode,
          pt_line_id: segment.ptLineId,
        })),
      },
    })),
  };
}

/** How many times this route changes vehicle — what a rider actually feels. */
export function transferCount(route: AgentRoute): number {
  const legs = route.segments
    .filter((segment) => segment.mode === "bus" || segment.mode === "train")
    .map((segment) => segment.ptLineId ?? -1);

  let changes = 0;
  for (let i = 1; i < legs.length; i += 1) {
    if (legs[i] !== legs[i - 1]) changes += 1;
  }
  return changes;
}
