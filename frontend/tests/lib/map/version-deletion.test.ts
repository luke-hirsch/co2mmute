import { describe, expect, it } from "vitest";

import { afterLines, goesLines, quotedList } from "@/lib/map/version-deletion";
import type { VersionDeletion } from "@/types/mapTypes";

/**
 * F14: the dialog that asks before a version is deleted.
 *
 * The server says what goes in numbers and names; these are the lines the
 * dialog makes of them. Nothing of a kind is no line, not "0 Knoten" — on the
 * shipped map nothing is ever in one version only, and the dialog has to say
 * that plainly rather than list seven zeros.
 */

const nothing: VersionDeletion["goes"] = {
  nodes: 0,
  edges: 0,
  streets: 0,
  rails: 0,
  bus_lines: [],
  train_lines: [],
  line_links: 0,
};

function deletion(overrides: Partial<VersionDeletion> = {}): VersionDeletion {
  return {
    version: { id: 9, name: "Neubaugebiet" },
    refusal: null,
    goes: nothing,
    ballot: [],
    keeps: [],
    ...overrides,
  };
}

describe("what goes", () => {
  it("is no line at all when the version holds nothing of its own", () => {
    expect(goesLines(nothing)).toEqual([]);
  });

  it("names each kind once, in the editor's words", () => {
    expect(
      goesLines({
        nodes: 1,
        edges: 2,
        streets: 2,
        rails: 0,
        bus_lines: ["200"],
        train_lines: ["U9", "U10"],
        line_links: 4,
      }),
    ).toEqual([
      "1 Knoten",
      "2 Kanten",
      "2 Straßen",
      "die Buslinie »200«",
      "die Bahnlinien »U9« und »U10«",
      "4 Abschnitte von Linien",
    ]);
  });

  it("counts one of a kind in the singular", () => {
    expect(goesLines({ ...nothing, edges: 1, rails: 1, line_links: 1 })).toEqual([
      "1 Kante",
      "1 Gleis",
      "1 Abschnitt von Linien",
    ]);
  });
});

describe("what follows from it", () => {
  it("names the ballot pairs that go and the versions that keep the change", () => {
    expect(
      afterLines(
        deletion({
          ballot: ["Grundversion", "Busspuren + Buslinie"],
          keeps: ["Busspuren + Buslinie"],
        }),
      ),
    ).toEqual([
      "Sie fällt aus der Abstimmung: von »Grundversion« und »Busspuren + Buslinie« aus steht sie nicht mehr zur Wahl.",
      "Ihre Änderung bleibt in »Busspuren + Buslinie« erhalten.",
    ]);
  });

  it("says nothing of a ballot it was never on", () => {
    expect(afterLines(deletion())).toEqual([]);
  });
});

describe("a list of names", () => {
  it("quotes them the way the ballot does", () => {
    expect(quotedList([])).toBe("");
    expect(quotedList(["A"])).toBe("»A«");
    expect(quotedList(["A", "B", "C"])).toBe("»A«, »B« und »C«");
  });
});
