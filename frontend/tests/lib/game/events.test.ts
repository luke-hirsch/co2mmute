import { describe, expect, it } from "vitest";

import { asGameEvent } from "@/lib/game/events";

describe("asGameEvent", () => {
  it("passes a frame with a type through", () => {
    const frame = { type: "roster.update", game_id: "ABC123", players: [] };
    expect(asGameEvent(frame)).toBe(frame);
  });

  // A frame with no type would otherwise reach the reducer's `default` branch
  // and be silently treated as an event the lobby has no opinion on — which is
  // true of `vote.recorded` and false of a broken frame.
  it("rejects anything that is not an event", () => {
    expect(asGameEvent(null)).toBeNull();
    expect(asGameEvent(undefined)).toBeNull();
    expect(asGameEvent("roster.update")).toBeNull();
    expect(asGameEvent(42)).toBeNull();
    expect(asGameEvent({})).toBeNull();
    expect(asGameEvent({ type: 7 })).toBeNull();
  });
});
