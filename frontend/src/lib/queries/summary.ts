/**
 * `GET api/game/<game_id>/summary/` — everything the game did, per player, per
 * round. `game/views_rest.py:GameSummaryView`.
 *
 * The one request the end screen makes, and the only one in the SPA that reads
 * across all the rounds of a game: the reducer knows the last round and nothing
 * before it, because that is all the socket ever sent.
 *
 * Read once and never invalidated. The game is over — this is the single screen
 * where the socket genuinely has nothing left to say, and a poll here would be
 * the 2.2 bug turning up on the last screen of the game.
 *
 * `HasGameAccess` lets both halves in: the host through their session, a player
 * through the game cookie. So one hook serves both screens.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { GameEndReason } from "@/lib/game/events";
import type { TransportMode } from "@/lib/de";

/**
 * One round of one player's game, on both scales.
 *
 * The `*_per_person` fields are the same round divided back down to one
 * commuter making one commute: by `agent_count` and by `people_per_agent`.
 * Divided on the server, because a screen dividing a figure that has already
 * been rounded for display by a thousand is dividing noise.
 */
export type SummaryRound = {
  round_number: number;
  /** Class scale: this seat's Fahrgäste x people_per_agent commuters. */
  co2_kg: number;
  cost_eur: number;
  /**
   * A sum of agent means, and therefore **not a quantity anybody has** — two
   * Fahrgäste commuting 30 min each report 60. Kept in the payload because it
   * was what the screen read before 2.4; read `time_min_per_agent` instead.
   */
  time_min: number;
  /** How many agent-trips the figures above are made of. */
  agent_count: number;
  /**
   * **Grams, not kilos**: a bike ride is 0 and a walk is 0, and a kg column
   * would print both as `0,00` beside a car's `1,33`.
   */
  co2_g_per_person: number;
  cost_eur_per_person: number;
  /** The mean over this round's agent-trips. Time has no second scale. */
  time_min_per_agent: number;
  /**
   * What the commuter actually handed over: one Ticket per PT trip, fuel and
   * brakes for a driver. `cost_eur_per_person` is what the trip costs
   * altogether, so the difference is the subsidy on one side and Abschreibung
   * on the other — *was du zahlst* beside *was es kostet*.
   */
  paid_eur_per_person: number;
};

/** One option as it stood on the ballot. */
export type SummaryVoteOption = {
  version_id: number;
  version_name: string;
};

/**
 * One option and its votes. `version_id` is null for the vote to leave the map
 * as it is, and its `version_name` is then the backend's English `LEAVE_AS_IS`
 * sentinel — never show it. `lib/game/vote-history.ts` strips it.
 */
export type SummaryVoteCount = {
  version_id: number | null;
  version_name: string;
  count: number;
};

/**
 * How the vote after a round came out, recorded when it happened and never
 * recomputed (`GameRound.vote_result`).
 *
 * The tally is derivable from the surviving `MapVersionVote` rows, and
 * deliberately not derived: `_tally_if_complete` counts the players still in the
 * game, so a re-tally at the summary counts a smaller room than voted and can
 * name a different winner than the class saw on the screen.
 */
export type SummaryVote = {
  options: SummaryVoteOption[];
  vote_counts: SummaryVoteCount[];
  /** Null when the map stayed as it was — a tie, or the host ending one. */
  winning_version_id: number | null;
  winning_version_name: string;
  tie: boolean;
  stalemate_count: number;
  /** The host cut a tie short rather than letting it resolve. */
  forced: boolean;
};

/**
 * One round of the whole class — the figure the budget is spent out of, which
 * is not the sum of the players below it.
 *
 * `co2_kg = the players' rows + the society emissions of the lines nobody rode`.
 * A PT line is on the network whether or not anybody boards, so its timetable
 * emits either way; the ridden part is already inside the riders' rows and only
 * the remainder is added on top. `unridden_co2_kg` is that remainder, and it is
 * what lets a screen show the gap instead of appearing not to add up.
 */
export type SummaryRoundTotals = {
  round_number: number;
  co2_kg: number;
  cost_eur: number;
  /** The whole timetable's own figures, ridden and unridden together. */
  network_co2_kg: number;
  network_cost_eur: number;
  /** The slice of the round that belongs to no player's row. */
  unridden_co2_kg: number;
  unridden_cost_eur: number;
  agent_count: number;
  co2_g_per_person: number;
  cost_eur_per_person: number;
  /** False when the fallback figures were used instead of the simulation. */
  simulation_used: boolean;
  /**
   * The vote held **after** this round, so the next row of numbers has a reason
   * above it. Null for a round that never reached a ballot: a single-version
   * map, `map_updates` off, the last round of the game, and every round played
   * before the field existed.
   */
  vote: SummaryVote | null;
};

export type SummaryPlayer = {
  player_id: string;
  /**
   * Real until anonymisation runs, 24 h after the end of the game (1.3), which
   * is deliberate — the debrief happens in the lesson and the names go after
   * it. On the screen only: never into a log, a toast or an error string.
   */
  name: string;
  /**
   * They left before the end, and they are **in this list** — with their rows
   * intact, because the rounds they played happened. Which is why nothing may
   * be ranked on the three totals below: they are sums over agent-trips, so a
   * leaver comes out fastest and cheapest for having played less.
   */
  left: boolean;
  /** Class scale, summed over every agent-trip of every round they played. */
  total_co2_kg: number;
  total_cost_eur: number;
  /** A sum of agent means. Not a quantity anybody has — see `SummaryRound`. */
  total_time_min: number;
  /** What the three totals are a sum of. */
  total_agent_trips: number;
  /** One commuter, one commute, over the whole game. Rank on these. */
  co2_g_per_person: number;
  cost_eur_per_person: number;
  time_min_per_agent: number;
  paid_eur_per_person: number;
  /** Every mode this player used at least once, over the whole game. */
  modes_used: TransportMode[];
  /**
   * Only the rounds this player actually moved in, so it can be shorter than
   * the game — somebody who joined in round 2 has no round 1 here. Always key
   * on `round_number`, never on the position in the array.
   */
  rounds: SummaryRound[];
};

export type GameSummary = {
  game_id: string;
  game_name: string;
  /**
   * Recomputed by the view from the totals, so an idle-ended game reports
   * `max_rounds` here exactly as it does everywhere else (E-05, open).
   *
   * It is still worth having: `game.state` carries `ended_at` and **no**
   * reason, so after a reload of the end screen the reducer has none and this
   * is the only source left. Prefer the reducer's when it is there — that one
   * came from the live `game.ended` — and fall back to this.
   */
  end_reason: GameEndReason | null;
  rounds_played: number;
  max_rounds: number;
  /**
   * **Kilos here, grams on the socket.** See lib/co2.ts: convert at the edge,
   * and never do arithmetic on a number whose unit is not in its name.
   */
  total_co2_kg: number;
  max_co2_kg: number;
  /**
   * One Fahrgast stands for this many real people, and every kg and euro on the
   * class scale is already multiplied by it. Derived from the class size
   * (`GameMap.district_commuters / (seats x Fahrgäste)`), so it differs from
   * game to game, and it reaches the SPA on no other endpoint the host can call.
   */
  people_per_agent: number;
  /** The class's own figure per round — never summed out of `players`. */
  rounds: SummaryRoundTotals[];
  /**
   * `without_host_rows()` — everybody but the host's own seat, **including the
   * people who left**, flagged. A seat played at the host machine is a player
   * like any other.
   */
  players: SummaryPlayer[];
};

export const summaryKeys = {
  summary: (gameId: string) => ["game", gameId, "summary"] as const,
};

export function fetchSummary(gameId: string): Promise<GameSummary> {
  return apiFetch<GameSummary>(`/api/game/${gameId}/summary/`);
}

export function useGameSummary(gameId: string, enabled: boolean) {
  return useQuery({
    queryKey: summaryKeys.summary(gameId),
    queryFn: () => fetchSummary(gameId),
    enabled: enabled && gameId.length > 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
