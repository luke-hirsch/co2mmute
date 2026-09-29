/**
 * The two numbers a game is played against, derived as the host types. S13.
 *
 * This mirrors `backend/game/calibration.py`. It is a mirror on purpose, the
 * same way `lib/map/edge-rules.ts` mirrors the simulation's rule: the whole
 * point of S13 is that the offer follows the class size *while it is being
 * chosen*, and a round trip per keystroke is not that. The inputs both come off
 * the selected map (`GET api/maps/` carries `district_commuters` and
 * `co2_budget_kg_per_round` per row), so nothing here is a constant that could
 * drift away from a particular neighbourhood's measurements.
 *
 * What the arithmetic is FOR is in the Python module's docstring and in
 * `docs/kalibrierung.md`; the short version:
 *
 * - **`people_per_agent` is derived from the class size, never picked.** A map
 *   depicts a place and a place has a commuter population. The class divides
 *   that population between its Gruppen; it does not summon new commuters
 *   when more students turn up. Pin the scale instead and a half-full class
 *   sees 0.4 min of delay where a full one sees 11.3 — a different game
 *   depending on who came to the lesson.
 * - **The budget carries no Gruppe term**, for the same reason: the district's
 *   population is constant, so a round costs what it costs however many play.
 *
 * Neither is a rule. Both are written into fields the host can type over, and
 * the endpoint takes whatever it is sent.
 */

/** What the create screen opens on. `game/calibration.py` has the same three. */
export const DEFAULT_MAX_PLAYERS = 16;
export const DEFAULT_AGENT_PER_PLAYER = 4;
export const DEFAULT_MAX_ROUNDS = 6;

/**
 * The two fields the derivation reads off whichever map is selected.
 *
 * A subset of the map row rather than the whole thing, so it is obvious that
 * nothing else about a map reaches this file.
 *
 * Both functions require one. The Python side falls back to the model's field
 * defaults when no map is named, because the server-rendered form had to render
 * before a map was chosen; the React screen has no such moment — it waits for
 * the map list, selects the first row and derives from that. Making the
 * argument non-null is what keeps a "no map yet" fallback constant out of this
 * file, where it would be a second answer to a question `GameMap` already has.
 */
export type CalibrationInputs = {
  district_commuters: number;
  co2_budget_kg_per_round: number;
};

/**
 * Python's `round()`, which is half-to-even — not `Math.round`, which is
 * half-up.
 *
 * It matters exactly once and the backend pins it: 800 commuters over 64
 * Gruppen is 12.5, and the answer is 12. Rounding down at a tie is the safe
 * side — it puts less traffic on the corridors than the map was measured for,
 * not more. `Math.round` would answer 13 and the two halves would disagree
 * about a game either could have created.
 *
 * Only defined for the non-negative values this module deals in.
 */
function roundHalfToEven(value: number): number {
  const lower = Math.floor(value);
  const fraction = value - lower;
  if (fraction > 0.5) return lower + 1;
  if (fraction < 0.5) return lower;
  return lower % 2 === 0 ? lower : lower + 1;
}

/**
 * How many real people one Gruppe stands for, for this class size.
 *
 * Floored at 1: a game with more Gruppen than the district has commuters is
 * nonsense, but it must not be a game where each one stands for nobody.
 */
export function peoplePerAgent(
  maxPlayers: number,
  agentPerPlayer: number,
  map: CalibrationInputs,
): number {
  const agents =
    Math.max(1, Math.trunc(maxPlayers) || 0) *
    Math.max(1, Math.trunc(agentPerPlayer) || 0);
  return Math.max(1, roundHalfToEven(map.district_commuters / agents));
}

/** The CO₂ budget in kg for a game of this many rounds on this map. */
export function co2BudgetKg(maxRounds: number, map: CalibrationInputs): number {
  return map.co2_budget_kg_per_round * Math.max(1, Math.trunc(maxRounds) || 0);
}
