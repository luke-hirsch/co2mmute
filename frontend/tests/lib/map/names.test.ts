import { describe, expect, it } from "vitest";

import { de } from "@/lib/de";
import { defaultName, isPlaceholderName } from "@/lib/map/names";

/**
 * What the editor calls what it draws, and which names it won't save.
 *
 * A node drawn by hand used to be "Knoten 4587", the row's id, so a new map
 * started in the thousands. Now a click names it after the map, counted from 1,
 * and the panels won't save that name or an empty one.
 */

const node = de.editor.node.defaultName;
const edge = de.editor.edge.defaultName;

describe("defaultName", () => {
  it("starts a map at 1", () => {
    expect(defaultName("Callenberg", [], node)).toBe("Callenberg Knoten 1");
    expect(defaultName("Callenberg", ["Markt", null, "Bahnhof"], edge)).toBe(
      "Callenberg Kante 1",
    );
  });

  it("counts on from the highest the editor gave on this map", () => {
    const taken = ["Callenberg Knoten 2", "Callenberg Knoten 7", "Markt", null];
    expect(defaultName("Callenberg", taken, node)).toBe("Callenberg Knoten 8");
  });

  it("reads only its own kind and its own map", () => {
    const taken = ["Callenberg Kante 9", "Berlin Knoten 40", "Knoten 4587"];
    expect(defaultName("Callenberg", taken, node)).toBe("Callenberg Knoten 1");
  });

  it("keeps a long map name inside the 100 characters a name holds", () => {
    const long = "Sehr lange Karte ".repeat(10);
    const first = defaultName(long, [], node);
    expect(first.length).toBeLessThanOrEqual(100);
    expect(first).toMatch(/ Knoten 1$/);
    expect(defaultName(long, [first], node)).toMatch(/ Knoten 2$/);
  });
});

describe("isPlaceholderName", () => {
  it("refuses an empty name and the editor's own", () => {
    for (const name of [
      "",
      "   ",
      "Knoten 4587",
      "Kante 12",
      "Callenberg Knoten 3",
      "Callenberg Kante 1",
      "node 12345",
    ]) {
      expect(isPlaceholderName(name), name).toBe(true);
    }
  });

  it("takes a name someone chose", () => {
    for (const name of ["Ernst-Reuter-Platz", "Kantstraße", "Knoten Nord", "U2"]) {
      expect(isPlaceholderName(name), name).toBe(false);
    }
  });
});
