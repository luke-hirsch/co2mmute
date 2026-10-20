/**
 * The model's numbers as the browser needs them.
 *
 * `backend/sim/constants.py` is where each one is written down, with its source.
 * The names here are the Python names; `tests/lib/constants.test.ts` reads that
 * file and fails when a value below disagrees. Changing a number is the two
 * files, and the test says if one was forgotten.
 *
 * The block "only here" has no twin: limits the client alone applies.
 */

// --- mirrored from sim/constants.py -----------------------------------------

/** Speeds when a map states none, km/h. */
export const FALLBACK_WALK_SPEED_KMH = 5;
export const FALLBACK_BIKE_SPEED_KMH = 20;
export const FALLBACK_CAR_SPEED_KMH = 50;

/** The car's CO₂ curve EF(v) = a/v + b + c·v², see `lib/map/car-emissions.ts`. */
export const CAR_EMISSIONS_G_PER_KM = 166.8;
export const CAR_EF_ANCHOR_SPEED_KMH = 50;
export const CAR_EF_MIN_SPEED_KMH = 70;
export const CAR_EF_DRAG_TERM = 0.0028605;
export const MAX_CAR_EMISSION_FACTOR = 2;

/** Storage capacity of a link, vehicles per lane-km. */
export const JAM_DENSITY_VEH_PER_KM_LANE = 133;

/** The budget's dial, kg of CO₂ per person per round. */
export const CO2_KG_PER_PERSON_NORMAL = 2.4;
export const CO2_KG_PER_PERSON_STEP = 0.2;
export const CO2_KG_PER_PERSON_MIN = 0.6;
export const CO2_KG_PER_PERSON_MAX = 6.0;

// --- only here --------------------------------------------------------------

/** How far anybody goes under their own power: 5 km on foot, 15 km by bike. */
export const MAX_WALK_M = 5000;
export const MAX_BIKE_M = 15000;

/** The walk to the first stop and from the last one, in the PT router. */
export const PT_MAX_WALK_DISTANCE_M = 2000;
