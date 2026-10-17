import { describe, expect, it } from "vitest";

import { RoundHeader } from "@/components/round/round-header";
import { de } from "@/lib/de";

import { renderInGame } from "../in-game";

const running = {
  currentRound: 2,
  maxRounds: 6,
  totalEmissionsG: 40_000,
  maxCo2LevelG: 100_000,
};

describe("RoundHeader", () => {
  it("shows the budget above every turn", () => {
    expect(renderInGame(<RoundHeader />, running)).toContain(de.co2.label);
  });

  it("shows no budget in a game that hides its CO₂", () => {
    const html = renderInGame(<RoundHeader />, { ...running, hideCo2: true });

    expect(html).not.toContain("CO₂");
    expect(html).toContain(de.round.of(2, 6));
  });
});
