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
 * The draft *does* survive a reload since S7, and the rule above is what shapes
 * how. A locked phone discarding the page is the ordinary case in a classroom,
 * so the taps come back — but only the taps. **A route is never stored.**
 * Mirroring routes into storage is what would put them in two places, which is
 * the pattern the old screens died of, and a stored route can outlive the graph
 * it was found on. So `draft-storage.ts` keeps `AgentChoice` per agent, the
 * `assign` action puts it back with `status: "empty"`, and the pathfinder
 * searches again against the map the game is on now. Re-picking still costs the
 * four taps it always did; they just come back on their own.
 *
 * Still not here, and for the original reason: *that* it was submitted. The
 * roster says that, after a reload, after a reconnect, and when another device
 * submitted the seat.
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

/**
 * What survives a reload: one agent's taps, and nothing computed from them.
 *
 * Both optimisations travel even though only one is live, for the same reason
 * `AgentDraft` keeps both — going car → PT → car should not forget that this
 * passenger drives the greenest way.
 */
export type AgentChoice = {
  agentId: number;
  mode: TransportMode;
  carOptimization: CarOptimization;
  ptOptimization: PTOptimization;
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
      /**
       * A turn this seat had begun in this round before the page went away
       * (S7). Applied only when the draft is actually built fresh — see below.
       */
      choices?: AgentChoice[];
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

      /**
       * Restoring rides on the `sameShape` guard above rather than having one
       * of its own, and that is deliberate: a restore may only ever happen when
       * this branch builds the agents, i.e. once per seat per round. React
       * Query re-delivers the assignment on every remount and focus change
       * while storage still holds the taps the turn began with, so a restore
       * that ran again would quietly undo the last choice each time the screen
       * came back.
       *
       * The route is *not* restored — `status` stays `empty`, which is exactly
       * what `use-round-draft.ts`'s routing effect looks for. See the header.
       */
      const stored = new Map((action.choices ?? []).map((c) => [c.agentId, c]));

      return {
        seatId: action.seatId,
        roundNumber: action.roundNumber,
        homeNode: action.homeNode,
        agents: action.agents.map((a) => {
          const agent = freshAgent(a.id, a.destination_node);
          const choice = stored.get(a.id);
          if (!choice) return agent;
          return {
            ...agent,
            mode: choice.mode,
            carOptimization: choice.carOptimization,
            ptOptimization: choice.ptOptimization,
          };
        }),
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
 * The taps worth keeping across a reload: every agent that has a mode.
 *
 * Status is not consulted on purpose. A route still searching, or one that
 * failed, is a choice the student made and would have to make again — half a
 * turn is the case the whole feature exists for.
 */
export function draftChoices(draft: RoundDraft): AgentChoice[] {
  return draft.agents
    .filter((agent) => agent.mode !== null)
    .map((agent) => ({
      agentId: agent.agentId,
      mode: agent.mode as TransportMode,
      carOptimization: agent.carOptimization,
      ptOptimization: agent.ptOptimization,
    }));
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
