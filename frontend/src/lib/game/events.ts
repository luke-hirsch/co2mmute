/**
 * Everything `ws/game/<game_id>/` can send, as one discriminated union.
 *
 * This file is the contract, not a convenience. The old `types/wsTypes.ts` had
 * grown apart from the backend without anything noticing: it still declared
 * `lobby.roster`, which no consumer sends any more, and it was missing every
 * event phase 1 added — `game.paused`, `game.resumed`, `player.revoked`,
 * `player.left`, `player.taken_over`, `player.handed_over`,
 * `simulation.progress`. A socket that silently drops an event it was never
 * told about is exactly how "daten im frontend nicht persistent" happens.
 *
 * So: every event the backend can send appears here, even the ones no screen
 * reads yet. The reducers switch on `type` and TypeScript checks the switch is
 * exhaustive, which turns "the backend grew an event" into a build error at the
 * one place that has to decide what to do with it.
 *
 * Where the shapes come from, so the next person can check them:
 * - `game/signals.py`   — player.joined, game.started, game.ended,
 *                         round.completed, simulation.progress
 * - `game/phases.py`    — round.started, stats.all_acked, vote.*, stalemate.*
 * - `game/roster.py`    — roster.update, player.revoked
 * - `game/seats.py`     — player.left, player.taken_over, player.handed_over
 * - `game/pause.py`     — game.paused, game.resumed
 * - `game/consumers.py` — game.state (the snapshot sent on connect), pong, error
 *
 * Note the envelope is not uniform: most events arrive as `{type, game_id,
 * data}`, but `roster.update` carries `players` at the top level and `error`
 * carries `message`. That is the backend's shape; it is described here rather
 * than smoothed over, because smoothing it over is what hides a drift.
 */

import type { SeatStatus, TransportMode } from "@/lib/de";

/** A seat as `roster.update` carries it. `game/roster.py:build`. */
export type RosterSeat = {
  player_id: string;
  name: string;
  /** The host's own row. The player list filters it out; the desk does not. */
  is_host: boolean;
  /** Since 1.6 this means "played at the host machine", not "is the host". */
  controlled_by_host: boolean;
  online: boolean;
  status: SeatStatus;
};

/** One option on the ballot. `game/phases.py:_build_version_dict`. */
export type VoteOption = {
  id: number;
  name: string;
  poll_text: string;
  is_rollback: boolean;
  change_img_url: string | null;
};

/** Per-player figures in `round.completed`. `game/signals.py`. */
export type RoundPlayerStats = {
  player_id: string;
  player_name: string;
  action: string;
  emissions_g: number;
  cost_eur: number;
  time_min: number;
  /** Only present when the simulation ran; the legacy fallback omits it. */
  agents?: { mode: TransportMode; [key: string]: unknown }[];
};

/**
 * The snapshot the consumer sends right after `accept()`, and the one place
 * the payload is camelCase — it is built in `GameConsumer._get_current_game_state`
 * rather than by a serializer.
 */
export type GameStateSnapshot = {
  isActive: boolean;
  currentRound: number;
  totalEmissionsG: number;
  maxCo2LevelG: number;
  maxRounds: number;
  startedAt: string | null;
  endedAt: string | null;
  pausedAt: string | null;
  betweenRoundPhase: BetweenRoundPhase;
  activeMapVersionId: number | null;
  hasMapVersions: boolean;
  mapVersions: VoteOption[];
};

/** `GameRound.BetweenRoundPhase`. */
export type BetweenRoundPhase =
  | "none"
  | "stats"
  | "discussion"
  | "voting"
  | "stalemate";

/** Why a game ended. `game/signals.py`. */
export type GameEndReason = "co2_limit" | "max_rounds";

/**
 * Why this device lost its seat. `game/roster.py:revoke`.
 * - `removed` — the host removed the player
 * - `left`    — the player left
 * - `taken_over` — the host plays this seat now (1.6)
 * - `handed_over` — another device redeemed a code for it (1.7)
 */
export type RevokeReason = "removed" | "left" | "taken_over" | "handed_over";

type Envelope<T extends string, D> = {
  type: T;
  game_id: string;
  data: D;
};

export type GameEvent =
  // ── connection ───────────────────────────────────────────────────────────
  | Envelope<"game.state", GameStateSnapshot>
  | { type: "pong" }
  | { type: "error"; message: string }

  // ── roster and seats ─────────────────────────────────────────────────────
  // The odd one out: `players` sits at the top level, not under `data`.
  | { type: "roster.update"; game_id: string; players: RosterSeat[] }
  | Envelope<
      "player.joined",
      {
        player_id: string;
        player_name: string;
        controlled_by_host: boolean;
        agent_assignments: unknown;
      }
    >
  | Envelope<
      "player.left",
      { player_id: string; player_name: string; was_kicked: boolean }
    >
  | Envelope<"player.revoked", { reason: RevokeReason | "" }>
  | Envelope<
      "player.taken_over",
      { old_player_id: string; new_player_id: string }
    >
  | Envelope<
      "player.handed_over",
      { old_player_id: string; new_player_id: string }
    >

  // ── the game itself ──────────────────────────────────────────────────────
  | Envelope<
      "game.started",
      {
        game_name: string;
        max_rounds: number;
        max_co2_level: number;
        current_round: number;
        started_at: string | null;
      }
    >
  | Envelope<
      "game.ended",
      {
        reason: GameEndReason;
        final_round: number;
        total_emissions_g: number;
        max_co2_level_g: number;
        ended_at: string | null;
      }
    >
  | Envelope<"game.paused", { paused_at: string }>
  | Envelope<"game.resumed", Record<string, never>>

  // ── rounds ───────────────────────────────────────────────────────────────
  | Envelope<
      "round.started",
      {
        round_number: number;
        max_rounds: number;
        total_game_emissions_g: number;
        max_co2_level_g: number;
      }
    >
  | Envelope<
      "round.completed",
      {
        round_number: number;
        round_emissions_g: number;
        round_cost_eur: number;
        total_game_emissions_g: number;
        max_co2_level_g: number;
        player_stats: RoundPlayerStats[];
        simulation_used: boolean;
        has_map_versions: boolean;
        map_versions: VoteOption[];
      }
    >
  | Envelope<
      "simulation.progress",
      {
        round_number: number;
        status: "starting" | "running" | "failed";
        tick?: number;
        total_ticks?: number;
        progress_percent?: number;
        error?: string;
      }
    >

  // ── between rounds ───────────────────────────────────────────────────────
  | Envelope<
      "stats.all_acked",
      { next_phase: "discussion" | "next_round"; map_versions?: VoteOption[] }
    >
  | Envelope<"vote.opened", { versions: VoteOption[] }>
  | Envelope<
      "vote.recorded",
      { player_id: string; votes_cast: number; votes_needed: number }
    >
  | Envelope<
      "vote.result",
      {
        stalemate: false;
        stalemate_count?: number;
        winning_version_id: number | null;
        winning_version_name: string;
        vote_counts: unknown[];
        forced?: boolean;
      }
    >
  | Envelope<
      "vote.stalemate",
      {
        stalemate: true;
        stalemate_count: number;
        vote_counts: unknown[];
        winning_version_id: null;
        winning_version_name: string;
      }
    >
  | Envelope<"stalemate.progress", { cast: number; needed: number }>;

export type GameEventType = GameEvent["type"];

/**
 * Narrow an unknown socket payload to a `GameEvent`.
 *
 * Deliberately shallow: it checks that there is a string `type` and nothing
 * more. Validating every field would mean a schema library and a second copy of
 * the contract above, and the failure it would catch — the backend changing a
 * payload — shows up just as fast in the reducer. What this does catch is the
 * real case: a non-object frame, or a frame with no type at all, reaching a
 * switch that then falls through to `default` for the wrong reason.
 */
export function asGameEvent(payload: unknown): GameEvent | null {
  if (!payload || typeof payload !== "object") return null;
  const type = (payload as { type?: unknown }).type;
  return typeof type === "string" ? (payload as GameEvent) : null;
}
