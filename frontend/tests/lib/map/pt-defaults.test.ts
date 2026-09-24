import { describe, expect, it } from "vitest";

import { DEFAULT_PT_CAPACITY, defaultPtCapacity } from "@/lib/map/pt-defaults";

describe("default PT capacity", () => {
  it("gives a train an order of magnitude more than a bus", () => {
    // The bug this constant exists to close: one default for both modes,
    // which put 60 seats in a U-Bahn on the shipped map.
    expect(defaultPtCapacity("train")).toBeGreaterThan(
      defaultPtCapacity("bus") * 10,
    );
  });

  it("matches the backend's own defaults", () => {
    // maps/models.py: bus_capacity default=85, train_capacity default=1000.
    // Drifting apart here is invisible until a map is built in the editor and
    // then re-imported from JSON with different numbers.
    expect(DEFAULT_PT_CAPACITY).toEqual({ bus: 85, train: 1000 });
  });
});
