/**
 * One game, one state, one reducer.
 *
 * This replaces `lobby-state.ts` and generalises it to the whole game. The rule
 * it enforces is Roadmap.md 2.2 in one sentence: **REST seeds, the socket owns,
 * the reducer applies.** Nothing polls, and nothing refetches in response to an
 * event.
 *
 * ### Why the switch is exhaustive here
 *
 * The lobby reducer was allowed a quiet `default` — it genuinely has no opinion
 * on `vote.recorded`. This one is not: `default` calls `assertNever`, so adding
 * an event to `events.ts` breaks the build right where somebody has to decide
 * what it means. That is the guard against repeating the thing F1 found — seven
 * events (`game.paused`, `game.resumed`, `player.revoked`, `player.left`,
 * `player.taken_over`, `player.handed_over`, `simulation.progress`) arriving for
 * months with nothing listening. Events that deliberately change nothing are
 * still listed by name, with a comment saying why.
 *
 * ### Who may write what
 *
 * Two sources can set the same field, so the precedence is explicit rather than
 * incidental:
 *
 * - settings (`gameName`, `maxPlayers`, `agentPerPlayer`, `chatEnabled`) exist
 *   only in the REST snapshot;
 * - lifecycle and round fields come from the snapshot *until* the socket has
 *   spoken, and from the socket ever after;
 * - `seats` come from `roster.update` alone.
 *
 * `game.state` is what makes that work. The consumer sends it immediately after
 * `accept()`, so it arrives on every connect **and every reconnect** — the
 * reconnect is itself the resync, which is why no screen needs to refetch after
 * one.
 */

import type {
  BetweenRoundPhase,
  GameEndReason,
  GameEvent,
  RevokeReason,
  RosterSeat,
  RoundPlayerStats,
  VoteOption,
} from "@/lib/game/events";

/** `GET api/game/<game_id>/lobby/`. `game/views_join.py:LobbyStateView`. */
export type LobbySnapshot = {
  game_id: string;
  game_name: string;
  max_players: number;
  agent_per_player: number;
  max_rounds: number;
  max_co2_level_kg: number;
  chat_enabled: boolean;
  is_active: boolean;
  started_at: string | null;
  ended_at: string | null;
  paused_at: string | null;
  joinable: boolean;
  reason: string | null;
  players: {
    player_id: string;
    name: string;
    is_host: boolean;
    controlled_by_host: boolean;
    is_muted: boolean;
  }[];
};

/** What the last completed round cost, as `round.completed` reported it. */
export type RoundResult = {
  roundNumber: number;
  emissionsG: number;
  costEur: number;
  totalEmissionsG: number;
  playerStats: RoundPlayerStats[];
  /** False when the fallback figures were used instead of the simulation. */
  simulationUsed: boolean;
};

/** How the map vote came out, or that it tied. */
export type VoteOutcome = {
  stalemate: boolean;
  winningVersionId: number | null;
  winningVersionName: string;
  /** The host cut a tie short rather than letting it resolve. */
  forced: boolean;
};

export type SimulationProgress = {
  roundNumber: number;
  status: "starting" | "running" | "failed";
  percent: number;
  error: string | null;
};

export type GameState = {
  // ── identity and settings: REST only ──────────────────────────────────────
  gameId: string;
  gameName: string;
  maxPlayers: number;
  agentPerPlayer: number;
  chatEnabled: boolean;

  // ── lifecycle: REST first, then the socket ────────────────────────────────
  isActive: boolean;
  startedAt: string | null;
  endedAt: string | null;
  pausedAt: string | null;
  endReason: GameEndReason | null;

  // ── the round ─────────────────────────────────────────────────────────────
  currentRound: number;
  maxRounds: number;
  totalEmissionsG: number;
  maxCo2LevelG: number;
  maxCo2LevelKg: number;

  /**
   * The map version the game is being played on.
   *
   * Read off the socket rather than out of `GET <game_id>/<player_id>/`, which
   * is `staleTime: Infinity` and does not remount between rounds — so a client
   * that took the version from there would keep routing round 2 on round 1's
   * map after a vote. `game.state` carries it on every connect and
   * `vote.result` carries the winner, so the socket knows it at every moment it
   * can change, and nothing has to refetch to find out.
   */
  activeMapVersionId: number | null;

  // ── between rounds ────────────────────────────────────────────────────────
  phase: BetweenRoundPhase;
  voteOptions: VoteOption[];
  /** How far the vote has got. Null while no vote is open. */
  votes: { cast: number; needed: number } | null;
  /** How far the "shall we vote again?" round has got. */
  stalemate: { cast: number; needed: number } | null;
  voteOutcome: VoteOutcome | null;
  lastRound: RoundResult | null;
  simulation: SimulationProgress | null;

  // ── who is in the game ────────────────────────────────────────────────────
  seats: RosterSeat[];
  hasLiveRoster: boolean;

  // ── this device ───────────────────────────────────────────────────────────
  /** Terminal: the seat is not ours any more and the socket is closed. */
  revoked: RevokeReason | null;
  /** True once any socket frame has arrived, so REST stops being authoritative. */
  socketSpoke: boolean;
};

export type GameAction =
  | { kind: "snapshot"; snapshot: LobbySnapshot }
  | { kind: "event"; event: GameEvent };

export function initialGameState(gameId: string): GameState {
  return {
    gameId,
    gameName: "",
    maxPlayers: 0,
    agentPerPlayer: 0,
    chatEnabled: false,

    isActive: false,
    startedAt: null,
    endedAt: null,
    pausedAt: null,
    endReason: null,

    currentRound: 0,
    maxRounds: 0,
    totalEmissionsG: 0,
    maxCo2LevelG: 0,
    maxCo2LevelKg: 0,
    activeMapVersionId: null,

    phase: "none",
    voteOptions: [],
    votes: null,
    stalemate: null,
    voteOutcome: null,
    lastRound: null,
    simulation: null,

    seats: [],
    hasLiveRoster: false,

    revoked: null,
    socketSpoke: false,
  };
}

/**
 * The snapshot cannot know who is connected — presence is a cache key with a
 * TTL, and only `roster.update` carries it. A seat therefore starts offline and
 * the first roster, which arrives as soon as this socket connects, corrects it.
 */
function seatFromSnapshot(
  player: LobbySnapshot["players"][number],
): RosterSeat {
  return {
    player_id: player.player_id,
    name: player.name,
    is_host: player.is_host,
    controlled_by_host: player.controlled_by_host,
    online: false,
    status: "not_connected",
  };
}

function applySnapshot(state: GameState, snapshot: LobbySnapshot): GameState {
  // Settings only the snapshot knows. These are safe to take at any time.
  const next: GameState = {
    ...state,
    gameId: snapshot.game_id,
    gameName: snapshot.game_name,
    maxPlayers: snapshot.max_players,
    agentPerPlayer: snapshot.agent_per_player,
    chatEnabled: snapshot.chat_enabled,
    maxCo2LevelKg: snapshot.max_co2_level_kg,
  };

  // Everything below is also carried by the socket. Taking it after the socket
  // has spoken would move the game backwards: the snapshot was read once, at
  // mount, and says nothing about what happened since. This is the general form
  // of the roster race F1 found, where a late snapshot blanked out presence
  // that was already correct.
  if (!state.socketSpoke) {
    next.isActive = snapshot.is_active;
    next.startedAt = snapshot.started_at;
    next.endedAt = snapshot.ended_at;
    next.pausedAt = snapshot.paused_at;
    next.maxRounds = snapshot.max_rounds;
    next.maxCo2LevelG = snapshot.max_co2_level_kg * 1000;
  }
  if (!state.hasLiveRoster) {
    next.seats = snapshot.players.map(seatFromSnapshot);
  }
  return next;
}

/** Reached only if a `GameEvent` variant has no `case`. Fails the build. */
function assertNever(event: never): never {
  throw new Error(
    `Unhandled game event: ${JSON.stringify((event as { type?: unknown })?.type)}`,
  );
}

export function gameReducer(state: GameState, action: GameAction): GameState {
  // A revoked seat is terminal. The socket is closed, and nothing that arrives
  // afterwards — including a snapshot that was already in flight — may put the
  // game back on screen.
  if (state.revoked) return state;

  if (action.kind === "snapshot") return applySnapshot(state, action.snapshot);

  const event = action.event;
  const seen: GameState = { ...state, socketSpoke: true };

  switch (event.type) {
    // ── connection ──────────────────────────────────────────────────────────

    // Sent right after accept(), so also after every reconnect. This is the
    // resync: whatever was missed while the socket was down arrives here.
    case "game.state": {
      const s = event.data;
      return {
        ...seen,
        isActive: s.isActive,
        currentRound: s.currentRound,
        totalEmissionsG: s.totalEmissionsG,
        maxCo2LevelG: s.maxCo2LevelG,
        maxRounds: s.maxRounds,
        startedAt: s.startedAt,
        endedAt: s.endedAt,
        pausedAt: s.pausedAt,
        phase: s.betweenRoundPhase,
        activeMapVersionId: s.activeMapVersionId,
        // The ballot is stored on the round, so a reconnect mid-vote gets the
        // same options back rather than a fresh draw.
        voteOptions: s.mapVersions,
      };
    }

    // Handled inside BaseWSClient (latency, presence renewal). Nothing to store.
    case "pong":
      return state;

    // A refusal for something this client asked for — voting when it may not,
    // mostly. It belongs next to the control that triggered it, not in the
    // game's state, so screens surface it through the provider's error channel.
    case "error":
      return state;

    // ── roster and seats ────────────────────────────────────────────────────

    case "roster.update":
      return { ...seen, seats: event.players, hasLiveRoster: true };

    // Announcements. The list itself always follows as a roster.update (both
    // call schedule_broadcast), and one authority for it beats two that can
    // disagree — the same reason there is no polling.
    case "player.joined":
    case "player.left":
      return seen;

    // Someone else's seat moved to another device. Ours is unaffected; the
    // roster that follows carries the new player_id.
    case "player.taken_over":
    case "player.handed_over":
      return seen;

    case "player.revoked":
      // An empty reason still means revoked. The socket is closing either way,
      // and a screen that keeps rendering is the worse failure.
      return { ...seen, revoked: event.data.reason || "removed" };

    // ── the game itself ─────────────────────────────────────────────────────

    case "game.started":
      return {
        ...seen,
        isActive: true,
        startedAt: event.data.started_at,
        maxRounds: event.data.max_rounds,
        currentRound: event.data.current_round,
        phase: "none",
      };

    case "game.ended":
      return {
        ...seen,
        isActive: false,
        endedAt: event.data.ended_at,
        endReason: event.data.reason,
        totalEmissionsG: event.data.total_emissions_g,
        maxCo2LevelG: event.data.max_co2_level_g,
        phase: "none",
      };

    case "game.paused":
      return { ...seen, pausedAt: event.data.paused_at };

    case "game.resumed":
      return { ...seen, pausedAt: null };

    // ── rounds ──────────────────────────────────────────────────────────────

    case "round.started":
      return {
        ...seen,
        currentRound: event.data.round_number,
        maxRounds: event.data.max_rounds,
        totalEmissionsG: event.data.total_game_emissions_g,
        maxCo2LevelG: event.data.max_co2_level_g,
        // A new round clears everything the last one's aftermath put on screen
        // — except what the vote decided. `phases._tally_if_complete` sends
        // `vote.result` and `round.started` back to back, so clearing the
        // outcome here would wipe it about a frame after it arrived and no
        // screen could ever have shown it. It stays until the next round is
        // over, and the round header says what the class voted in (Z-11).
        phase: "none",
        voteOptions: [],
        votes: null,
        stalemate: null,
        simulation: null,
      };

    case "round.completed":
      return {
        ...seen,
        totalEmissionsG: event.data.total_game_emissions_g,
        maxCo2LevelG: event.data.max_co2_level_g,
        voteOptions: event.data.map_versions,
        simulation: null,
        // The last vote has been on screen for a whole round by now; this round
        // gets its own aftermath.
        voteOutcome: null,
        // The backend moves the round into the stats phase as it completes.
        phase: "stats",
        lastRound: {
          roundNumber: event.data.round_number,
          emissionsG: event.data.round_emissions_g,
          costEur: event.data.round_cost_eur,
          totalEmissionsG: event.data.total_game_emissions_g,
          playerStats: event.data.player_stats,
          simulationUsed: event.data.simulation_used,
        },
      };

    case "simulation.progress":
      return {
        ...seen,
        simulation: {
          roundNumber: event.data.round_number,
          status: event.data.status,
          percent: event.data.progress_percent ?? 0,
          error: event.data.error ?? null,
        },
      };

    // ── between rounds ──────────────────────────────────────────────────────

    case "stats.all_acked":
      // "next_round" is followed by round.started, which resets the phase
      // anyway; setting it here keeps the screen from flashing the stats again
      // in between.
      return {
        ...seen,
        phase: event.data.next_phase === "discussion" ? "discussion" : "none",
        voteOptions: event.data.map_versions ?? state.voteOptions,
      };

    case "vote.opened":
      return {
        ...seen,
        phase: "voting",
        voteOptions: event.data.versions,
        // A reopened vote after a tie starts the count again.
        votes: null,
        stalemate: null,
      };

    case "vote.recorded":
      return {
        ...seen,
        votes: {
          cast: event.data.votes_cast,
          needed: event.data.votes_needed,
        },
      };

    case "vote.result":
      return {
        ...seen,
        // The winner is the game's new active map version, and this is the only
        // event that says so. A tie left as it is sends `null` and changes
        // nothing — so only a real winner may overwrite it.
        activeMapVersionId:
          event.data.winning_version_id ?? state.activeMapVersionId,
        voteOutcome: {
          stalemate: false,
          winningVersionId: event.data.winning_version_id,
          winningVersionName: event.data.winning_version_name,
          forced: event.data.forced ?? false,
        },
      };

    case "vote.stalemate":
      return {
        ...seen,
        phase: "stalemate",
        stalemate: null,
        voteOutcome: {
          stalemate: true,
          winningVersionId: null,
          winningVersionName: event.data.winning_version_name,
          forced: false,
        },
      };

    case "stalemate.progress":
      return {
        ...seen,
        stalemate: { cast: event.data.cast, needed: event.data.needed },
      };

    default:
      return assertNever(event);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Selectors. One place per question, so no screen re-derives them differently.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Seats that count — `PlayerQuerySet.playing()` on the frontend side. The
 * host's own row is never one of them: the round does not wait for it and it
 * does not count against `max_players`. A seat played at the host machine does
 * count, which is the whole point of 1.6.
 */
export function playingSeats(state: GameState): RosterSeat[] {
  return state.seats.filter((seat) => !seat.is_host);
}

export function hostSeat(state: GameState): RosterSeat | null {
  return state.seats.find((seat) => seat.is_host) ?? null;
}

export function seatById(
  state: GameState,
  playerId: string | null,
): RosterSeat | null {
  if (!playerId) return null;
  return state.seats.find((seat) => seat.player_id === playerId) ?? null;
}

/** Seats played at the host machine — the carousel F4 steps through. */
export function hostControlledSeats(state: GameState): RosterSeat[] {
  return playingSeats(state).filter((seat) => seat.controlled_by_host);
}

/** How many have submitted this round, out of how many are waited for. */
export function moveProgress(state: GameState): { done: number; total: number } {
  const players = playingSeats(state);
  return {
    done: players.filter((seat) => seat.status === "waiting").length,
    total: players.length,
  };
}

/** Which screen the game is on. The router does not decide this, the game does. */
export type GameScreen =
  | "lobby"
  | "playing"
  | "between-rounds"
  | "ended"
  | "revoked";

export function currentScreen(state: GameState): GameScreen {
  if (state.revoked) return "revoked";
  if (state.endedAt) return "ended";
  // A between-round phase and a round number are both proof that the game is
  // running, and they are checked before the lobby rather than after it: a
  // client that joins mid-game, or one that missed `game.started` while its
  // socket was down, would otherwise be shown a lobby for a game in progress.
  if (state.phase !== "none") return "between-rounds";
  if (state.isActive || state.startedAt || state.currentRound > 0) {
    return "playing";
  }
  return "lobby";
}

/**
 * The CO₂ budget as a fraction. The bar turns from primary to accent at
 * `BUDGET_ATTENTION_AT`; there is no third band, because "warning" versus
 * "danger" is a distinction the screen cannot act on.
 */
export function budgetUsed(state: GameState): number {
  if (state.maxCo2LevelG <= 0) return 0;
  return state.totalEmissionsG / state.maxCo2LevelG;
}
