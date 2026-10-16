import { describe, expect, it } from "vitest";

import { replayClockOfDay } from "@/lib/replay/clock-of-day";

describe("replayClockOfDay", () => {
  it("runs the morning from one hour before the departure hour", () => {
    expect(replayClockOfDay(0, { morningHour: 9, eveningHour: 17, homeStartMin: 1000 })).toBe("8:00 Uhr");
    expect(replayClockOfDay(75, { morningHour: 9, eveningHour: 17, homeStartMin: 1000 })).toBe("9:15 Uhr");
  });

  it("runs the evening from one hour before the evening hour", () => {
    const h = { morningHour: 9, eveningHour: 17, homeStartMin: 1000 };
    expect(replayClockOfDay(1000, h)).toBe("16:00 Uhr");
    expect(replayClockOfDay(1030, h)).toBe("16:30 Uhr");
  });
});
