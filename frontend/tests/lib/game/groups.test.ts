import { describe, expect, it } from "vitest";

import { modeTally, ownGroups } from "@/lib/game/groups";
import type { GameSummary, SummaryGroup, SummaryPlayer } from "@/lib/queries/summary";

/**
 * "Meine Gruppen" on the end screen, without React.
 *
 * Only a seat's own Gruppen, and only when the game dealt Pendlertypen — the
 * switch offers the view on nothing else. The host has no seat in `players`
 * (`without_host_rows`), so the projector never offers it.
 */

function group(overrides: Partial<SummaryGroup> = {}): SummaryGroup {
  return {
    agent_id: 1,
    destination: "Arbeit",
    persona: { name: "Sparfuchs", description: "Jeder Euro zählt." },
    rounds: 3,
    modes: { bike: 2, car: 1 },
    time_min: 40,
    distance_km: 9.5,
    speed_kmh: 14.3,
    paid_eur: 0.2,
    co2_g: 310,
    changes: 0,
    ...overrides,
  };
}

function player(player_id: string, groups: SummaryGroup[]): SummaryPlayer {
  return {
    player_id,
    name: player_id,
    left: false,
    total_co2_kg: 0,
    total_cost_eur: 0,
    total_time_min: 0,
    total_agent_trips: 0,
    co2_g_per_person: 0,
    cost_eur_per_person: 0,
    time_min_per_agent: 0,
    paid_eur_per_person: 0,
    modes_used: [],
    rounds: [],
    groups,
  };
}

function summary(players: SummaryPlayer[]): GameSummary {
  return {
    game_id: "ABC123",
    game_name: "5b",
    end_reason: "max_rounds",
    rounds_played: 3,
    max_rounds: 3,
    total_co2_kg: 0,
    max_co2_kg: 100,
    people_per_agent: 100,
    rounds: [],
    players,
  };
}

describe("ownGroups", () => {
  it("is the viewer's own seat's Gruppen", () => {
    const mine = [group(), group({ agent_id: 2 })];
    const data = summary([player("P-OTHR", [group()]), player("P-MINE", mine)]);

    expect(ownGroups(data, "P-MINE")).toBe(mine);
  });

  it("is empty for a game without Pendlertypen", () => {
    expect(ownGroups(summary([player("P-MINE", [])]), "P-MINE")).toEqual([]);
  });

  it("is empty for the host, whose row is not in the list", () => {
    expect(ownGroups(summary([player("P-MINE", [group()])]), "P-HOST")).toEqual([]);
  });

  it("is empty before the summary lands or without a seat", () => {
    expect(ownGroups(undefined, "P-MINE")).toEqual([]);
    expect(ownGroups(summary([player("P-MINE", [group()])]), null)).toEqual([]);
  });
});

describe("modeTally", () => {
  it("lists the modes taken, most often first", () => {
    expect(modeTally({ car: 1, bike: 2 })).toEqual([
      { mode: "bike", count: 2 },
      { mode: "car", count: 1 },
    ]);
  });

  it("breaks a tie in the order the four lines always run in", () => {
    expect(modeTally({ walk: 1, public: 1, car: 1 }).map((m) => m.mode)).toEqual([
      "car",
      "public",
      "walk",
    ]);
  });

  it("is empty for a Gruppe that never rode a simulated round", () => {
    expect(modeTally({})).toEqual([]);
  });
});
