import { describe, expect, it } from "vitest";

import { ReplayCanvas } from "@/components/replay/replay-canvas";

// The tests run in Node with no DOM, so a re-render cannot be counted. What can
// be pinned is that the canvas is memoised: the player re-renders four times a
// second for the clock text, and an unmemoised canvas re-rendered every street
// of the map with it (a 50-60 ms frame on built Berlin).
describe("ReplayCanvas", () => {
  it("is memoised, so a clock tick of the player does not re-render it", () => {
    expect((ReplayCanvas as unknown as { $$typeof: symbol }).$$typeof).toBe(
      Symbol.for("react.memo"),
    );
  });
});
