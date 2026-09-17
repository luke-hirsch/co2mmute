import { describe, expect, it } from "vitest";

import {
  BUDGET_DANGER_AT,
  BUDGET_WARN_AT,
  budgetLevel,
  budgetShare,
  displayKg,
  exceededBudget,
  gramsToKg,
  kgToGrams,
} from "@/lib/co2";

/**
 * Units are the documented recurring bug in this project: the websocket sends
 * grams, the summary endpoint sends kg, and `game.started` / `game.ended`
 * disagree with each other about which one they mean. These functions are the
 * one place the SPA converts, so they are worth pinning down.
 */
describe("grams and kilograms", () => {
  it("converts both ways", () => {
    expect(gramsToKg(41_200)).toBe(41.2);
    expect(kgToGrams(100)).toBe(100_000);
    expect(gramsToKg(kgToGrams(37))).toBe(37);
  });

  it("rounds to whole kg for display", () => {
    expect(displayKg(41_200)).toBe(41);
    expect(displayKg(41_800)).toBe(42);
    expect(displayKg(0)).toBe(0);
  });
});

describe("budgetShare", () => {
  it("is the fraction of the budget used", () => {
    expect(budgetShare(kgToGrams(25), kgToGrams(100))).toBe(0.25);
  });

  it("clamps, so a bar never overdraws its track", () => {
    expect(budgetShare(kgToGrams(150), kgToGrams(100))).toBe(1);
    expect(budgetShare(-5, kgToGrams(100))).toBe(0);
  });

  it("survives the values a fresh game actually sends", () => {
    // A game that has not started has no emissions, and a game with no map has
    // never had a max either — neither may render NaN into a style attribute.
    expect(budgetShare(0, kgToGrams(100))).toBe(0);
    expect(budgetShare(0, 0)).toBe(0);
    expect(budgetShare(Number.NaN, kgToGrams(100))).toBe(0);
  });
});

describe("exceededBudget", () => {
  it("is true only past the limit, not at it", () => {
    expect(exceededBudget(kgToGrams(99), kgToGrams(100))).toBe(false);
    expect(exceededBudget(kgToGrams(100), kgToGrams(100))).toBe(false);
    expect(exceededBudget(kgToGrams(101), kgToGrams(100))).toBe(true);
  });

  it("is false when there is no budget to exceed", () => {
    expect(exceededBudget(kgToGrams(10), 0)).toBe(false);
  });
});

describe("budgetLevel", () => {
  const max = kgToGrams(100);

  it("walks ok -> warn -> danger at the documented bands", () => {
    expect(budgetLevel(kgToGrams(10), max)).toBe("ok");
    expect(budgetLevel(max * (BUDGET_WARN_AT - 0.01), max)).toBe("ok");
    expect(budgetLevel(max * BUDGET_WARN_AT, max)).toBe("warn");
    expect(budgetLevel(max * (BUDGET_DANGER_AT - 0.01), max)).toBe("warn");
    expect(budgetLevel(max * BUDGET_DANGER_AT, max)).toBe("danger");
  });

  it("is danger once the budget is blown, which ends the game", () => {
    expect(budgetLevel(kgToGrams(120), max)).toBe("danger");
  });
});
