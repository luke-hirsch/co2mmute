import { describe, expect, it } from "vitest";

import {
  DEFAULT_AGENT_PER_PLAYER,
  DEFAULT_MAX_PLAYERS,
  DEFAULT_MAX_ROUNDS,
  co2BudgetKg,
  peoplePerAgent,
} from "@/lib/calibration";

/**
 * The mirror of `backend/game/calibration.py`, which is the point of S13: the
 * two numbers the create screen offers have to follow the class size *while it
 * is being chosen*, and a round trip per keystroke is not that.
 *
 * Every number in here is also asserted on the Python side — the cases are
 * deliberately the same ones, so a change to either half has to move two files
 * and a reader can hold them side by side. `game/tests/test_join.py` has the
 * 16/8/4/2 table, the 6/3/10 budgets and the 800-over-64 tie.
 */

/** Berlin Mitte-West, which is what the shipped map and the field defaults say. */
const BERLIN = { district_commuters: 6_400, co2_budget_kg_per_round: 8_000 };

describe("what the create screen opens on", () => {
  it("is the calibrated class size", () => {
    expect(DEFAULT_MAX_PLAYERS).toBe(16);
    expect(DEFAULT_AGENT_PER_PLAYER).toBe(4);
    expect(DEFAULT_MAX_ROUNDS).toBe(6);
  });

  /**
   * The pair that replaced 1000-against-500, which ended every game in round
   * one: the shipped map's timetable alone emits about 2 900 kg a round.
   */
  it("derives the shipped pair on the shipped map", () => {
    expect(
      peoplePerAgent(DEFAULT_MAX_PLAYERS, DEFAULT_AGENT_PER_PLAYER, BERLIN),
    ).toBe(100);
    expect(co2BudgetKg(DEFAULT_MAX_ROUNDS, BERLIN)).toBe(48_000);
  });
});

describe("people per Fahrgast follows the class size", () => {
  /**
   * The district's commuter population is constant, so half the seats means
   * twice the people behind each Fahrgast. Pin the scale instead and a
   * half-full class sees 0.4 min of delay where a full one sees 11.3 — a
   * different game depending on who came to the lesson.
   */
  it("doubles as the seats halve", () => {
    expect(peoplePerAgent(16, 4, BERLIN)).toBe(100);
    expect(peoplePerAgent(8, 4, BERLIN)).toBe(200);
    expect(peoplePerAgent(4, 4, BERLIN)).toBe(400);
    expect(peoplePerAgent(2, 4, BERLIN)).toBe(800);
  });

  it("counts Fahrgäste, not players", () => {
    expect(peoplePerAgent(16, 2, BERLIN)).toBe(200);
    expect(peoplePerAgent(32, 1, BERLIN)).toBe(200);
  });

  it("comes off the map that was chosen", () => {
    const quiet = { district_commuters: 1_600, co2_budget_kg_per_round: 2_000 };
    expect(peoplePerAgent(16, 4, quiet)).toBe(25);
  });

  /**
   * Python's `round()` is half-to-even and `Math.round` is half-up, so this is
   * the one case where a naive mirror would disagree with the server about a
   * game either could create. 800 over 64 Fahrgäste is 12.5, and the answer is
   * 12 — under the corridors' capacity is the safe side of a tie.
   */
  it("rounds a tie down, the way Python does", () => {
    const tiny = { district_commuters: 800, co2_budget_kg_per_round: 8_000 };
    expect(peoplePerAgent(16, 4, tiny)).toBe(12);
  });

  it("rounds the other tie up, the way Python does", () => {
    // 2400 / 64 = 37.5, and 37 is odd, so half-to-even goes to 38.
    const other = { district_commuters: 2_400, co2_budget_kg_per_round: 8_000 };
    expect(peoplePerAgent(16, 4, other)).toBe(38);
  });

  /** A Fahrgast standing for nobody is not a smaller game, it is no game. */
  it("never goes below one", () => {
    const empty = { district_commuters: 1, co2_budget_kg_per_round: 8_000 };
    expect(peoplePerAgent(16, 4, empty)).toBe(1);
  });

  /** The fields are strings while they are being retyped. Empty is not zero. */
  it("treats an empty field as one, not as a division by zero", () => {
    expect(Number.isFinite(peoplePerAgent(Number(""), 4, BERLIN))).toBe(true);
    expect(peoplePerAgent(0, 0, BERLIN)).toBe(6_400);
  });
});

describe("the CO2 budget follows the round count and nothing else", () => {
  it("multiplies the map's per-round figure", () => {
    expect(co2BudgetKg(6, BERLIN)).toBe(48_000);
    expect(co2BudgetKg(3, BERLIN)).toBe(24_000);
    expect(co2BudgetKg(10, BERLIN)).toBe(80_000);
  });

  /**
   * No Fahrgast term, on purpose: the district's population is constant, so a
   * round costs what it costs however many students play.
   */
  it("does not move with the class size", () => {
    expect(co2BudgetKg(6, BERLIN)).toBe(
      co2BudgetKg(6, { ...BERLIN, district_commuters: 999 }),
    );
  });

  it("comes off the map that was chosen", () => {
    const quiet = { district_commuters: 1_600, co2_budget_kg_per_round: 2_000 };
    expect(co2BudgetKg(6, quiet)).toBe(12_000);
  });

  it("treats an empty field as one round", () => {
    expect(co2BudgetKg(Number(""), BERLIN)).toBe(8_000);
  });
});
