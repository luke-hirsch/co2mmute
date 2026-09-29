import { describe, expect, it } from "vitest";

import { classArc, orderBy, playerValue, roundValue } from "@/lib/game/summary";
import type {
  SummaryPlayer,
  SummaryRound,
  SummaryRoundTotals,
} from "@/lib/queries/summary";

/**
 * The end-of-game summary's arithmetic, without React.
 *
 * Three things are worth pinning.
 *
 * **The order**, because the whole screen is the same three players in three
 * different orders and the finding only exists if those orders genuinely differ
 * — a sort that quietly fell back to one field would show three identical lists
 * and nobody would notice it was a bug.
 *
 * **That the order is per-commute by default**, because the three totals are
 * sums over agent-trips and the list now contains the people who left. Ranked on
 * the sums, whoever played least is fastest *and* cheapest. The payload carries
 * both scales, the reader switches between them, and time never switches at all:
 * a sum of travel times is not a quantity anybody has.
 *
 * **And the arc**, because it used to be derived — summed out of the listed
 * players, which undershot by everybody who had left the game. The payload
 * carries the class's own per-round figure now, so the arc reads it.
 */

function player(
  overrides: Partial<SummaryPlayer> & { player_id: string },
): SummaryPlayer {
  return {
    name: "Ben",
    left: false,
    total_co2_kg: 0,
    total_cost_eur: 0,
    total_time_min: 0,
    total_agent_trips: 0,
    co2_g_per_person: 0,
    cost_eur_per_person: 0,
    time_min_per_agent: 0,
    paid_eur_per_person: 0,
    modes_used: [],
    rounds: [],
    ...overrides,
  };
}

function round(overrides: Partial<SummaryRound>): SummaryRound {
  return {
    round_number: 1,
    co2_kg: 0,
    cost_eur: 0,
    time_min: 0,
    agent_count: 1,
    co2_g_per_person: 0,
    cost_eur_per_person: 0,
    time_min_per_agent: 0,
    paid_eur_per_person: 0,
    ...overrides,
  };
}

function classRound(overrides: Partial<SummaryRoundTotals>): SummaryRoundTotals {
  return {
    round_number: 1,
    co2_kg: 0,
    cost_eur: 0,
    network_co2_kg: 0,
    network_cost_eur: 0,
    unridden_co2_kg: 0,
    unridden_cost_eur: 0,
    agent_count: 4,
    co2_g_per_person: 0,
    cost_eur_per_person: 0,
    simulation_used: true,
    vote: null,
    ...overrides,
  };
}

/**
 * Two Gruppen each, one round, 100 people per Gruppe — so a class-scale
 * kilo is 200 per-person grams and the two scales are genuinely different
 * numbers rather than the same one twice.
 */

/** Walks: least CO2, cheapest, slowest by a long way. */
const mira = player({
  player_id: "P-1",
  name: "Mira",
  total_co2_kg: 36,
  total_cost_eur: 4.2,
  total_time_min: 96,
  total_agent_trips: 2,
  co2_g_per_person: 180,
  cost_eur_per_person: 0.021,
  time_min_per_agent: 48,
  paid_eur_per_person: 0,
  rounds: [
    round({ round_number: 1, co2_kg: 36, cost_eur: 4.2, co2_g_per_person: 180 }),
  ],
});

/** Public transport: in the middle on everything but the cheapest. */
const jonas = player({
  player_id: "P-2",
  name: "Jonas",
  total_co2_kg: 42,
  total_cost_eur: 3.1,
  total_time_min: 142,
  total_agent_trips: 2,
  co2_g_per_person: 210,
  cost_eur_per_person: 0.0155,
  time_min_per_agent: 71,
  paid_eur_per_person: 1.3,
});

/** Drives: fastest, dirtiest, dearest. The trade-off in one row. */
const ada = player({
  player_id: "P-3",
  name: "Ada",
  total_co2_kg: 48,
  total_cost_eur: 6.8,
  total_time_min: 61,
  total_agent_trips: 2,
  co2_g_per_person: 240,
  cost_eur_per_person: 0.034,
  time_min_per_agent: 30.5,
  paid_eur_per_person: 0.017,
});

const players = [mira, jonas, ada];

function names(ordered: readonly SummaryPlayer[]): string[] {
  return ordered.map((p) => p.name);
}

describe("orderBy", () => {
  it("puts the lowest first for each of the three metrics", () => {
    // Ascending is better for all three: less CO2, less money, less time.
    expect(names(orderBy(players, "co2", "person"))).toEqual([
      "Mira",
      "Jonas",
      "Ada",
    ]);
    expect(names(orderBy(players, "cost", "person"))).toEqual([
      "Jonas",
      "Mira",
      "Ada",
    ]);
    expect(names(orderBy(players, "time", "person"))).toEqual([
      "Ada",
      "Mira",
      "Jonas",
    ]);
  });

  it("gives three different orders for the same three players", () => {
    // This is the screen's entire argument — three lists, three first names.
    // If a sort ever silently fell back to one field, the lists would agree
    // and the trade-off would vanish without an error anywhere.
    const firsts = (["co2", "cost", "time"] as const).map(
      (metric) => orderBy(players, metric, "person")[0].name,
    );

    expect(new Set(firsts).size).toBe(3);
  });

  it("does not rank a leaver first for having played less", () => {
    // The bug the per-commute figures exist for. Ada played two rounds with
    // two Gruppen; Cem left after one round with one. The sums say Cem is
    // cleaner, cheaper and faster than everybody; the per-commute figures say
    // he drove exactly like Ada, because he did.
    const cem = player({
      player_id: "P-4",
      name: "Cem",
      left: true,
      total_co2_kg: 12,
      total_cost_eur: 1.7,
      total_time_min: 15.25,
      total_agent_trips: 1,
      co2_g_per_person: 240,
      cost_eur_per_person: 0.034,
      time_min_per_agent: 30.5,
    });

    expect(names(orderBy([ada, cem], "co2", "class"))).toEqual(["Cem", "Ada"]);
    // Per commute they are the same figure, so the stable sort keeps the order
    // the backend sent — and neither is put above the other.
    expect(names(orderBy([ada, cem], "co2", "person"))).toEqual(["Ada", "Cem"]);
  });

  it("follows the scale the reader is looking at", () => {
    // Mira's two agents walked; Dana's one drove. Per commute Dana is far
    // dirtier, in class scale her single Gruppe still moved less CO2.
    const dana = player({
      player_id: "P-5",
      name: "Dana",
      total_co2_kg: 24,
      total_agent_trips: 1,
      co2_g_per_person: 240,
    });

    expect(names(orderBy([mira, dana], "co2", "class"))).toEqual([
      "Dana",
      "Mira",
    ]);
    expect(names(orderBy([mira, dana], "co2", "person"))).toEqual([
      "Mira",
      "Dana",
    ]);
  });

  it("does not mutate the list it was given", () => {
    // The three lists render off one query result; an in-place sort would
    // reorder the other two behind their backs.
    orderBy(players, "time", "person");

    expect(names(players)).toEqual(["Mira", "Jonas", "Ada"]);
  });

  it("keeps ties in the order they arrived", () => {
    const a = player({ player_id: "P-1", name: "Ada", co2_g_per_person: 100 });
    const b = player({ player_id: "P-2", name: "Ben", co2_g_per_person: 100 });
    const c = player({ player_id: "P-3", name: "Cem", co2_g_per_person: 100 });

    expect(names(orderBy([a, b, c], "co2", "person"))).toEqual([
      "Ada",
      "Ben",
      "Cem",
    ]);
  });

  it("handles a game nobody finished a round of", () => {
    expect(orderBy([], "co2", "person")).toEqual([]);
  });
});

describe("playerValue", () => {
  it("reads CO2 in grams on both scales", () => {
    // Grams throughout, because the switch has to compare them: the payload
    // sends the class figure in kilos and the per-person one in grams, and
    // lib/co2.ts is the only place allowed to know it.
    expect(playerValue(ada, "co2", "class")).toBe(48_000);
    expect(playerValue(ada, "co2", "person")).toBe(240);
  });

  it("reads cost in euro on both scales", () => {
    expect(playerValue(ada, "cost", "class")).toBe(6.8);
    expect(playerValue(ada, "cost", "person")).toBe(0.034);
  });

  it("reads the same mean per trip for time, whatever the scale", () => {
    // `total_time_min` is a sum of agent means — 61 min for two commutes of
    // 30,5. It is not a quantity anybody has and nothing may read it.
    expect(playerValue(ada, "time", "person")).toBe(30.5);
    expect(playerValue(ada, "time", "class")).toBe(30.5);
  });
});

describe("roundValue", () => {
  it("reads one round's figure on the chosen scale", () => {
    const row = round({
      round_number: 2,
      co2_kg: 22,
      cost_eur: 3.4,
      time_min: 62,
      agent_count: 2,
      co2_g_per_person: 110,
      cost_eur_per_person: 0.017,
      time_min_per_agent: 31,
    });

    expect(roundValue(row, "co2", "class")).toBe(22_000);
    expect(roundValue(row, "co2", "person")).toBe(110);
    expect(roundValue(row, "cost", "class")).toBe(3.4);
    expect(roundValue(row, "cost", "person")).toBe(0.017);
    expect(roundValue(row, "time", "class")).toBe(31);
    expect(roundValue(row, "time", "person")).toBe(31);
  });
});

describe("classArc", () => {
  it("reads the class's own per-round figure", () => {
    // It used to sum the listed players, which undershot the round by
    // everybody who had left — and the headline total then disagreed with the
    // chart under it.
    const stops = classArc([
      classRound({ round_number: 1, co2_kg: 350 }),
      classRound({ round_number: 2, co2_kg: 280 }),
    ]);

    expect(stops.map((stop) => stop.co2Kg)).toEqual([350, 280]);
  });

  it("carries the part of each round no player rode", () => {
    // The timetable runs whether anybody boards or not, so a round total is
    // larger than its rows and the screen has to be able to say by how much.
    const [stop] = classArc([
      classRound({ round_number: 1, co2_kg: 350, unridden_co2_kg: 28.8 }),
    ]);

    expect(stop.unriddenCo2Kg).toBe(28.8);
  });

  it("carries whether the round was simulated at all", () => {
    const stops = classArc([
      classRound({ round_number: 1, simulation_used: false }),
      classRound({ round_number: 2, simulation_used: true }),
    ]);

    expect(stops.map((stop) => stop.simulationUsed)).toEqual([false, true]);
  });

  it("orders the stops by round number, whatever order the payload had", () => {
    const stops = classArc([
      classRound({ round_number: 3 }),
      classRound({ round_number: 1 }),
    ]);

    expect(stops.map((stop) => stop.roundNumber)).toEqual([1, 3]);
  });

  it("has no stops when no round was completed", () => {
    expect(classArc([])).toEqual([]);
  });
});
