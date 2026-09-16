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

  it("interpolates the parameterised strings", () => {
    expect(de.join.seats(3, 8)).toBe("3 von 8 Plätzen belegt");
    expect(de.lobby.co2Kg(120)).toBe("120 kg");
    expect(de.lobby.roundsCount(1)).toBe("1 Runde");
    expect(de.lobby.roundsCount(5)).toBe("5 Runden");
  });
});
