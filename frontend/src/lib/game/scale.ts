/**
 * The two scales every figure in this game has, and the unit a column of them
 * is written in.
 *
 * A round's numbers are class scale: kg and euro are multiplied by
 * `people_per_agent`, so one Fahrgast's commute arrives as a hundred or a
 * thousand commutes. That is the right scale for the budget — the game is played
 * against a CO₂ figure for the whole district — and the wrong one for "what did
 * my way to school cost". Both are in the payload, computed on the server
 * (a client dividing a rounded display figure by a thousand is dividing noise),
 * and the reader switches between them.
 *
 * Nothing here converts anything. `Scale` is which field to read; `co2Unit` is
 * how to write a column of whatever came back.
 */

/** Which of the two figures a screen is showing. */
export type Scale = "person" | "class";

export const scales: readonly Scale[] = ["person", "class"];

/** The switch, and all of its behaviour. */
export function otherScale(scale: Scale): Scale {
  return scale === "person" ? "class" : "person";
}

/** Grams or kilos, for a whole column at once. */
export type Co2Unit = "g" | "kg";

/**
 * One unit for a column of CO₂ figures, picked from the largest of them.
 *
 * `de.between.grams` switches at a kilo per figure, which is right for a single
 * number and wrong for a list: a column reading `0 g` over `4.794 kg` makes the
 * reader do a unit conversion to see which is bigger, and comparison is the only
 * thing these lists do. Per-person commutes usually all fit in grams and class
 * figures all fit in kilos, but a jammed car commute crosses the kilo on its own
 * — and then exactly one cell would change unit.
 *
 * Grams for an empty column, and NaN is ignored rather than allowed to poison
 * `Math.max`: a field that arrived as null would otherwise silently pick grams
 * for a column of tonnes.
 */
export function co2Unit(grams: readonly number[]): Co2Unit {
  let peak = 0;
  for (const value of grams) {
    if (Number.isFinite(value) && Math.abs(value) > peak) peak = Math.abs(value);
  }
  return peak >= 1000 ? "kg" : "g";
}
