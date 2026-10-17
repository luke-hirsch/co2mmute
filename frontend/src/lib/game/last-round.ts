/**
 * The one line under a Gruppe on the round screen: what it lived last round.
 *
 * Read off `player_stats[].agents` of `round.completed`, matched by the seat and
 * the Gruppe's id — both are in the payload already. Null in round 1 and
 * wherever the simulation did not run (the fallback rows carry no per-Gruppe
 * figures), so nothing is preselected or promised. A game that hides its CO₂
 * gets the line without the kg.
 */

import { de } from "@/lib/de";
import type { RoundResult } from "@/lib/game/game-state";

export function lastRoundLine(
  round: RoundResult | null,
  seatId: string | null,
  agentId: number,
  hideCo2 = false,
): string | null {
  if (!round || !seatId) return null;
  const stats = round.playerStats.find((p) => p.player_id === seatId);
  const agent = stats?.agents?.find((a) => a.agent_id === agentId);
  if (!agent) return null;
  return de.round.lastRoundLine(
    agent.mode,
    agent.trip_time_min,
    hideCo2 ? null : agent.co2_g_per_person / 1000,
  );
}
