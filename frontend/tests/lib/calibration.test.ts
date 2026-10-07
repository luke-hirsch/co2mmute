import { describe, expect, it } from "vitest";

import {
  CO2_KG_PER_PERSON_NORMAL,
  DEFAULT_AGENT_PER_PLAYER,
  DEFAULT_MAX_PLAYERS,
  DEFAULT_MAX_ROUNDS,
  co2BudgetKg,
  co2KgPerPersonChoices,
  peoplePerAgent,
} from "@/lib/calibration";

/**
 * The mirror of `backend/game/calibration.py`, which is the point of S13: the
 * numbers the create screen offers have to follow the class size *while it is
 * being chosen*, and a round trip per keystroke is not that.
 *
 * Every number in here is also asserted on the Python side — the cases are
 * deliberately the same ones, so a change to either half has to move two files
 * and a reader can hold them side by side. `game/tests/test_join.py` has the
 * 16/8/4/2 table, the budgets and the 800-over-64 tie; `test_calibration.py`
 * has the dial.
 */

/** Berlin Mitte-West, which is what the shipped map and the field default say. */
const BERLIN = { district_commuters: 6_800 };

describe("what the create screen opens on", () => {
  it("is the calibrated class size", () => {
    expect(DEFAULT_MAX_PLAYERS).toBe(16);
    expect(DEFAULT_AGENT_PER_PLAYER).toBe(4);
    expect(DEFAULT_MAX_ROUNDS).toBe(6);
  });

  /** 106 people behind each of 64 Gruppen; 2.4 kg × 6 800 × six rounds. */
  it("derives the shipped pair on the shipped map", () => {
    expect(
      peoplePerAgent(DEFAULT_MAX_PLAYERS, DEFAULT_AGENT_PER_PLAYER, BERLIN),
    ).toBe(106);
    expect(
      co2BudgetKg(DEFAULT_MAX_ROUNDS, BERLIN, CO2_KG_PER_PERSON_NORMAL),
    ).toBe(97_920);
  });
});

describe("people per Gruppe follows the class size", () => {
  /**
   * The district's commuter population is constant, so half the seats means
   * twice the people behind each Gruppe. Pin the scale instead and a
   * half-full class sees 0.4 min of delay where a full one sees 11.3 — a
   * different game depending on who came to the lesson.
   */
  it("doubles as the seats halve", () => {
    expect(peoplePerAgent(16, 4, BERLIN)).toBe(106);
    // 6 800 / 32 is 212.5, and Python's round() goes to even.
    expect(peoplePerAgent(8, 4, BERLIN)).toBe(212);
    expect(peoplePerAgent(4, 4, BERLIN)).toBe(425);
    expect(peoplePerAgent(2, 4, BERLIN)).toBe(850);
  });

  it("counts Gruppen, not players", () => {
    expect(peoplePerAgent(16, 2, BERLIN)).toBe(212);
    expect(peoplePerAgent(32, 1, BERLIN)).toBe(212);
  });

  it("comes off the map that was chosen", () => {
    expect(peoplePerAgent(16, 4, { district_commuters: 1_600 })).toBe(25);
  });

  /**
   * Python's `round()` is half-to-even and `Math.round` is half-up, so this is
   * the one case where a naive mirror would disagree with the server about a
   * game either could create. 800 over 64 Gruppen is 12.5, and the answer is
   * 12 — under the corridors' capacity is the safe side of a tie.
   */
  it("rounds a tie down, the way Python does", () => {
    expect(peoplePerAgent(16, 4, { district_commuters: 800 })).toBe(12);
  });

  it("rounds the other tie up, the way Python does", () => {
    // 2400 / 64 = 37.5, and 37 is odd, so half-to-even goes to 38.
    expect(peoplePerAgent(16, 4, { district_commuters: 2_400 })).toBe(38);
  });

  /** A Gruppe standing for nobody is not a smaller game, it is no game. */
  it("never goes below one", () => {
    expect(peoplePerAgent(16, 4, { district_commuters: 1 })).toBe(1);
  });

  /** The fields are strings while they are being retyped. Empty is not zero. */
  it("treats an empty field as one, not as a division by zero", () => {
    expect(Number.isFinite(peoplePerAgent(Number(""), 4, BERLIN))).toBe(true);
    expect(peoplePerAgent(0, 0, BERLIN)).toBe(6_800);
  });
});

describe("the CO₂ budget is kg per person × commuters × rounds", () => {
  it("multiplies the dial by the map's commuters and the rounds", () => {
    expect(co2BudgetKg(6, BERLIN, "2.4")).toBe(97_920);
    expect(co2BudgetKg(3, BERLIN, "2.4")).toBe(48_960);
    expect(co2BudgetKg(10, BERLIN, "2.4")).toBe(163_200);
    expect(co2BudgetKg(6, BERLIN, "1.0")).toBe(40_800);
    expect(co2BudgetKg(6, BERLIN, "6.0")).toBe(244_800);
  });

  /**
   * A map with fewer commuters gets a smaller budget at the same kg, and only
   * through them: the kg is the same on every map.
   */
  it("comes off the map that was chosen", () => {
    expect(co2BudgetKg(6, { district_commuters: 1_600 }, "2.4")).toBe(23_040);
  });

  it("treats an empty field as one round", () => {
    expect(co2BudgetKg(Number(""), BERLIN, "2.4")).toBe(16_320);
  });
});

describe("the dial", () => {
  /**
   * Berlin Mitte-West's half-driving round, 2.41 kg a head, rounded to the
   * step: a design anchor, the same on every map.
   */
  it("opens on normal", () => {
    expect(CO2_KG_PER_PERSON_NORMAL).toBe("2.4");
  });

  it("goes from 1.0 to 6.0 kg in steps of 0.2", () => {
    const choices = co2KgPerPersonChoices();
    expect(choices[0]).toBe("1.0");
    expect(choices.at(-1)).toBe("6.0");
    expect(choices).toHaveLength(26);
    expect(choices).toContain(CO2_KG_PER_PERSON_NORMAL);
    const tenths = choices.map((value) => Math.round(Number(value) * 10));
    expect(new Set(tenths.slice(1).map((t, i) => t - tenths[i]))).toEqual(
      new Set([2]),
    );
  });

  /** What is sent is what Django's decimal field reads back: one decimal. */
  it("writes every value the way the endpoint takes it", () => {
    for (const value of co2KgPerPersonChoices()) {
      expect(value).toMatch(/^\d\.\d$/);
    }
  });
});
