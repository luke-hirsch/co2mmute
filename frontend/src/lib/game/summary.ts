/**
 * The end screen's arithmetic. No React, no formatting — just the orders and
 * the one derived series.
 *
 * The screen shows the same players three times, ordered by CO₂, by cost and by
 * time, and nobody is numbered or crowned: the research group's position is
 * that there is no winner, or that who won is exactly what the class argues
 * about afterwards (Lukas, 2026-09-18). The order is what carries the finding,
 * and the finding is that the three orders disagree — whoever emitted least
 * walked and took an hour longer, whoever was fastest drove.
 *
 * Which is why the sort lives here with a test on it rather than inline in the
 * component: three lists that quietly came out in the same order would look
 * entirely normal and would have lost the only argument the screen makes.
 */

import type { SummaryPlayer, SummaryRound } from "@/lib/queries/summary";

/** The three things a commute costs. Less is better in all three. */
export type SummaryMetric = "co2" | "cost" | "time";

export const summaryMetrics: readonly SummaryMetric[] = ["co2", "cost", "time"];

export function playerValue(player: SummaryPlayer, metric: SummaryMetric): number {
  switch (metric) {
    case "co2":
      return player.total_co2_kg;
    case "cost":
      return player.total_cost_eur;
    case "time":
      return player.total_time_min;
  }
}

export function roundValue(round: SummaryRound, metric: SummaryMetric): number {
  switch (metric) {
    case "co2":
      return round.co2_kg;
    case "cost":
      return round.cost_eur;
    case "time":
      return round.time_min;
  }
}

/**
 * Lowest first. Copies rather than sorting in place — the three lists render
 * off one query result, and an in-place sort would reorder the other two behind
 * their backs.
 *
 * `sort` is stable in every engine this runs in, so equal players keep the
 * order the backend sent, which is join order. Nothing else would be any more
 * meaningful, and shuffling them would suggest a difference that is not there.
 */
export function orderBy(
  players: readonly SummaryPlayer[],
  metric: SummaryMetric,
): SummaryPlayer[] {
  return [...players].sort((a, b) => playerValue(a, metric) - playerValue(b, metric));
}

/** One round of the whole class. */
export type ArcStop = {
  roundNumber: number;
  co2Kg: number;
};

/**
 * What the class emitted, round by round — the line that answers "did changing
 * the map do anything?".
 *
 * **Derived, because the payload has no per-round class total**: it carries
 * per-round figures per player and one grand total for the game, nothing in
 * between. So this sums the players in the list.
 *
 * Which means it can come out *under* `total_co2_kg`, and that is not a bug:
 * `players` comes from `playing()`, so somebody who left mid-game is missing
 * from it while their emissions stay in the game total. The headline figure
 * stays the authoritative one — never rebuild it by summing these stops.
 *
 * CO₂ only. Cost and time are the players' to compare; the budget is the
 * class's, and it is the one number the whole game is played against.
 */
export function classArc(players: readonly SummaryPlayer[]): ArcStop[] {
  const byRound = new Map<number, number>();

  for (const player of players) {
    for (const round of player.rounds) {
      // Keyed on the round number, never the array position: a player who
      // joined in round 2 has a short `rounds` array, and indexing would add
      // their first round onto everybody else's and shift the line left.
      const total = byRound.get(round.round_number) ?? 0;
      byRound.set(round.round_number, total + round.co2_kg);
    }
  }

  return [...byRound.entries()]
    .map(([roundNumber, co2Kg]) => ({ roundNumber, co2Kg }))
    .sort((a, b) => a.roundNumber - b.roundNumber);
}
