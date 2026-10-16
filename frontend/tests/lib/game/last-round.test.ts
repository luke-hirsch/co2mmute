import { describe, expect, it } from "vitest";

import { lastRoundLine } from "@/lib/game/last-round";
import type { RoundResult } from "@/lib/game/game-state";

function round(agents: unknown[] | undefined): RoundResult {
  return {
    roundNumber: 1,
    emissionsG: 0,
    costEur: 0,
    totalEmissionsG: 0,
    playerStats: [
      {
        player_id: "p1",
        player_name: "Mia",
        action: "car",
        emissions_g: 0,
        cost_eur: 0,
        time_min: 0,
        agent_count: 1,
        co2_g_per_person: 0,
        cost_eur_per_person: 0,
        paid_eur_per_person: 0,
        agents,
      },
    ],
    simulationUsed: true,
    peoplePerAgent: 10,
    networkCo2G: 0,
    networkCostEur: 0,
    unriddenCo2G: 0,
    unriddenCostEur: 0,
    paidEur: 0,
  } as RoundResult;
}

describe("lastRoundLine", () => {
  it("names mode, minutes and kg of the Gruppe", () => {
    const r = round([
      { agent_id: 2, mode: "car", trip_time_min: 34.4, co2_g_per_person: 2140 },
    ]);
    expect(lastRoundLine(r, "p1", 2)).toBe("Letzte Runde: Auto · 34 min · 2,1 kg");
  });

  it("is null in round 1, for another seat and for another Gruppe", () => {
    const r = round([
      { agent_id: 2, mode: "car", trip_time_min: 34, co2_g_per_person: 2140 },
    ]);
    expect(lastRoundLine(null, "p1", 2)).toBeNull();
    expect(lastRoundLine(r, "p9", 2)).toBeNull();
    expect(lastRoundLine(r, "p1", 3)).toBeNull();
    expect(lastRoundLine(round(undefined), "p1", 2)).toBeNull();
  });
});
