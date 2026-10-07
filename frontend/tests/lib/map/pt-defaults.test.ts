import { describe, expect, it } from "vitest";

import {
  DEFAULT_PT_CAPACITY,
  DEFAULT_PT_SPEED_KMH,
  defaultPtCapacity,
  defaultPtSpeed,
} from "@/lib/map/pt-defaults";

describe("default PT capacity", () => {
  it("gives a train an order of magnitude more than a bus", () => {
    // The bug this constant exists to close: one default for both modes,
    // which put 60 seats in a U-Bahn on the shipped map.
    expect(defaultPtCapacity("train")).toBeGreaterThan(
      defaultPtCapacity("bus") * 10,
    );
  });

  it("matches the backend's own defaults", () => {
    // maps/models.py: bus_capacity default=85, TrainLine.DEFAULTS 1000 for a
    // train and 248 for a tram (Berlin's 40 m Flexity). Drifting apart here is
    // invisible until a map is built in the editor and then re-imported from
    // JSON with different numbers.
    expect(DEFAULT_PT_CAPACITY).toEqual({ bus: 85, train: 1000, tram: 248 });
  });
});

describe("default PT speed", () => {
  it("matches the backend's own defaults", () => {
    // maps/models.py: bus_speed_kmh default=30, TrainLine.DEFAULTS 40 for a
    // train and 30 for a tram. The editor started every new line at 30 and the
    // version builder a train at 60.
    expect(DEFAULT_PT_SPEED_KMH).toEqual({ bus: 30, train: 40, tram: 30 });
    expect(defaultPtSpeed("tram")).toBe(30);
    expect(defaultPtCapacity("tram")).toBe(248);
  });
});
