import { describe, expect, it } from "vitest";

import { co2Unit, otherScale } from "@/lib/game/scale";

/**
 * The two scales every figure in this game has, and the unit a column of them
 * is allowed to carry.
 *
 * A round's numbers are class scale — kg and euro are multiplied by
 * `people_per_agent` — and the same numbers divided back down are what one
 * commuter did once. Both are true and both are in the payload; the screen lets
 * the reader switch between them, so nothing here converts anything. It only
 * decides how a column is written.
 *
 * And that decision is the bug this module exists for: `de.between.grams`
 * switches to kg at a kilo, which is right for a single figure and wrong for a
 * column. A list that says `0 g` over `4.794 kg` makes the reader convert units
 * to see which is bigger, and a column of per-person figures where one commute
 * happens to cross a kilo reads as two different quantities.
 */

describe("co2Unit", () => {
  it("writes a column of small figures in grams", () => {
    // A per-person commute: a few hundred grams, a bike ride zero.
    expect(co2Unit([525.2, 610.4, 0, 138.7])).toBe("g");
  });

  it("writes a column in kilos as soon as one figure needs them", () => {
    // The point of picking per column rather than per cell: the 0 and the 138
    // move to kg with the rest, instead of standing in a different unit.
    expect(co2Unit([525.2, 2_140.0, 0])).toBe("kg");
  });

  it("takes the whole column into account, not the first value", () => {
    expect(co2Unit([0, 0, 1_200_000])).toBe("kg");
  });

  it("stays in grams exactly at the boundary minus one", () => {
    expect(co2Unit([999.9])).toBe("g");
    expect(co2Unit([1_000])).toBe("kg");
  });

  it("answers for an empty column without throwing", () => {
    // A round nobody played: the table renders its head and no rows.
    expect(co2Unit([])).toBe("g");
  });

  it("ignores figures that are not numbers", () => {
    // Defensive: a payload field that arrived as null would otherwise make
    // Math.max return NaN and the comparison silently pick grams.
    expect(co2Unit([Number.NaN, 4_000])).toBe("kg");
  });
});

describe("otherScale", () => {
  it("is the switch's whole behaviour", () => {
    expect(otherScale("person")).toBe("class");
    expect(otherScale("class")).toBe("person");
  });
});
