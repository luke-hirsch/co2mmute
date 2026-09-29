/**
 * The end screen's arithmetic. No React, no formatting — just the orders and
 * the class's own series.
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
 *
 * **Every figure has two scales and the reader picks one** (`lib/game/scale.ts`).
 * The order follows whatever is on screen, so both are honest — but the default
 * is the per-commute one, because the three totals are sums over agent-trips and
 * the list now contains the people who left. Ranked on the sums, whoever played
 * least is cleanest, cheapest *and* fastest.
 */

import { kgToGrams } from "@/lib/co2";
import type { Scale } from "@/lib/game/scale";
import type {
  SummaryPlayer,
  SummaryRound,
  SummaryRoundTotals,
} from "@/lib/queries/summary";

/** The three things a commute costs. Less is better in all three. */
export type SummaryMetric = "co2" | "cost" | "time";

export const summaryMetrics: readonly SummaryMetric[] = ["co2", "cost", "time"];

/**
 * CO₂ in **grams** on both scales, cost in euro, time in minutes.
 *
 * Grams rather than the payload's mixed units, because the switch compares the
 * two scales against each other and `lib/co2.ts` is the only place allowed to
 * know that the summary sends kilos where the socket sends grams.
 *
 * **Time has one scale.** `total_time_min` is a sum of agent means — two
 * Gruppen commuting half an hour each report an hour — so there is no class
 * figure to switch to, only a mean per trip. Reading it on both branches is
 * deliberate, not an oversight: the alternative is a column that goes blank when
 * the reader flips the switch.
 */
export function playerValue(
  player: SummaryPlayer,
  metric: SummaryMetric,
  scale: Scale,
): number {
  switch (metric) {
    case "co2":
      return scale === "class"
        ? kgToGrams(player.total_co2_kg)
        : player.co2_g_per_person;
    case "cost":
      return scale === "class" ? player.total_cost_eur : player.cost_eur_per_person;
    case "time":
      return player.time_min_per_agent;
  }
}

export function roundValue(
  round: SummaryRound,
  metric: SummaryMetric,
  scale: Scale,
): number {
  switch (metric) {
    case "co2":
      return scale === "class" ? kgToGrams(round.co2_kg) : round.co2_g_per_person;
    case "cost":
      return scale === "class" ? round.cost_eur : round.cost_eur_per_person;
    case "time":
      return round.time_min_per_agent;
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
  scale: Scale,
): SummaryPlayer[] {
  return [...players].sort(
    (a, b) => playerValue(a, metric, scale) - playerValue(b, metric, scale),
  );
}

/** One round of the whole class. */
export type ArcStop = {
  roundNumber: number;
  co2Kg: number;
  /**
   * The slice of it that is timetable nobody rode. A PT line emits because it
   * runs, so a round total is larger than the sum of its rows by exactly this.
   */
  unriddenCo2Kg: number;
  /** False when the fallback figures were used instead of the simulation. */
  simulationUsed: boolean;
};

/**
 * What the class emitted, round by round — the line that answers "did changing
 * the map do anything?".
 *
 * **Read, not derived.** It used to be summed out of the listed players, which
 * undershot every round by whoever had left the game and made the chart disagree
 * with the headline total above it. The payload carries the class's own figure
 * per round now, which is the same number the CO₂ budget is spent out of.
 *
 * CO₂ only. Cost and time are the players' to compare; the budget is the
 * class's, and it is the one number the whole game is played against.
 */
export function classArc(rounds: readonly SummaryRoundTotals[]): ArcStop[] {
  return [...rounds]
    .sort((a, b) => a.round_number - b.round_number)
    .map((round) => ({
      roundNumber: round.round_number,
      co2Kg: round.co2_kg,
      unriddenCo2Kg: round.unridden_co2_kg,
      simulationUsed: round.simulation_used,
    }));
}
