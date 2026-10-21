import { describe, expect, it } from "vitest";

import { modeTally, ownGroups, typeOverview } from "@/lib/game/groups";
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
    home: "Wohnort Moabit",
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

describe("typeOverview", () => {
  const sparfuchs = (modes: SummaryGroup["modes"], rounds = 3) =>
    group({ persona: { name: "Sparfuchs", description: "x" }, modes, rounds });
  const sport = (modes: SummaryGroup["modes"], rounds = 3) =>
    group({ persona: { name: "Sportskanone", description: "y" }, modes, rounds });

  it("lays every type out once, over all the seats that hold it", () => {
    const rows = typeOverview([
      player("A", [sparfuchs({ bike: 2, car: 1 }), sport({ bike: 3 })]),
      player("B", [sparfuchs({ bike: 1, public: 2 })]),
    ]);

    expect(rows.map((r) => [r.name, r.groups, r.rounds])).toEqual([
      ["Sparfuchs", 2, 6],
      ["Sportskanone", 1, 3],
    ]);
    expect(rows[0].modes).toEqual({ bike: 3, car: 1, public: 2 });
  });

  it("counts a Gruppe that never ran, and lets it add no trip", () => {
    const rows = typeOverview([
      player("A", [sparfuchs({}, 0), sparfuchs({ car: 2 }, 2)]),
    ]);

    expect(rows[0].groups).toBe(2);
    expect(rows[0].rounds).toBe(2);
    expect(rows[0].modes).toEqual({ car: 2 });
  });

  it("leaves out a Gruppe with no type, and a game with none", () => {
    expect(typeOverview([player("A", [group({ persona: null })])])).toEqual([]);
    expect(typeOverview([player("A", [])])).toEqual([]);
  });

  it("names no player and no figure of CO₂", () => {
    const rows = typeOverview([player("A", [sparfuchs({ bike: 1 })])]);

    expect(JSON.stringify(rows)).not.toContain("co2");
    expect(JSON.stringify(rows)).not.toContain("player");
    expect(JSON.stringify(rows)).not.toContain('"A"');
  });
});
