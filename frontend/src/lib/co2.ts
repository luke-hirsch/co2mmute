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

/** Bands the budget bar changes colour at. Kept here so the test can see them. */
export const BUDGET_WARN_AT = 0.6;
export const BUDGET_DANGER_AT = 0.85;

export type BudgetLevel = "ok" | "warn" | "danger";

export function budgetLevel(usedG: number, maxG: number): BudgetLevel {
  const share = budgetShare(usedG, maxG);
  if (exceededBudget(usedG, maxG) || share >= BUDGET_DANGER_AT) return "danger";
  if (share >= BUDGET_WARN_AT) return "warn";
  return "ok";
}
