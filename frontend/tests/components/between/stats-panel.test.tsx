import { describe, expect, it } from "vitest";

import { StatsPanel } from "@/components/between/stats-panel";
import { de } from "@/lib/de";
import type { RoundResult } from "@/lib/game/game-state";

import { renderInGame } from "../in-game";

const round: RoundResult = {
  roundNumber: 2,
  emissionsG: 52_000,
  costEur: 410,
  totalEmissionsG: 98_000,
  playerStats: [
    {
      player_id: "P-1",
      player_name: "Alex",
      action: "car",
      emissions_g: 30_000,
      cost_eur: 250,
      time_min: 31,
      agent_count: 2,
      co2_g_per_person: 2_100,
      cost_eur_per_person: 4.2,
      paid_eur_per_person: 3.1,
    },
  ],
  simulationUsed: true,
  peoplePerAgent: 106,
  networkCo2G: 30_000,
  networkCostEur: 200,
  unriddenCo2G: 22_000,
  unriddenCostEur: 160,
  paidEur: 180,
};

function panel() {
  return (
    <StatsPanel
      round={round}
      seatId="P-1"
      totalEmissionsG={98_000}
      maxCo2LevelG={200_000}
    />
  );
}

describe("StatsPanel", () => {
  it("shows the CO₂ column, its sums and the budget", () => {
    const html = renderInGame(panel());

    expect(html).toContain(`>${de.between.co2}<`);
    expect(html).toContain(de.co2.label);
    expect(html).toContain(de.between.unriddenHint);
  });

  it("shows time and cost, and no CO₂, in a game that hides it", () => {
    const html = renderInGame(panel(), { hideCo2: true });

    expect(html).not.toContain("CO₂");
    expect(html).not.toContain(de.between.co2Figure(round.emissionsG, "kg"));
    expect(html).toContain(de.between.cost);
    expect(html).toContain(de.between.time);
    expect(html).toContain(de.between.eur(round.unriddenCostEur));
    expect(html).toContain(de.between.unriddenCostHint);
  });
});
