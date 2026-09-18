import { describe, expect, it } from "vitest";

import { classArc, orderBy, playerValue, roundValue } from "@/lib/game/summary";
import type { SummaryPlayer } from "@/lib/queries/summary";

/**
 * The end-of-game summary's arithmetic, without React.
 *
 * Two things are worth pinning. **The order**, because the whole screen is the
 * same three players in three different orders and the finding only exists if
 * those orders genuinely differ — a sort that quietly falls back to one field
 * would show three identical lists and nobody would notice it was a bug.
 *
 * And **the arc**, because it is derived rather than sent: the payload has
 * per-round figures per player and one grand total, nothing in between, so the
 * class's round-by-round line is summed here. The cases that matter are the
 * ones a real game produces — somebody who joined late, a round with no move —
 * where a player's `rounds` array is shorter than the game.
 */

function player(
  overrides: Partial<SummaryPlayer> & { player_id: string },
): SummaryPlayer {
  return {
    name: "Ben",
    total_co2_kg: 0,
    total_cost_eur: 0,
    total_time_min: 0,
    modes_used: [],
    rounds: [],
    ...overrides,
  };
}

/** Walks: least CO2, cheapest to run, slowest by a long way. */
const mira = player({
  player_id: "P-1",
  name: "Mira",
  total_co2_kg: 180,
  total_cost_eur: 4.2,
  total_time_min: 96,
  rounds: [
    { round_number: 1, co2_kg: 100, cost_eur: 2.2, time_min: 50 },
    { round_number: 2, co2_kg: 80, cost_eur: 2, time_min: 46 },
  ],
});

/** Public transport: in the middle on everything but the cheapest. */
const jonas = player({
  player_id: "P-2",
  name: "Jonas",
  total_co2_kg: 210,
  total_cost_eur: 3.1,
  total_time_min: 142,
  rounds: [
    { round_number: 1, co2_kg: 120, cost_eur: 1.6, time_min: 70 },
    { round_number: 2, co2_kg: 90, cost_eur: 1.5, time_min: 72 },
  ],
});

/** Drives: fastest, dirtiest, dearest. The trade-off in one row. */
const ada = player({
  player_id: "P-3",
  name: "Ada",
  total_co2_kg: 240,
  total_cost_eur: 6.8,
  total_time_min: 61,
  rounds: [
    { round_number: 1, co2_kg: 130, cost_eur: 3.4, time_min: 30 },
    { round_number: 2, co2_kg: 110, cost_eur: 3.4, time_min: 31 },
  ],
});

const players = [mira, jonas, ada];

function names(ordered: readonly SummaryPlayer[]): string[] {
  return ordered.map((p) => p.name);
}

describe("orderBy", () => {
  it("puts the lowest first for each of the three metrics", () => {
    // Ascending is better for all three: less CO2, less money, less time.
    expect(names(orderBy(players, "co2"))).toEqual(["Mira", "Jonas", "Ada"]);
    expect(names(orderBy(players, "cost"))).toEqual(["Jonas", "Mira", "Ada"]);
    expect(names(orderBy(players, "time"))).toEqual(["Ada", "Mira", "Jonas"]);
  });

  it("gives three different orders for the same three players", () => {
    // This is the screen's entire argument — three lists, three first names.
    // If a sort ever silently fell back to one field, the lists would agree
    // and the trade-off would vanish without an error anywhere.
    const firsts = (["co2", "cost", "time"] as const).map(
      (metric) => orderBy(players, metric)[0].name,
    );

    expect(new Set(firsts).size).toBe(3);
  });

  it("does not mutate the list it was given", () => {
    // The three lists render off one query result; an in-place sort would
    // reorder the other two behind their backs.
    orderBy(players, "time");

    expect(names(players)).toEqual(["Mira", "Jonas", "Ada"]);
  });

  it("keeps ties in the order they arrived", () => {
    const a = player({ player_id: "P-1", name: "Ada", total_co2_kg: 100 });
    const b = player({ player_id: "P-2", name: "Ben", total_co2_kg: 100 });
    const c = player({ player_id: "P-3", name: "Cem", total_co2_kg: 100 });

    expect(names(orderBy([a, b, c], "co2"))).toEqual(["Ada", "Ben", "Cem"]);
  });

  it("handles a game nobody finished a round of", () => {
    expect(orderBy([], "co2")).toEqual([]);
  });
});

describe("playerValue", () => {
  it("reads the total for the metric, in the unit the backend sent", () => {
    // kg, euro, minutes. Nothing is converted here: `GET .../summary/` sends
    // kilos where the socket sends grams, and lib/co2.ts is the only place
    // that is allowed to know it.
    expect(playerValue(ada, "co2")).toBe(240);
    expect(playerValue(ada, "cost")).toBe(6.8);
    expect(playerValue(ada, "time")).toBe(61);
  });
});

describe("roundValue", () => {
  it("reads one round's figure for the metric", () => {
    const round = { round_number: 2, co2_kg: 110, cost_eur: 3.4, time_min: 31 };

    expect(roundValue(round, "co2")).toBe(110);
    expect(roundValue(round, "cost")).toBe(3.4);
    expect(roundValue(round, "time")).toBe(31);
  });
});

describe("classArc", () => {
  it("sums the listed players round by round", () => {
    expect(classArc(players)).toEqual([
      { roundNumber: 1, co2Kg: 350 },
      { roundNumber: 2, co2Kg: 280 },
    ]);
  });

  it("orders the stops by round number, whatever order the payload had", () => {
    const late = player({
      player_id: "P-9",
      rounds: [
        { round_number: 3, co2_kg: 10, cost_eur: 0, time_min: 0 },
        { round_number: 1, co2_kg: 30, cost_eur: 0, time_min: 0 },
      ],
    });

    expect(classArc([late]).map((stop) => stop.roundNumber)).toEqual([1, 3]);
  });

  it("keys on the round number, not on the position in the array", () => {
    // A player who joined in round 2 has a two-element `rounds` array for a
    // three-round game. Indexing would add their round 2 onto everyone's
    // round 1 and shift the whole line left.
    const full = player({
      player_id: "P-1",
      rounds: [
        { round_number: 1, co2_kg: 100, cost_eur: 0, time_min: 0 },
        { round_number: 2, co2_kg: 100, cost_eur: 0, time_min: 0 },
        { round_number: 3, co2_kg: 100, cost_eur: 0, time_min: 0 },
      ],
    });
    const joinedLate = player({
      player_id: "P-2",
      rounds: [
        { round_number: 2, co2_kg: 5, cost_eur: 0, time_min: 0 },
        { round_number: 3, co2_kg: 5, cost_eur: 0, time_min: 0 },
      ],
    });

    expect(classArc([full, joinedLate])).toEqual([
      { roundNumber: 1, co2Kg: 100 },
      { roundNumber: 2, co2Kg: 105 },
      { roundNumber: 3, co2Kg: 105 },
    ]);
  });

  it("has no stops when nobody is in the list", () => {
    // `playing()` filters everyone who left, so a game whose players all left
    // comes back with an empty list and a non-zero total. The arc says
    // nothing rather than claiming zero.
    expect(classArc([])).toEqual([]);
  });
});
