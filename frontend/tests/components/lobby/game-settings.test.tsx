import { describe, expect, it } from "vitest";

import { GameSettings } from "@/components/lobby/game-settings";
import { de } from "@/lib/de";

import { renderInGame } from "../in-game";

const lobby = { agentPerPlayer: 4, maxRounds: 6, maxCo2LevelKg: 97_920 };

describe("GameSettings", () => {
  it("names the CO₂ budget the game was set up with", () => {
    expect(renderInGame(<GameSettings />, lobby)).toContain(
      de.lobby.settings.co2Budget,
    );
  });

  it("leaves the budget out of a game that hides its CO₂", () => {
    const html = renderInGame(<GameSettings />, { ...lobby, hideCo2: true });

    expect(html).not.toContain("CO₂");
    expect(html).toContain(de.lobby.settings.maxRounds);
  });
});
