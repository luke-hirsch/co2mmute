import { describe, expect, it } from "vitest";

import { canDriveOn, canUseEdge, carLanes } from "@/lib/map/edge-rules";
import type { Edge } from "@/types/mapTypes";

/**
 * Who may use a link, decided the way the simulation decides it.
 *
 * The rule these pin is `sim/state.py:EdgeState.open_to_cars` — `car_lanes > 0`,
 * where `car_lanes = max(0, lanes - reservations)` on a street and 0 without
 * one. `game/views_rest.py:_validate_routes` refuses the same cases at submit.
 * Before this module the client knew only `street_edge != null`, so it would
 * route a car down a gate and the submit would bounce it.
 */

function edge(over: Partial<Edge> = {}): Edge {
  return {
    id: 1,
    name: "",
    start_node: 1,
    end_node: 2,
    biking: true,
    walking: true,
    bike_lane: false,
    street_edge: { id: 1, speed_limit: 50, lanes: 2, dedicated_bus_lane: false },
    train_edge: null,
    ...over,
  };
}

const street = (lanes: number, over: Partial<Edge> = {}) =>
  edge({
    street_edge: { id: 1, speed_limit: 50, lanes, dedicated_bus_lane: false },
    ...over,
  });

const withBusLane = (lanes: number, over: Partial<Edge> = {}) =>
  edge({
    street_edge: { id: 1, speed_limit: 50, lanes, dedicated_bus_lane: true },
    ...over,
  });

describe("carLanes", () => {
  it("counts the whole street, reservations included", () => {
    expect(carLanes(street(2))).toBe(2);
    expect(carLanes(withBusLane(2))).toBe(1);
    expect(carLanes(street(2, { bike_lane: true }))).toBe(1);
  });

  it("takes one lane per reservation, so two reservations take two", () => {
    expect(carLanes(withBusLane(3, { bike_lane: true }))).toBe(1);
    expect(carLanes(withBusLane(2, { bike_lane: true }))).toBe(0);
  });

  it("floors at zero rather than going negative", () => {
    expect(carLanes(withBusLane(1, { bike_lane: true }))).toBe(0);
  });

  it("is zero on a link with no street under it", () => {
    // `"type": "path"` — a way for bikes and pedestrians, and a car goes round.
    expect(carLanes(edge({ street_edge: null }))).toBe(0);
  });
});

const withTramTrack = (lanes: number, track: "" | "lane" | "own") =>
  edge({
    street_edge: {
      id: 1,
      speed_limit: 30,
      lanes,
      dedicated_bus_lane: false,
      tram_track: track,
    },
    train_edge: { id: 1 },
  });

describe("carLanes with rails in the street", () => {
  // Friedrichstraße north: one lane, the M1's rails in it. The cars drive on
  // the rails, so they lose nothing; the tram's own track is a lane taken
  // from the street like a bus lane, and on one lane it is the last one.
  it("leaves the car lane to the cars where the rails lie in it", () => {
    expect(carLanes(withTramTrack(1, "lane"))).toBe(1);
  });

  it("takes a lane for the tram's own track", () => {
    expect(carLanes(withTramTrack(2, "own"))).toBe(1);
  });

  it("closes a one-lane street to cars once the tram has its own track", () => {
    expect(canDriveOn(withTramTrack(1, "own"))).toBe(false);
  });

  it("takes nothing for rails beside or under the street", () => {
    // The U2 under Bismarckstraße.
    expect(carLanes(withTramTrack(2, ""))).toBe(2);
  });
});

describe("canDriveOn", () => {
  it("allows the shipped map's bus-lane streets, which keep a car lane", () => {
    // Berlin Mitte-West: all 30 `Busspuren` edges are two-lane, so the version
    // closes nothing to cars. Measured 2026-09-28.
    expect(canDriveOn(withBusLane(2))).toBe(true);
  });

  it("refuses a gate: a one-lane street given over to the bus", () => {
    expect(canDriveOn(withBusLane(1))).toBe(false);
  });

  it("refuses a gate made by a bike lane, exactly as a bus lane makes one", () => {
    expect(canDriveOn(street(1, { bike_lane: true }))).toBe(false);
  });

  it("refuses a two-lane street carrying both reservations", () => {
    expect(canDriveOn(withBusLane(2, { bike_lane: true }))).toBe(false);
  });

  it("refuses a link with no street under it", () => {
    expect(canDriveOn(edge({ street_edge: null }))).toBe(false);
  });
});

describe("canUseEdge", () => {
  it("keeps a gate open to buses, bikes and pedestrians", () => {
    // That is the whole point of a gate: it is closed to cars and to nothing
    // else. `sim/linkqueue.py`: "closed to cars, open to buses, bikes and
    // pedestrians."
    const gate = withBusLane(1);
    expect(canUseEdge(gate, "car")).toBe(false);
    expect(canUseEdge(gate, "bike")).toBe(true);
    expect(canUseEdge(gate, "walk")).toBe(true);
  });

  it("still refuses a car on a plain path", () => {
    expect(canUseEdge(edge({ street_edge: null }), "car")).toBe(false);
  });

  it("treats a missing access flag as permission, not refusal", () => {
    // The graph omits `walking`/`biking` on an edge that carries the default.
    expect(canUseEdge(edge({ walking: undefined }), "walk")).toBe(true);
    expect(canUseEdge(edge({ biking: undefined }), "bike")).toBe(true);
  });

  it("honours an explicit refusal of bike or foot access", () => {
    expect(canUseEdge(edge({ biking: false }), "bike")).toBe(false);
    expect(canUseEdge(edge({ walking: false }), "walk")).toBe(false);
  });

  it("does not let a bike lane override a closure to bikes", () => {
    // The serializer refuses that combination on write; the client must not
    // invent access from the infrastructure flag if one slips through.
    expect(canUseEdge(edge({ biking: false, bike_lane: true }), "bike")).toBe(false);
  });

  it("routes public transport through its own router, never through an edge test", () => {
    expect(canUseEdge(edge(), "public")).toBe(false);
  });
});
