import { describe, expect, it } from "vitest";

import type { GameEvent, RosterSeat } from "@/lib/game/events";
import {
  budgetUsed,
  currentScreen,
  gameReducer,
  hostControlledSeats,
  hostSeat,
  initialGameState,
  moveProgress,
  playingSeats,
  seatById,
  type GameState,
  type LobbySnapshot,
} from "@/lib/game/game-state";

const snapshot: LobbySnapshot = {
  game_id: "ABC123",
  game_name: "Testspiel",
  max_players: 4,
  agent_per_player: 3,
  max_rounds: 5,
  max_co2_level_kg: 120,
  chat_enabled: true,
  is_active: false,
  started_at: null,
  ended_at: null,
  paused_at: null,
  joinable: true,
  reason: null,
  players: [
    {
      player_id: "H-1",
      name: "Sarah Wolf (Host)",
      is_host: true,
      controlled_by_host: false,
      is_muted: false,
    },
    {
      player_id: "P-1",
      name: "Alex",
      is_host: false,
      controlled_by_host: false,
      is_muted: false,
    },
  ],
};

function seat(overrides: Partial<RosterSeat> = {}): RosterSeat {
  return {
    player_id: "P-1",
    name: "Alex",
    is_host: false,
    controlled_by_host: false,
    online: true,
    status: "ready",
    ...overrides,
  };
}

function apply(state: GameState, ...events: GameEvent[]): GameState {
  return events.reduce(
    (acc, event) => gameReducer(acc, { kind: "event", event }),
    state,
  );
}

const start = () =>
  gameReducer(initialGameState("ABC123"), { kind: "snapshot", snapshot });

const roundStarted = (n: number): GameEvent => ({
  type: "round.started",
  game_id: "ABC123",
  data: {
    round_number: n,
    max_rounds: 5,
    total_game_emissions_g: 0,
    max_co2_level_g: 120_000,
  },
});

describe("snapshot", () => {
  it("seeds settings and seats", () => {
    const state = start();

    expect(state.gameName).toBe("Testspiel");
    expect(state.agentPerPlayer).toBe(3);
    expect(state.maxCo2LevelKg).toBe(120);
    expect(state.seats).toHaveLength(2);
    expect(state.socketSpoke).toBe(false);
  });

  it("starts every seat offline, because the snapshot cannot know", () => {
    expect(start().seats.every((s) => !s.online)).toBe(true);
  });

  // The generalised form of the race F1 found in the lobby: the snapshot is
  // read once at mount and says nothing about what happened since, so once the
  // socket has spoken it must not move lifecycle fields back.
  it("does not move the game backwards when it resolves late", () => {
    const live = apply(start(), {
      type: "game.started",
      game_id: "ABC123",
      data: {
        game_name: "Testspiel",
        max_rounds: 5,
        max_co2_level: 120,
        current_round: 1,
        started_at: "2026-09-18T09:00:00Z",
      },
    });

    const after = gameReducer(live, { kind: "snapshot", snapshot });

    expect(after.isActive).toBe(true);
    expect(after.startedAt).toBe("2026-09-18T09:00:00Z");
    // Settings the socket never carries are still taken.
    expect(after.gameName).toBe("Testspiel");
  });

  it("does not overwrite a roster that already arrived", () => {
    const live = apply(start(), {
      type: "roster.update",
      game_id: "ABC123",
      players: [seat({ online: true, status: "ready" })],
    });

    const after = gameReducer(live, { kind: "snapshot", snapshot });

    expect(after.seats).toHaveLength(1);
    expect(after.seats[0].online).toBe(true);
  });
});

describe("game.state resync", () => {
  // The consumer sends this right after accept(), so it arrives on every
  // reconnect too. That is why nothing refetches after a dropped socket.
  it("takes the whole lifecycle from a reconnect snapshot", () => {
    const state = apply(start(), {
      type: "game.state",
      game_id: "ABC123",
      data: {
        isActive: true,
        currentRound: 3,
        totalEmissionsG: 40_000,
        maxCo2LevelG: 120_000,
        maxRounds: 5,
        startedAt: "2026-09-18T09:00:00Z",
        endedAt: null,
        pausedAt: "2026-09-18T09:30:00Z",
        betweenRoundPhase: "voting",
        activeMapVersionId: 7,
        hasMapVersions: true,
        mapVersions: [
          {
            id: 9,
            name: "Busspur",
            poll_text: "Neue Busspur?",
            is_rollback: false,
            change_img_url: null,
          },
        ],
      },
    });

    expect(state.currentRound).toBe(3);
    expect(state.phase).toBe("voting");
    expect(state.pausedAt).toBe("2026-09-18T09:30:00Z");
    // The ballot is stored on the round, so a mid-vote reconnect gets the same
    // options back rather than a fresh draw.
    expect(state.voteOptions).toHaveLength(1);
  });
});

describe("rounds and phases", () => {
  it("moves into the stats phase when a round completes", () => {
    const state = apply(start(), roundStarted(1), {
      type: "round.completed",
      game_id: "ABC123",
      data: {
        round_number: 1,
        round_emissions_g: 12_000,
        round_cost_eur: 8.5,
        total_game_emissions_g: 12_000,
        max_co2_level_g: 120_000,
        player_stats: [],
        simulation_used: true,
        has_map_versions: false,
        map_versions: [],
      },
    });

    expect(state.phase).toBe("stats");
    expect(state.lastRound?.emissionsG).toBe(12_000);
    expect(state.totalEmissionsG).toBe(12_000);
    expect(currentScreen(state)).toBe("between-rounds");
  });

  it("clears the last round's aftermath when the next one starts", () => {
    const state = apply(
      start(),
      roundStarted(1),
      {
        type: "vote.opened",
        game_id: "ABC123",
        data: {
          versions: [
            {
              id: 9,
              name: "Busspur",
              poll_text: "?",
              is_rollback: false,
              change_img_url: null,
            },
          ],
        },
      },
      {
        type: "vote.recorded",
        game_id: "ABC123",
        data: { player_id: "P-1", votes_cast: 1, votes_needed: 2 },
      },
      roundStarted(2),
    );

    expect(state.currentRound).toBe(2);
    expect(state.phase).toBe("none");
    expect(state.voteOptions).toEqual([]);
    expect(state.votes).toBeNull();
    expect(state.voteOutcome).toBeNull();
  });

  it("follows a vote through a tie and a revote", () => {
    let state = apply(start(), roundStarted(1), {
      type: "vote.stalemate",
      game_id: "ABC123",
      data: {
        stalemate: true,
        stalemate_count: 1,
        vote_counts: [],
        winning_version_id: null,
        winning_version_name: "So lassen",
      },
    });
    expect(state.phase).toBe("stalemate");

    state = apply(state, {
      type: "stalemate.progress",
      game_id: "ABC123",
      data: { cast: 1, needed: 2 },
    });
    expect(state.stalemate).toEqual({ cast: 1, needed: 2 });

    // A reopened vote starts both counts again.
    state = apply(state, {
      type: "vote.opened",
      game_id: "ABC123",
      data: { versions: [] },
    });
    expect(state.phase).toBe("voting");
    expect(state.stalemate).toBeNull();
    expect(state.votes).toBeNull();
  });

  it("tracks simulation progress and drops it when the round lands", () => {
    let state = apply(start(), roundStarted(1), {
      type: "simulation.progress",
      game_id: "ABC123",
      data: { round_number: 1, status: "running", progress_percent: 40 },
    });
    expect(state.simulation?.percent).toBe(40);

    state = apply(state, {
      type: "round.completed",
      game_id: "ABC123",
      data: {
        round_number: 1,
        round_emissions_g: 1,
        round_cost_eur: 1,
        total_game_emissions_g: 1,
        max_co2_level_g: 120_000,
        player_stats: [],
        simulation_used: true,
        has_map_versions: false,
        map_versions: [],
      },
    });
    expect(state.simulation).toBeNull();
  });
});

describe("pause and end", () => {
  it("pauses and resumes", () => {
    let state = apply(start(), {
      type: "game.paused",
      game_id: "ABC123",
      data: { paused_at: "2026-09-18T09:20:00Z" },
    });
    expect(state.pausedAt).toBe("2026-09-18T09:20:00Z");

    state = apply(state, {
      type: "game.resumed",
      game_id: "ABC123",
      data: {} as Record<string, never>,
    });
    expect(state.pausedAt).toBeNull();
  });

  it("records why the game ended", () => {
    const state = apply(start(), {
      type: "game.ended",
      game_id: "ABC123",
      data: {
        reason: "co2_limit",
        final_round: 3,
        total_emissions_g: 130_000,
        max_co2_level_g: 120_000,
        ended_at: "2026-09-18T10:00:00Z",
      },
    });

    expect(state.endReason).toBe("co2_limit");
    expect(currentScreen(state)).toBe("ended");
  });
});

describe("revocation is terminal", () => {
  it("ignores everything after the seat is gone", () => {
    const revoked = apply(start(), {
      type: "player.revoked",
      game_id: "ABC123",
      data: { reason: "taken_over" },
    });

    const after = apply(revoked, roundStarted(9));
    const afterSnapshot = gameReducer(revoked, { kind: "snapshot", snapshot });

    expect(after.currentRound).toBe(0);
    expect(after.revoked).toBe("taken_over");
    expect(afterSnapshot.revoked).toBe("taken_over");
  });

  it("treats an empty reason as a removal, not as no revocation", () => {
    const state = apply(start(), {
      type: "player.revoked",
      game_id: "ABC123",
      data: { reason: "" },
    });

    expect(state.revoked).toBe("removed");
    expect(currentScreen(state)).toBe("revoked");
  });
});

describe("exhaustiveness", () => {
  /**
   * The guard that makes the rest worth having. `gameReducer`'s default branch
   * calls `assertNever`, so TypeScript fails the build when an event in
   * `events.ts` has no case — which is precisely how seven events managed to
   * arrive for months with nothing listening. This test covers the runtime
   * half: an event the union does not describe must be loud, not silent.
   */
  it("throws on an event it was never told about", () => {
    const bogus = {
      type: "round.cancelled",
      game_id: "ABC123",
      data: {},
    } as unknown as GameEvent;

    expect(() => apply(start(), bogus)).toThrow(/round.cancelled/);
  });

  it("handles every event the backend sends without throwing", () => {
    // One frame per event name in events.ts. Payloads are minimal — this is
    // about coverage of the switch, not about the fields.
    const every: GameEvent[] = [
      { type: "pong" },
      { type: "error", message: "nope" },
      { type: "roster.update", game_id: "ABC123", players: [] },
      {
        type: "player.joined",
        game_id: "ABC123",
        data: {
          player_id: "P-2",
          player_name: "Kim",
          controlled_by_host: false,
          agent_assignments: null,
        },
      },
      {
        type: "player.left",
        game_id: "ABC123",
        data: { player_id: "P-2", player_name: "Kim", was_kicked: false },
      },
      {
        type: "player.taken_over",
        game_id: "ABC123",
        data: { old_player_id: "P-2", new_player_id: "P-9" },
      },
      {
        type: "player.handed_over",
        game_id: "ABC123",
        data: { old_player_id: "P-2", new_player_id: "P-9" },
      },
      {
        type: "game.started",
        game_id: "ABC123",
        data: {
          game_name: "T",
          max_rounds: 5,
          max_co2_level: 120,
          current_round: 1,
          started_at: null,
        },
      },
      {
        type: "game.paused",
        game_id: "ABC123",
        data: { paused_at: "2026-09-18T09:00:00Z" },
      },
      {
        type: "game.resumed",
        game_id: "ABC123",
        data: {} as Record<string, never>,
      },
      roundStarted(1),
      {
        type: "round.completed",
        game_id: "ABC123",
        data: {
          round_number: 1,
          round_emissions_g: 0,
          round_cost_eur: 0,
          total_game_emissions_g: 0,
          max_co2_level_g: 120_000,
          player_stats: [],
          simulation_used: false,
          has_map_versions: false,
          map_versions: [],
        },
      },
      {
        type: "simulation.progress",
        game_id: "ABC123",
        data: { round_number: 1, status: "starting", progress_percent: 0 },
      },
      {
        type: "stats.all_acked",
        game_id: "ABC123",
        data: { next_phase: "discussion" },
      },
      { type: "vote.opened", game_id: "ABC123", data: { versions: [] } },
      {
        type: "vote.recorded",
        game_id: "ABC123",
        data: { player_id: "P-1", votes_cast: 1, votes_needed: 2 },
      },
      {
        type: "vote.result",
        game_id: "ABC123",
        data: {
          stalemate: false,
          winning_version_id: 9,
          winning_version_name: "Busspur",
          vote_counts: [],
        },
      },
      {
        type: "vote.stalemate",
        game_id: "ABC123",
        data: {
          stalemate: true,
          stalemate_count: 1,
          vote_counts: [],
          winning_version_id: null,
          winning_version_name: "So lassen",
        },
      },
      {
        type: "stalemate.progress",
        game_id: "ABC123",
        data: { cast: 1, needed: 2 },
      },
      {
        type: "game.state",
        game_id: "ABC123",
        data: {
          isActive: true,
          currentRound: 1,
          totalEmissionsG: 0,
          maxCo2LevelG: 120_000,
          maxRounds: 5,
          startedAt: null,
          endedAt: null,
          pausedAt: null,
          betweenRoundPhase: "none",
          activeMapVersionId: null,
          hasMapVersions: false,
          mapVersions: [],
        },
      },
      {
        type: "game.ended",
        game_id: "ABC123",
        data: {
          reason: "max_rounds",
          final_round: 5,
          total_emissions_g: 0,
          max_co2_level_g: 120_000,
          ended_at: null,
        },
      },
      // Last, because it is terminal.
      { type: "player.revoked", game_id: "ABC123", data: { reason: "left" } },
    ];

    expect(() => apply(start(), ...every)).not.toThrow();
  });
});

describe("selectors", () => {
  const withRoster = () =>
    apply(start(), {
      type: "roster.update",
      game_id: "ABC123",
      players: [
        seat({ player_id: "H-1", name: "Host", is_host: true }),
        seat({ player_id: "P-1", status: "waiting" }),
        seat({ player_id: "P-2", name: "Kim", controlled_by_host: true }),
        seat({ player_id: "P-3", name: "Sam", status: "making_move" }),
      ],
    });

  // The host's own row is never a seat — the round does not wait for it and it
  // does not count against max_players. `PlayerQuerySet.playing()` is the
  // backend half of the same rule.
  it("keeps the host's own row out of the playing seats", () => {
    const state = withRoster();

    expect(playingSeats(state).map((s) => s.player_id)).toEqual([
      "P-1",
      "P-2",
      "P-3",
    ]);
    expect(hostSeat(state)?.player_id).toBe("H-1");
  });

  // 1.6: a seat played at the host machine is still a seat. That is the whole
  // point — a class where not everyone has a phone.
  it("counts seats played at the host machine, and can list them", () => {
    const state = withRoster();

    expect(hostControlledSeats(state).map((s) => s.name)).toEqual(["Kim"]);
    expect(moveProgress(state)).toEqual({ done: 1, total: 3 });
  });

  it("finds a seat by id, and copes with none", () => {
    const state = withRoster();

    expect(seatById(state, "P-2")?.name).toBe("Kim");
    expect(seatById(state, null)).toBeNull();
    expect(seatById(state, "nope")).toBeNull();
  });

  it("picks the screen from the game, not from the route", () => {
    expect(currentScreen(start())).toBe("lobby");
    // A round number is proof the game is running, even without game.started —
    // which is what a client that joined mid-game or missed the event sees.
    expect(currentScreen(apply(start(), roundStarted(1)))).toBe("playing");

    const playing = apply(start(), {
      type: "game.started",
      game_id: "ABC123",
      data: {
        game_name: "T",
        max_rounds: 5,
        max_co2_level: 120,
        current_round: 1,
        started_at: "2026-09-18T09:00:00Z",
      },
    });
    expect(currentScreen(playing)).toBe("playing");
  });

  it("reports the budget as a fraction and survives a missing limit", () => {
    const state = { ...start(), totalEmissionsG: 30_000, maxCo2LevelG: 120_000 };

    expect(budgetUsed(state)).toBe(0.25);
    expect(budgetUsed({ ...state, maxCo2LevelG: 0 })).toBe(0);
  });
});
