/**
 * Who may use a link — the client's copy of a rule the backend already owns.
 *
 * `lanes` counts the whole street, every reservation included, so ticking
 * "Busspur" or "Radweg" **is** the trade-off: it takes a lane off the cars. When
 * it takes the last one the street becomes a **gate** — closed to cars, open to
 * buses, bikes and pedestrians. Zero car lanes is legal and deliberate (Lukas:
 * "if that means a road gets closed for the car entirely, then this is what it
 * is. People can decide and vote about it").
 *
 * The client did not know any of that. It asked `street_edge != null` and
 * nothing else, so it would happily route a car through a gate and
 * `_validate_routes` would bounce the submit with a message written for a
 * developer. Same gap for a Fahrradstraße.
 *
 * ### Which backend rule this mirrors
 *
 * The simulation's, not the validator's. `sim/state.py:EdgeState.open_to_cars`
 * is `car_lanes > 0` with `car_lanes = max(0, lanes - reservations)`;
 * `game/views_rest.py:_validate_routes` refuses only when there is at least one
 * reservation, so the two disagree about a zero-lane street with no reservation
 * on it. No map has one, and mirroring the simulation is the safe direction: the
 * client is then never laxer than the server, so it can never offer a route the
 * submit refuses.
 *
 * ### What it changes on the shipped map today: nothing
 *
 * Measured 2026-09-28 over `map_examples/Berlin_Mitte-West.json`: 30 street
 * edges carry a bus lane, all of them on the four `Busspuren` versions, and all
 * 30 are two-lane — so one car lane survives every one of them and the map has
 * no gate anywhere. There are no bike lanes on it at all. This is insurance, and
 * it stops being insurance the moment a bike lane is drawn: 48 of the map's 116
 * street edges are one-lane, and a bike lane on any of them is a gate.
 */

import type { Edge } from "@/types/mapTypes";
import type { TransportMode } from "@/types/routeTypes";

/**
 * Lanes left for cars once the reservations have taken theirs.
 *
 * Zero on a link with no street under it — a `"type": "path"`, which is a way
 * for bikes and pedestrians and nothing else.
 */
export function carLanes(edge: Edge): number {
  const street = edge.street_edge;
  if (!street) return 0;

  // Counted, not asked about by name: with two reservations on one street the
  // "is it a bus lane or a bike lane" question falls through both branches.
  let reserved = 0;
  if (street.dedicated_bus_lane) reserved += 1;
  if (edge.bike_lane) reserved += 1;

  return Math.max(0, street.lanes - reserved);
}

/** False on a gate, and on anything with no street under it. */
export function canDriveOn(edge: Edge): boolean {
  return carLanes(edge) > 0;
}

/**
 * Whether a mode may use this link at all.
 *
 * A missing access flag means permission: the graph omits `walking`/`biking` on
 * an edge carrying the default, so only an explicit `false` is a refusal.
 *
 * Public transport is never answered here — it rides its own lines and
 * `ptRouting.ts` walks them.
 */
export function canUseEdge(edge: Edge, mode: TransportMode): boolean {
  switch (mode) {
    case "walk":
      return edge.walking !== false;
    case "bike":
      // `bike_lane` is the infrastructure and `biking` is the access right. A
      // lane never invents permission — the serializer refuses that combination
      // on write, and the client must not undo it if one slips through.
      return edge.biking !== false;
    case "car":
      return canDriveOn(edge);
    default:
      return false;
  }
}
