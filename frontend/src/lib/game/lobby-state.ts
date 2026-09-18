/**
 * The lobby as one state, built the way every game screen will be built.
 *
 * The shape this establishes (Roadmap.md 2.2):
 *
 *     REST snapshot ──┐
 *                     ├──> lobbyReducer ──> LobbyState
 *     socket events ──┘
 *
 * REST is read exactly once, to have something to draw before the socket is up.
 * After that the socket owns every field. There is no polling, and nothing
 * re-reads the snapshot in response to an event — that combination is what the
 * old screens did (a 2 s `refetchInterval` plus a `refetchRef` fired from WS
 * callbacks), and it is the root of the state bugs, not a detail of them.
 *
 * Pure on purpose: no React import, so `tests/lib/game/lobby-state.test.ts` can
 * feed it a snapshot and a sequence of events and assert the result.
 */

import type {
  GameEvent,
  RevokeReason,
  RosterSeat,
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

export type LobbyState = {
  gameId: string;
  gameName: string;
  maxPlayers: number;
  agentPerPlayer: number;
  maxRounds: number;
  maxCo2LevelKg: number;
  chatEnabled: boolean;
  isActive: boolean;
  startedAt: string | null;
  endedAt: string | null;
  pausedAt: string | null;
  /** Every seat still in the game, host row included, in join order. */
  seats: RosterSeat[];
  /**
   * Whether a `roster.update` has arrived. Once it has, the REST snapshot must
   * never touch `seats` again — see `lobbyReducer`.
   */
  hasLiveRoster: boolean;
  /**
   * Set when this device's seat was revoked. Once set the screen stops showing
   * a lobby — the seat is not ours any more, and the socket is already closed.
   */
  revoked: RevokeReason | null;
};

export type LobbyAction =
  | { kind: "snapshot"; snapshot: LobbySnapshot }
  | { kind: "event"; event: GameEvent };

/**
 * The REST snapshot knows who is in the game but not who is connected — that
 * lives in the cache and only `roster.update` carries it. So a seat starts
 * offline and the first roster, which the backend sends as soon as this socket
 * connects, fills it in. Showing "nicht verbunden" for a moment is honest;
 * claiming everyone is online until proven otherwise is what the old
 * Redis-only roster did, and it never recovered from a restart.
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

export function initialLobbyState(gameId: string): LobbyState {
  return {
    gameId,
    gameName: "",
    maxPlayers: 0,
    agentPerPlayer: 0,
    maxRounds: 0,
    maxCo2LevelKg: 0,
    chatEnabled: false,
    isActive: false,
    startedAt: null,
    endedAt: null,
    pausedAt: null,
    seats: [],
    hasLiveRoster: false,
    revoked: null,
  };
}

export function lobbyStateFromSnapshot(snapshot: LobbySnapshot): LobbyState {
  return {
    gameId: snapshot.game_id,
    gameName: snapshot.game_name,
    maxPlayers: snapshot.max_players,
    agentPerPlayer: snapshot.agent_per_player,
    maxRounds: snapshot.max_rounds,
    maxCo2LevelKg: snapshot.max_co2_level_kg,
    chatEnabled: snapshot.chat_enabled,
    isActive: snapshot.is_active,
    startedAt: snapshot.started_at,
    endedAt: snapshot.ended_at,
    pausedAt: snapshot.paused_at,
    seats: snapshot.players.map(seatFromSnapshot),
    hasLiveRoster: false,
    revoked: null,
  };
}

/**
 * Apply one socket event to the lobby.
 *
 * Unhandled events fall through to `default` and return the state unchanged.
 * That is deliberate here and not a hole: the lobby genuinely has no opinion on
 * `vote.recorded`. F2's game reducer is the one that has to be exhaustive,
 * because by then every event means something to somebody.
 *
 * `player.joined` and `player.left` are not used to edit the seat list. The
 * backend sends a full `roster.update` right after each of them (both call
 * `schedule_broadcast`), and one authority for the list beats two that can
 * disagree — the same reason there is no polling. They stay in the union so the
 * screens can say *what* happened; the list itself comes from the roster.
 */
export function lobbyReducer(
  state: LobbyState,
  action: LobbyAction,
): LobbyState {
  if (action.kind === "snapshot") {
    // A snapshot never clobbers a revocation: it is read once, at mount, and
    // the only way it could arrive late is a race we would otherwise resolve
    // in favour of the stale answer.
    if (state.revoked) return state;

    const next = lobbyStateFromSnapshot(action.snapshot);

    // The same race, and the one that actually bit: the socket connects, the
    // backend answers with a full roster, and *then* the REST snapshot
    // resolves. The snapshot cannot know who is connected — it builds every
    // seat offline — so applying it would blank out presence that is already
    // correct, and the lobby would sit there showing "nicht verbunden" for
    // people who are plainly online. Whoever is newer wins, and after the first
    // roster.update that is always the socket.
    if (state.hasLiveRoster) {
      return { ...next, seats: state.seats, hasLiveRoster: true };
    }
    return next;
  }

  const event = action.event;
  switch (event.type) {
    case "roster.update":
      return { ...state, seats: event.players, hasLiveRoster: true };

    case "game.state": {
      const snapshot = event.data;
      return {
        ...state,
        isActive: snapshot.isActive,
        startedAt: snapshot.startedAt,
        endedAt: snapshot.endedAt,
        pausedAt: snapshot.pausedAt,
        maxRounds: snapshot.maxRounds,
      };
    }

    case "game.started":
      return {
        ...state,
        isActive: true,
        startedAt: event.data.started_at,
        maxRounds: event.data.max_rounds,
      };

    case "game.ended":
      return { ...state, isActive: false, endedAt: event.data.ended_at };

    case "game.paused":
      return { ...state, pausedAt: event.data.paused_at };

    case "game.resumed":
      return { ...state, pausedAt: null };

    case "player.revoked":
      // `reason` can be "" if the backend ever sends one without it; treat that
      // as "removed" rather than as "not revoked", because the socket is
      // closing either way and a lobby that keeps rendering is the worse bug.
      return { ...state, revoked: event.data.reason || "removed" };

    default:
      return state;
  }
}

/** Seats that count against `max_players` — the host's own row is not one. */
export function playingSeats(state: LobbyState): RosterSeat[] {
  return state.seats.filter((seat) => !seat.is_host);
}

/** The host's own row, if the game has one. */
export function hostSeat(state: LobbyState): RosterSeat | null {
  return state.seats.find((seat) => seat.is_host) ?? null;
}
