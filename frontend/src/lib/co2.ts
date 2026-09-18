/**
 * Units, in one place.
 *
 * The backend is not consistent about this and cannot be made consistent
 * without breaking the running game, so the SPA converts at the edge:
 *
 *   - the websocket sends grams        (`total_emissions_g`, `max_co2_level_g`)
 *   - `GET .../summary/` sends kg      (`total_co2_kg`, `max_co2_kg`)
 *   - `GameSession.max_CO2_level` is kg, and `game.started` sends it in kg
 *     while `game.ended` sends `max_co2_level_g` in grams
 *
 * Everything below takes grams. Convert once, where the data arrives, and never
 * do arithmetic on a number whose unit is not in its name.
 */

export const GRAMS_PER_KG = 1000;

export function gramsToKg(grams: number): number {
  return grams / GRAMS_PER_KG;
}

export function kgToGrams(kg: number): number {
  return kg * GRAMS_PER_KG;
}

/** Whole kg, for display. The game never needs more precision than this. */
export function displayKg(grams: number): number {
  return Math.round(gramsToKg(grams));
}

/**
 * How much of the budget is used, 0..1. Clamped, so a bar never overdraws its
 * track — `exceededBudget` is what tells you it went over.
 */
export function budgetShare(usedG: number, maxG: number): number {
  if (!Number.isFinite(usedG) || !Number.isFinite(maxG) || maxG <= 0) return 0;
  return Math.min(Math.max(usedG / maxG, 0), 1);
}

export function exceededBudget(usedG: number, maxG: number): boolean {
  if (!Number.isFinite(usedG) || !Number.isFinite(maxG) || maxG <= 0) {
    return false;
  }
  return usedG > maxG;
}

/**
 * The budget has two states, not three.
 *
 * A third band would have to distinguish "warning" from "danger", and on this
 * screen that is a distinction without a difference: either the budget is fine
 * or it wants your attention. So the bar runs in the primary and flips to the
 * accent — the primary's complement, which is what makes the flip read as
 * tension rather than as decoration.
 *
 * 0.75 rather than something later: the budget ending the game is the event the
 * whole round is played against, and players need a round or two to change what
 * they are doing about it.
 */
export const BUDGET_ATTENTION_AT = 0.75;

export type BudgetLevel = "ok" | "attention";

export function budgetLevel(usedG: number, maxG: number): BudgetLevel {
  if (exceededBudget(usedG, maxG)) return "attention";
  return budgetShare(usedG, maxG) >= BUDGET_ATTENTION_AT ? "attention" : "ok";
}
