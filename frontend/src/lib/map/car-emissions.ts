/**
 * What a car emits per kilometre at a given average speed, relative to 50 km/h.
 *
 * The backend's curve, `sim/constants.py:car_emissions_g_per_km` — COPERT/HBEFA
 * style, EF(v) = a/v + b + c·v², minimum at 70 km/h, with `a` and `b` derived
 * from `c` and the two calibration conditions so that EF(50) is exactly the
 * anchor. Only the ratio leaves this file: the router weighs a link by
 * distance × factor, and the anchor cancels. The factor is capped at 2.00×
 * (biting below 9.2 km/h) rather than the speed being floored, as there.
 *
 * Written twice on purpose, like the design tokens: the halves share no
 * package. `tests/utils/traffic-routing.test.ts` pins the numbers the backend
 * gives, so a change on one side turns the other red.
 */

import {
  CAR_EF_ANCHOR_SPEED_KMH,
  CAR_EF_DRAG_TERM,
  CAR_EF_MIN_SPEED_KMH,
  CAR_EMISSIONS_G_PER_KM,
  MAX_CAR_EMISSION_FACTOR,
} from "@/lib/constants";

const ANCHOR_G_PER_KM = CAR_EMISSIONS_G_PER_KM; // at 50 km/h
const ANCHOR_SPEED_KMH = CAR_EF_ANCHOR_SPEED_KMH;
const MIN_SPEED_KMH = CAR_EF_MIN_SPEED_KMH;
const DRAG = CAR_EF_DRAG_TERM; // c
const IDLE = 2 * DRAG * MIN_SPEED_KMH ** 3; // a
const ROLLING =
  ANCHOR_G_PER_KM - IDLE / ANCHOR_SPEED_KMH - DRAG * ANCHOR_SPEED_KMH ** 2; // b
const MAX_FACTOR = MAX_CAR_EMISSION_FACTOR;

export function carEmissionFactor(speedKmh: number): number {
  const speed = Math.max(speedKmh, 1);
  const grams = IDLE / speed + ROLLING + DRAG * speed * speed;
  return Math.min(grams, MAX_FACTOR * ANCHOR_G_PER_KM) / ANCHOR_G_PER_KM;
}
