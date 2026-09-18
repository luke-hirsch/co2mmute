import { describe, expect, it } from "vitest";

import type { GameEvent, RosterSeat } from "@/lib/game/events";
import {
  hostSeat,
  initialLobbyState,
  lobbyReducer,
  lobbyStateFromSnapshot,
  playingSeats,
  type LobbySnapshot,
  type LobbyState,
} from "@/lib/game/lobby-state";

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

function apply(state: LobbyState, ...events: GameEvent[]): LobbyState {
  return events.reduce(
    (acc, event) => lobbyReducer(acc, { kind: "event", event }),
    state,
  );
}

const start = () =>
  lobbyReducer(initialLobbyState("ABC123"), { kind: "snapshot", snapshot });

describe("lobbyStateFromSnapshot", () => {
  it("maps the REST body onto the state", () => {
    const state = lobbyStateFromSnapshot(snapshot);

    expect(state.gameId).toBe("ABC123");
    expect(state.gameName).toBe("Testspiel");
    expect(state.maxPlayers).toBe(4);
    expect(state.maxCo2LevelKg).toBe(120);
    expect(state.revoked).toBeNull();
  });

  // The lobby endpoint knows who is in the game but not who is connected —
  // presence lives in the cache and only roster.update carries it.
  it("starts every seat offline, because the snapshot cannot know", () => {
    const state = lobbyStateFromSnapshot(snapshot);

    expect(state.seats.map((s) => s.online)).toEqual([false, false]);
    expect(state.seats.map((s) => s.status)).toEqual([
      "not_connected",
      "not_connected",
    ]);
  });
});

describe("lobbyReducer", () => {
  it("lets roster.update replace the seat list wholesale", () => {
    const state = apply(start(), {
      type: "roster.update",
      game_id: "ABC123",
      players: [seat(), seat({ player_id: "P-2", name: "Kim", online: false })],
    });

    expect(state.seats).toHaveLength(2);
    expect(state.seats[0].online).toBe(true);
    expect(state.seats[1].name).toBe("Kim");
  });

  // player.joined and player.left are announcements; the roster that follows
  // them is the list. Two authorities for one list is the bug this whole layer
  // exists to remove.
  it("does not edit the seat list from player.joined", () => {
    const before = start();
    const after = apply(before, {
      type: "player.joined",
      game_id: "ABC123",
      data: {
        player_id: "P-9",
        player_name: "Neu",
        controlled_by_host: false,
        agent_assignments: null,
      },
    });

    expect(after.seats).toEqual(before.seats);
  });

  it("follows the game through start, pause, resume and end", () => {
    let state = apply(start(), {
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
    expect(state.isActive).toBe(true);
    expect(state.startedAt).toBe("2026-09-18T09:00:00Z");

    state = apply(state, {
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

    state = apply(state, {
      type: "game.ended",
      game_id: "ABC123",
      data: {
        reason: "max_rounds",
        final_round: 5,
        total_emissions_g: 1000,
        max_co2_level_g: 120000,
        ended_at: "2026-09-18T10:00:00Z",
      },
    });
    expect(state.isActive).toBe(false);
    expect(state.endedAt).toBe("2026-09-18T10:00:00Z");
  });

  // The race that actually bit, found in WebKit on 2026-09-18: the socket
  // connects and the backend answers with a full roster before the REST
  // snapshot resolves. The snapshot cannot know who is connected, so letting it
  // land would blank out presence that was already right — the lobby showed
  // "nicht verbunden" for people who were visibly online.
  it("does not let a late snapshot overwrite a roster that already arrived", () => {
    const live = apply(start(), {
      type: "roster.update",
      game_id: "ABC123",
      players: [seat({ online: true, status: "ready" })],
    });

    const after = lobbyReducer(live, { kind: "snapshot", snapshot });

    expect(after.seats).toHaveLength(1);
    expect(after.seats[0].online).toBe(true);
    expect(after.seats[0].status).toBe("ready");
  });

  // The other order is the normal one and has to keep working.
  it("takes the snapshot when no roster has arrived yet", () => {
    const state = start();

    expect(state.hasLiveRoster).toBe(false);
    expect(state.seats).toHaveLength(2);
  });

  // Settings still come from the snapshot even when the roster beat it there.
  it("still applies the snapshot's settings when the roster came first", () => {
    const live = apply(initialLobbyState("ABC123"), {
      type: "roster.update",
      game_id: "ABC123",
      players: [seat()],
    });

    const after = lobbyReducer(live, { kind: "snapshot", snapshot });

    expect(after.gameName).toBe("Testspiel");
    expect(after.maxPlayers).toBe(4);
    expect(after.seats).toHaveLength(1);
  });

  it("records why the seat was revoked", () => {
    const state = apply(start(), {
      type: "player.revoked",
      game_id: "ABC123",
      data: { reason: "taken_over" },
    });

    expect(state.revoked).toBe("taken_over");
  });

  // The socket closes right after player.revoked, so a revocation is terminal.
  // A snapshot resolving late must not put the lobby back on screen.
  it("keeps a revocation even if the snapshot arrives afterwards", () => {
    const revoked = apply(start(), {
      type: "player.revoked",
      game_id: "ABC123",
      data: { reason: "removed" },
    });

    const after = lobbyReducer(revoked, { kind: "snapshot", snapshot });

    expect(after.revoked).toBe("removed");
  });

  it("treats a revocation without a reason as a removal, not as no revocation", () => {
    const state = apply(start(), {
      type: "player.revoked",
      game_id: "ABC123",
      data: { reason: "" },
    });

    expect(state.revoked).toBe("removed");
  });

  it("ignores events the lobby has no opinion on", () => {
    const before = start();
    const after = apply(before, {
      type: "vote.recorded",
      game_id: "ABC123",
      data: { player_id: "P-1", votes_cast: 1, votes_needed: 3 },
    });

    expect(after).toBe(before);
  });
});

describe("seat selectors", () => {
  // The host's own row is never a seat: the round does not wait for it and it
  // does not count against max_players. `PlayerQuerySet.playing()` is the
  // backend half of the same rule.
  it("leaves the host's own row out of the playing seats", () => {
    const state = apply(start(), {
      type: "roster.update",
      game_id: "ABC123",
      players: [
        seat({ player_id: "H-1", name: "Host", is_host: true }),
        seat(),
        seat({ player_id: "P-2", name: "Kim", controlled_by_host: true }),
      ],
    });

    expect(playingSeats(state).map((s) => s.player_id)).toEqual(["P-1", "P-2"]);
    expect(hostSeat(state)?.player_id).toBe("H-1");
  });

  // A seat played at the host machine is still a seat — that is exactly the
  // 1.6 case where a whole class shares one device.
  it("counts a seat played at the host machine", () => {
    const state = apply(start(), {
      type: "roster.update",
      game_id: "ABC123",
      players: [seat({ controlled_by_host: true })],
    });

    expect(playingSeats(state)).toHaveLength(1);
  });
});
