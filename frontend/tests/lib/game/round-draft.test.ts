import { describe, expect, it } from "vitest";

import {
  DEFAULT_CAR_OPTIMIZATION,
  DEFAULT_PT_OPTIMIZATION,
  draftChoices,
  draftComplete,
  draftPayload,
  draftProgress,
  draftRouting,
  initialRoundDraft,
  roundDraftReducer,
  type AgentChoice,
  type RoundDraft,
  type RoundDraftAction,
} from "@/lib/game/round-draft";
import type { AgentRoute } from "@/types/routeTypes";

/**
 * The turn of one seat, before it is submitted.
 *
 * What is worth testing here is not "does a setter set" but the three rules the
 * old `useAgentRoutes` got wrong, each of which showed up as a state bug on the
 * legacy screen:
 *
 *  - a re-delivered assignment must not wipe a half-made choice;
 *  - changing the mode must drop the route that belonged to the old one;
 *  - the submission payload is the DRF serializer's shape, snake_case and all,
 *    and it is null unless every agent is actually ready.
 */

const ASSIGN: RoundDraftAction = {
  kind: "assign",
  seatId: "P-1",
  roundNumber: 1,
  homeNode: 10,
  agents: [
    { id: 1, destination_node: 20 },
    { id: 2, destination_node: 30 },
  ],
};

function route(overrides: Partial<AgentRoute> = {}): AgentRoute {
  return {
    agentId: 1,
    transportMode: "car",
    optimization: "time",
    totalDistanceM: 4200,
    estimatedTimeMin: 11.5,
    segments: [
      {
        edgeId: 101,
        startNode: 10,
        endNode: 15,
        mode: "car",
        distanceM: 2000,
        estimatedTimeMin: 5.5,
        ptLineId: undefined,
      },
      {
        edgeId: 102,
        startNode: 15,
        endNode: 20,
        mode: "car",
        distanceM: 2200,
        estimatedTimeMin: 6,
        ptLineId: undefined,
      },
    ],
    // Not the way there turned round: other edges, another length. A payload
    // that sent the first leg twice would still pass with a mirror.
    wayHome: {
      totalDistanceM: 4300,
      estimatedTimeMin: 12,
      segments: [
        {
          edgeId: 112,
          startNode: 20,
          endNode: 15,
          mode: "car",
          distanceM: 2200,
          estimatedTimeMin: 6,
          ptLineId: undefined,
        },
        {
          edgeId: 111,
          startNode: 15,
          endNode: 10,
          mode: "car",
          distanceM: 2100,
          estimatedTimeMin: 6,
          ptLineId: undefined,
        },
      ],
    },
    ...overrides,
  } as AgentRoute;
}

function apply(draft: RoundDraft, ...actions: RoundDraftAction[]): RoundDraft {
  return actions.reduce(roundDraftReducer, draft);
}

/** An assigned draft where every agent already has a route. */
function readyDraft(): RoundDraft {
  return apply(
    initialRoundDraft(),
    ASSIGN,
    { kind: "mode", agentId: 1, mode: "car" },
    { kind: "routed", agentId: 1, route: route() },
    { kind: "mode", agentId: 2, mode: "bike" },
    {
      kind: "routed",
      agentId: 2,
      route: route({
        agentId: 2,
        transportMode: "bike",
        optimization: undefined,
        segments: [
          {
            edgeId: 201,
            startNode: 10,
            endNode: 30,
            mode: "bike",
            distanceM: 1500,
            estimatedTimeMin: 7,
            ptLineId: undefined,
          },
        ],
        wayHome: {
          totalDistanceM: 1500,
          estimatedTimeMin: 7,
          segments: [
            {
              edgeId: 202,
              startNode: 30,
              endNode: 10,
              mode: "bike",
              distanceM: 1500,
              estimatedTimeMin: 7,
              ptLineId: undefined,
            },
          ],
        },
      }),
    },
  );
}

describe("roundDraftReducer — assignment", () => {
  it("turns agent assignments into one draft agent each", () => {
    const draft = apply(initialRoundDraft(), ASSIGN);

    expect(draft.seatId).toBe("P-1");
    expect(draft.roundNumber).toBe(1);
    expect(draft.homeNode).toBe(10);
    expect(draft.agents.map((a) => a.agentId)).toEqual([1, 2]);
    expect(draft.agents.map((a) => a.destinationNode)).toEqual([20, 30]);
    expect(draft.agents.every((a) => a.mode === null)).toBe(true);
    expect(draft.agents.every((a) => a.status === "empty")).toBe(true);
    expect(draft.agents[0].carOptimization).toBe(DEFAULT_CAR_OPTIMIZATION);
    expect(draft.agents[0].ptOptimization).toBe(DEFAULT_PT_OPTIMIZATION);
  });

  it("is idempotent: the same assignment again keeps a half-made choice", () => {
    // React Query hands back the same assignment object on every remount and
    // focus change. The old hook nearly wiped the turn each time and worked
    // around it by comparing joined agent ids; here the rule is the reducer's.
    const chosen = apply(initialRoundDraft(), ASSIGN, {
      kind: "mode",
      agentId: 1,
      mode: "walk",
    });

    const again = roundDraftReducer(chosen, ASSIGN);

    expect(again).toBe(chosen);
    expect(again.agents[0].mode).toBe("walk");
  });

  it("starts over when the round advances", () => {
    const chosen = apply(initialRoundDraft(), ASSIGN, {
      kind: "mode",
      agentId: 1,
      mode: "walk",
    });

    const nextRound = roundDraftReducer(chosen, { ...ASSIGN, roundNumber: 2 });

    expect(nextRound.roundNumber).toBe(2);
    expect(nextRound.agents.every((a) => a.mode === null)).toBe(true);
    // The assignment itself does not change between rounds — home and
    // destinations belong to the player, not to the round.
    expect(nextRound.homeNode).toBe(10);
    expect(nextRound.agents.map((a) => a.destinationNode)).toEqual([20, 30]);
  });

  it("starts over when another seat is being played", () => {
    // F4 plays someone else's seat through this same screen. Carrying the
    // previous seat's choices over would submit them for the wrong player.
    const chosen = apply(initialRoundDraft(), ASSIGN, {
      kind: "mode",
      agentId: 1,
      mode: "walk",
    });

    const otherSeat = roundDraftReducer(chosen, { ...ASSIGN, seatId: "P-2" });

    expect(otherSeat.seatId).toBe("P-2");
    expect(otherSeat.agents.every((a) => a.mode === null)).toBe(true);
  });
});

describe("roundDraftReducer — choosing", () => {
  it("drops the route when the mode changes", () => {
    // Otherwise the screen shows, for a moment, a car route under a bike icon.
    const withRoute = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "routed", agentId: 1, route: route() },
    );
    expect(withRoute.agents[0].status).toBe("ready");

    const switched = roundDraftReducer(withRoute, {
      kind: "mode",
      agentId: 1,
      mode: "bike",
    });

    expect(switched.agents[0].mode).toBe("bike");
    expect(switched.agents[0].route).toBeNull();
    expect(switched.agents[0].status).toBe("empty");
  });

  it("drops the route when an optimization changes", () => {
    const withRoute = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "routed", agentId: 1, route: route() },
    );

    const cheaper = roundDraftReducer(withRoute, {
      kind: "car-optimization",
      agentId: 1,
      optimization: "co2",
    });

    expect(cheaper.agents[0].carOptimization).toBe("co2");
    expect(cheaper.agents[0].route).toBeNull();
    expect(cheaper.agents[0].status).toBe("empty");
  });

  it("keeps the other optimization across a mode switch", () => {
    // Switching car → PT → car should not forget that this agent drives the
    // greenest way; the setting belongs to the agent, not to the current mode.
    const draft = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "car-optimization", agentId: 1, optimization: "co2" },
      { kind: "mode", agentId: 1, mode: "public" },
      { kind: "mode", agentId: 1, mode: "car" },
    );

    expect(draft.agents[0].carOptimization).toBe("co2");
  });

  it("records a failed route with its reason and no route", () => {
    const draft = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "routing", agentId: 1 },
      { kind: "route-failed", agentId: 1, error: "no-route" },
    );

    expect(draft.agents[0].status).toBe("failed");
    expect(draft.agents[0].error).toBe("no-route");
    expect(draft.agents[0].route).toBeNull();
  });

  it("clears one agent back to untouched without touching the others", () => {
    const draft = apply(readyDraft(), { kind: "clear", agentId: 1 });

    expect(draft.agents[0].mode).toBeNull();
    expect(draft.agents[0].route).toBeNull();
    expect(draft.agents[0].status).toBe("empty");
    expect(draft.agents[1].status).toBe("ready");
  });

  it("leaves the draft untouched for an agent that is not in it", () => {
    const draft = apply(initialRoundDraft(), ASSIGN);

    expect(roundDraftReducer(draft, { kind: "mode", agentId: 99, mode: "car" })).toBe(
      draft,
    );
  });
});

describe("round draft selectors", () => {
  it("counts progress and is only complete when every agent has a route", () => {
    const half = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "routed", agentId: 1, route: route() },
    );

    expect(draftProgress(half)).toEqual({ done: 1, total: 2 });
    expect(draftComplete(half)).toBe(false);
    expect(draftComplete(readyDraft())).toBe(true);
    expect(draftProgress(readyDraft())).toEqual({ done: 2, total: 2 });
  });

  it("is not complete before an assignment arrives", () => {
    // Nothing chosen and nothing to choose is not "everything is ready".
    expect(draftComplete(initialRoundDraft())).toBe(false);
  });

  it("knows while a route is being computed", () => {
    const draft = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "routing", agentId: 1 },
    );

    expect(draftRouting(draft)).toBe(true);
    expect(draftRouting(readyDraft())).toBe(false);
  });

  it("builds the payload in the serializer's shape", () => {
    // PlayerMoveWithRoutesInputSerializer + RouteSegmentInputSerializer in
    // game/serializers.py. snake_case, and the backend checks that the first
    // segment starts at home and the last ends at the destination.
    const payload = draftPayload(readyDraft());

    expect(payload).toEqual({
      agents: [
        {
          id: 1,
          transport_mode: "car",
          optimization: "time",
          route: {
            total_distance_m: 4200,
            estimated_time_min: 11.5,
            segments: [
              {
                edge_id: 101,
                start_node: 10,
                end_node: 15,
                mode: "car",
                pt_line_id: undefined,
              },
              {
                edge_id: 102,
                start_node: 15,
                end_node: 20,
                mode: "car",
                pt_line_id: undefined,
              },
            ],
          },
          return_route: {
            total_distance_m: 4300,
            estimated_time_min: 12,
            segments: [
              {
                edge_id: 112,
                start_node: 20,
                end_node: 15,
                mode: "car",
                pt_line_id: undefined,
              },
              {
                edge_id: 111,
                start_node: 15,
                end_node: 10,
                mode: "car",
                pt_line_id: undefined,
              },
            ],
          },
        },
        {
          id: 2,
          transport_mode: "bike",
          optimization: undefined,
          route: {
            total_distance_m: 4200,
            estimated_time_min: 11.5,
            segments: [
              {
                edge_id: 201,
                start_node: 10,
                end_node: 30,
                mode: "bike",
                pt_line_id: undefined,
              },
            ],
          },
          return_route: {
            total_distance_m: 1500,
            estimated_time_min: 7,
            segments: [
              {
                edge_id: 202,
                start_node: 30,
                end_node: 10,
                mode: "bike",
                pt_line_id: undefined,
              },
            ],
          },
        },
      ],
    });
  });

  it("sends an optimization only for the car", () => {
    // `optimization` is a ChoiceField over AgentRoute.Optimization, whose
    // choices are the car's. Sending the PT one would be a 400.
    const draft = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "public" },
      { kind: "pt-optimization", agentId: 1, optimization: "no_bus" },
      { kind: "routed", agentId: 1, route: route({ transportMode: "public" }) },
      { kind: "mode", agentId: 2, mode: "walk" },
      { kind: "routed", agentId: 2, route: route({ agentId: 2, transportMode: "walk" }) },
    );

    const payload = draftPayload(draft);

    expect(payload?.agents[0].optimization).toBeUndefined();
    expect(payload?.agents[1].optimization).toBeUndefined();
  });

  it("refuses to build a payload while an agent is unrouted", () => {
    const half = apply(initialRoundDraft(), ASSIGN, {
      kind: "mode",
      agentId: 1,
      mode: "car",
    });

    expect(draftPayload(half)).toBeNull();
    expect(draftPayload(initialRoundDraft())).toBeNull();
  });
});

/**
 * A reload in the middle of an unfinished turn (S7).
 *
 * A locked phone discards the page; in a classroom that is the ordinary case,
 * not the edge case. What comes back is the **taps** — the mode and the two
 * optimisations — and never the route: `use-round-draft.ts` already re-routes
 * anyone holding a mode with no route, so the routes are recomputed against the
 * graph the game is on now. That is what keeps the pathfinder the single source
 * of truth for a route, which is the rule this file's header is about.
 */
describe("roundDraftReducer — restoring a turn", () => {
  const CHOICES: AgentChoice[] = [
    {
      agentId: 1,
      mode: "car",
      carOptimization: "co2",
      ptOptimization: DEFAULT_PT_OPTIMIZATION,
    },
    {
      agentId: 2,
      mode: "public",
      carOptimization: DEFAULT_CAR_OPTIMIZATION,
      ptOptimization: "fewest_transfers",
    },
  ];

  it("puts the modes and both optimisations back", () => {
    const draft = apply(initialRoundDraft(), { ...ASSIGN, choices: CHOICES });

    expect(draft.agents.map((a) => a.mode)).toEqual(["car", "public"]);
    expect(draft.agents[0].carOptimization).toBe("co2");
    expect(draft.agents[1].ptOptimization).toBe("fewest_transfers");
  });

  /**
   * The one that makes the routes come back. `empty` plus a mode is exactly
   * what the hook's routing effect looks for, so restoring a choice re-runs the
   * search rather than resurrecting a route off the old graph.
   */
  it("leaves every restored agent unrouted, so the routes are computed again", () => {
    const draft = apply(initialRoundDraft(), { ...ASSIGN, choices: CHOICES });

    expect(draft.agents.every((a) => a.status === "empty")).toBe(true);
    expect(draft.agents.every((a) => a.route === null)).toBe(true);
    expect(draftComplete(draft)).toBe(false);
    expect(draftPayload(draft)).toBeNull();
  });

  it("restores only the agents it has, and leaves the rest fresh", () => {
    const draft = apply(initialRoundDraft(), {
      ...ASSIGN,
      choices: [CHOICES[1]],
    });

    expect(draft.agents[0].mode).toBeNull();
    expect(draft.agents[1].mode).toBe("public");
  });

  it("ignores a choice for an agent this round does not have", () => {
    const draft = apply(initialRoundDraft(), {
      ...ASSIGN,
      choices: [...CHOICES, { ...CHOICES[0], agentId: 99 }],
    });

    expect(draft.agents.map((a) => a.agentId)).toEqual([1, 2]);
    expect(draft.agents.map((a) => a.mode)).toEqual(["car", "public"]);
  });

  /**
   * The same guard the plain assignment has, and it matters more here: React
   * Query re-delivers the assignment while the storage still holds the taps the
   * turn began with, so a restore that ran twice would undo the last choice
   * every time the screen refocused.
   */
  it("does not re-apply over a turn that is already under way", () => {
    const chosen = apply(
      initialRoundDraft(),
      { ...ASSIGN, choices: CHOICES },
      { kind: "mode", agentId: 1, mode: "bike" },
    );

    const again = roundDraftReducer(chosen, { ...ASSIGN, choices: CHOICES });

    expect(again).toBe(chosen);
    expect(again.agents[0].mode).toBe("bike");
  });

  it("is the plain assignment when there is nothing to restore", () => {
    const withNone = apply(initialRoundDraft(), { ...ASSIGN, choices: [] });
    const without = apply(initialRoundDraft(), ASSIGN);

    expect(withNone).toEqual(without);
  });
});

describe("draftChoices", () => {
  it("is what gets stored: the taps of every agent that has one", () => {
    const draft = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "car-optimization", agentId: 1, optimization: "co2" },
    );

    expect(draftChoices(draft)).toEqual([
      {
        agentId: 1,
        mode: "car",
        carOptimization: "co2",
        ptOptimization: DEFAULT_PT_OPTIMIZATION,
      },
    ]);
  });

  it("carries a choice whose route has not arrived or has failed", () => {
    // Half a turn is the case this whole feature exists for. A mode that is
    // still searching, or that failed, is still a tap worth bringing back.
    const draft = apply(
      initialRoundDraft(),
      ASSIGN,
      { kind: "mode", agentId: 1, mode: "car" },
      { kind: "routing", agentId: 1 },
      { kind: "mode", agentId: 2, mode: "walk" },
      { kind: "route-failed", agentId: 2, error: "too-far" },
    );

    expect(draftChoices(draft).map((c) => c.agentId)).toEqual([1, 2]);
  });

  it("is empty before anything is chosen", () => {
    expect(draftChoices(apply(initialRoundDraft(), ASSIGN))).toEqual([]);
    expect(draftChoices(initialRoundDraft())).toEqual([]);
  });
});
