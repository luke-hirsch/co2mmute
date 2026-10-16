import { describe, expect, it } from "vitest";

import { endDisplay } from "@/components/replay/use-replay-clock";
import { buildWarp } from "@/lib/replay/time-warp";

describe("endDisplay", () => {
  const warp = buildWarp({ endMin: 1135, morningEndMin: 135, homeStartMin: 1000 });

  it("is the finished animation: last minute, on the beat, over", () => {
    const end = endDisplay(warp);
    expect(end.finished).toBe(true);
    expect(end.beat).toBe(true);
    expect(end.midday).toBe(false);
    expect(end.minute).toBe(warp.simMinuteAt(warp.durationSec));
  });
});
