import { describe, expect, it } from "vitest";

import { de } from "@/lib/de";

type Node = string | ((...args: never[]) => string) | { [key: string]: Node };

/** Every leaf in the dictionary, as `a.b.c` paths. */
function leaves(node: Node, path: string[] = []): [string, Node][] {
  if (typeof node === "string" || typeof node === "function") {
    return [[path.join("."), node]];
  }
  return Object.entries(node).flatMap(([key, value]) => leaves(value, [...path, key]));
}

describe("de", () => {
  it("has no blank or untrimmed strings", () => {
    const bad = leaves(de as unknown as Node)
      .filter(([, value]) => typeof value === "string")
      .filter(([, value]) => {
        const text = value as string;
        return text.length === 0 || text !== text.trim();
      })
      .map(([path]) => path);

    expect(bad).toEqual([]);
  });

  it("covers exactly the reasons the backend can send", () => {
    // `_joinable()` in backend/game/views_join.py returns one of these three.
    expect(Object.keys(de.join.blocked).sort()).toEqual(["ended", "full", "started"]);
  });

  it("covers exactly the four transport modes the backend stores", () => {
    // `AgentRoute.transport_mode` in backend/game/models.py.
    expect(Object.keys(de.modes).sort()).toEqual([
      "bike",
      "car",
      "public",
      "walk",
    ]);
  });

  it("covers exactly the revoke reasons the backend can send", () => {
    // `revoke()` in backend/game/roster.py, called from game/seats.py.
    expect(Object.keys(de.revoked.reason).sort()).toEqual([
      "handed_over",
      "left",
      "removed",
      "taken_over",
    ]);
  });

  it("covers exactly the car optimizations the backend accepts", () => {
    // `AgentRoute.Optimization` in backend/game/models.py. The serializer's
    // ChoiceField rejects anything else with a 400, so a missing key here is
    // a turn that cannot be submitted.
    expect(Object.keys(de.round.carOptimization).sort()).toEqual([
      "co2",
      "distance",
      "time",
    ]);
  });

  it("covers exactly the public-transport optimizations the router offers", () => {
    // `PTOptimization` in src/types/routeTypes.ts — client-side only, but the
    // picker renders one label per value.
    expect(Object.keys(de.round.ptOptimization).sort()).toEqual([
      "fastest",
      "fewest_transfers",
      "no_bus",
    ]);
  });

  it("names the turn without naming a player", () => {
    // Copy rule: a player's name never reaches a log, a toast or an error.
    // These three are the strings the round screen shows while waiting.
    expect(de.round.agent(1)).toBe("Fahrgast 1");
    expect(de.round.submittedOf(3, 5)).toBe("3 von 5 abgeschickt");
    expect(de.round.chosenOf(1, 2)).toBe("1 von 2 gewählt");
  });

  it("covers exactly the roster statuses the backend can send", () => {
    // `_status()` in backend/game/roster.py.
    expect(Object.keys(de.seat.status).sort()).toEqual([
      "making_move",
      "not_connected",
      "ready",
      "waiting",
    ]);
  });

  it("interpolates the parameterised strings", () => {
    expect(de.join.seats(3, 8)).toBe("3 von 8 Plätzen belegt");
    expect(de.lobby.co2Kg(120)).toBe("120 kg");
    expect(de.lobby.roundsCount(1)).toBe("1 Runde");
    expect(de.lobby.roundsCount(5)).toBe("5 Runden");
    expect(de.round.of(3, 5)).toBe("Runde 3 von 5");
    expect(de.co2.used(41, 100)).toBe("41 von 100 kg");
  });

  it("does not promise minutes it cannot keep on a code about to expire", () => {
    expect(de.code.expiresIn(300)).toBe("noch 5 Minuten gültig");
    expect(de.code.expiresIn(90)).toBe("noch 2 Minuten gültig");
    expect(de.code.expiresIn(45)).toBe("läuft gleich ab");
  });

  it("addresses the reader as du, never Sie", () => {
    // Settled 2026-09-17 and it applies to the legal pages too, so it is worth
    // a test rather than a habit.
    const siezen = /\b(Sie|Ihre|Ihren|Ihrem|Ihnen)\b/;
    const offenders = leaves(de as unknown as Node)
      .filter(([, value]) => typeof value === "string")
      .filter(([, value]) => siezen.test(value as string))
      .map(([path]) => path);

    expect(offenders).toEqual([]);
  });
});
