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

  it("says what the vote put on the map, under its own title", () => {
    const html = renderInGame(<RoundHeader />, {
      ...running,
      voteOutcome: {
        stalemate: false,
        winningVersionId: 9,
        winningVersionName: "Buslinie",
        winningIsRollback: false,
        forced: false,
      },
    });

    expect(html).toContain(de.vote.appliedTitle);
    expect(html).toContain(de.vote.applied("Buslinie"));
  });

  it("calls a vote back „Wieder wie vorher“, not new on the map", () => {
    const html = renderInGame(<RoundHeader />, {
      ...running,
      voteOutcome: {
        stalemate: false,
        winningVersionId: 3,
        winningVersionName: "Busspuren zurücknehmen",
        winningIsRollback: true,
        forced: false,
      },
    });

    expect(de.vote.rolledBackTitle).toBe("Wieder wie vorher");
    expect(html).toContain("Wieder wie vorher");
    expect(html).not.toContain(de.vote.appliedTitle);
    expect(html).toContain(de.vote.applied("Busspuren zurücknehmen"));
  });
});
