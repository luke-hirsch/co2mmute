import { describe, expect, it } from "vitest";

import { mapUpdatesSent } from "@/components/host/create-game-screen";

describe("mapUpdatesSent", () => {
  it("is off on a map with nothing to vote on, whatever the host left it at", () => {
    expect(mapUpdatesSent({ offers_map_changes: false }, true)).toBe(false);
  });

  it("is the host's choice on a map with a ballot", () => {
    expect(mapUpdatesSent({ offers_map_changes: true }, true)).toBe(true);
    expect(mapUpdatesSent({ offers_map_changes: true }, false)).toBe(false);
  });

  it("keeps the host's choice while the map list is in flight", () => {
    expect(mapUpdatesSent(null, true)).toBe(true);
  });
});
