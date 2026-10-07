/**
 * The two numbers a game is played against, derived as the host types. S13.
 *
 * This mirrors `backend/game/calibration.py`. It is a mirror on purpose, the
 * same way `lib/map/edge-rules.ts` mirrors the simulation's rule: the whole
 * point of S13 is that the offer follows the class size *while it is being
 * chosen*, and a round trip per keystroke is not that. The scale comes off the
 * selected map (`GET api/maps/` carries `district_commuters` per row); the
 * budget is kg per person per round, the same on every map since F8 step 2b,
 * so the dial's four numbers are the one constant here, mirrored from Python.
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
 * - **The budget is kg per person × the map's commuters × the rounds**, and
 *   carries no Gruppe term: the district's population is constant, so a round
 *   costs what it costs however many play. The kg is the host's dial; a map
 *   with long commutes or a thin timetable is harder at the same kg by itself,
 *   which is the lesson, not a flaw.
 *
 * Neither is a rule. The scale is written into a field the host can type over,
 * the budget follows the dial, and the endpoint takes whatever it is sent.
 */

/** What the create screen opens on. `game/calibration.py` has the same three. */
export const DEFAULT_MAX_PLAYERS = 16;
export const DEFAULT_AGENT_PER_PLAYER = 4;
export const DEFAULT_MAX_ROUNDS = 6;

/**
 * The dial: kg of CO₂ per person per round, there and back. Normal is Berlin
 * Mitte-West's half-driving round, 2.41 kg a head, rounded to the step — a
 * design anchor, the same on every map. Strings, because they are what the
 * select holds and what the endpoint's decimal field reads; the arithmetic
 * below works in tenths so no float ever reaches a budget.
 */
export const CO2_KG_PER_PERSON_NORMAL = "2.4";
const KG_TENTHS = { min: 10, max: 60, step: 2 } as const;

/** Every value the dial offers, smallest first: "1.0" … "6.0". */
export function co2KgPerPersonChoices(): string[] {
  const choices: string[] = [];
  for (let t = KG_TENTHS.min; t <= KG_TENTHS.max; t += KG_TENTHS.step) {
    choices.push((t / 10).toFixed(1));
  }
  return choices;
}

/**
 * The field the derivation reads off whichever map is selected.
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

/**
 * The CO₂ budget in kg for a game: kg per person × the map's commuters ×
 * rounds.
 *
 * The map's commuters, not the people the scale field puts on it: they are the
 * same figure while the scale is derived, and a host who lightens a round by
 * typing over the scale must not get a budget the timetable alone exceeds —
 * the lines run whether anybody rides. Whole kg, because `max_CO2_level` is;
 * half-to-even like Python, though the dial's even tenths never make a tie.
 */
export function co2BudgetKg(
  maxRounds: number,
  map: CalibrationInputs,
  kgPerPerson: string,
): number {
  const tenths = Math.round(Number(kgPerPerson) * 10);
  const total =
    tenths * map.district_commuters * Math.max(1, Math.trunc(maxRounds) || 0);
  return roundHalfToEven(total / 10);
}
