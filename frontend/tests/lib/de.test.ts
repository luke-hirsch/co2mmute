import { describe, expect, it } from "vitest";

import { de, type GameEndReason } from "@/lib/de";

/**
 * The dictionary is the one place a missing string is cheap to catch.
 *
 * Components stay untested — they are still in flux and the rule is to target
 * the pure `lib/` layer — but `de.ts` is pure data, and two things about it
 * have gone wrong for real: a reason the backend sends that the frontend has no
 * word for (renders as nothing at all), and a figure that skipped the German
 * formatter ("10349 von 500000 kg" next to "10.349 kg" elsewhere).
 */

/**
 * Every member of the union, listed once. TypeScript checks this against
 * `GameEndReason`, so adding a fifth reason to the type without adding it here
 * fails the build rather than the test — which is the same trick the
 * `Record<GameEndReason, string>` in `de.ts` plays on the dictionary itself.
 */
const allEndReasons: readonly GameEndReason[] = [
  "co2_limit",
  "max_rounds",
  "host",
  "idle",
];

describe("de.summary.reason", () => {
  it("has a German sentence for every way a game can end", () => {
    for (const reason of allEndReasons) {
      expect(de.summary.reason[reason], reason).toBeTruthy();
    }
  });

  it("says who ended it when the host did", () => {
    expect(de.summary.reason.host).toContain("Spielleitung");
  });

  it("does not claim all rounds were played when the game idled out", () => {
    expect(de.summary.reason.idle).not.toBe(de.summary.reason.max_rounds);
  });
});

describe("the CO₂ budget line", () => {
  it("groups thousands in both figures", () => {
    const line = de.co2.used(10349, 500000);

    expect(line).toContain("10.349");
    expect(line).toContain("500.000");
    expect(line).not.toContain("500000");
  });

  it("groups the lobby's budget too", () => {
    expect(de.lobby.co2Kg(500000)).toContain("500.000");
  });

  it("leaves small numbers alone", () => {
    expect(de.co2.used(0, 500)).toBe("0 von 500 kg");
  });
});

describe("the map editor speaks German", () => {
  /**
   * F7 translated the editor's shell and left the instructional and status
   * strings in English, which is what the 2026-09-19 run found. These are the
   * keys that pass wired up; a missing one is a component falling back to a
   * hardcoded string.
   */
  const keys: [string, string][] = [
    ["editor.notFound", de.editor.notFound],
    ["editor.unsaved", de.editor.unsaved],
    ["editor.emptyMap", de.editor.emptyMap],
    ["editor.pickHint", de.editor.pickHint],
    ["editor.modify", de.editor.modify],
    ["editor.remove", de.editor.remove],
    ["editor.manage", de.editor.manage],
    ["editor.tools.addNodeHint", de.editor.tools.addNodeHint],
    ["editor.tools.addEdgeHint", de.editor.tools.addEdgeHint],
    ["editor.tools.selectHint", de.editor.tools.selectHint],
    ["editor.tools.proposeNodeHint", de.editor.tools.proposeNodeHint],
    ["editor.tools.proposeEdgeHint", de.editor.tools.proposeEdgeHint],
    ["editor.node.noTypes", de.editor.node.noTypes],
    ["editor.edge.direction", de.editor.edge.direction],
    ["editor.edge.whichDirection", de.editor.edge.whichDirection],
    ["editor.edge.accessibleBy", de.editor.edge.accessibleBy],
    ["editor.ptLine.flipDirection", de.editor.ptLine.flipDirection],
    ["editor.ptLine.extendHint", de.editor.ptLine.extendHint],
    ["editor.ptLine.none", de.editor.ptLine.none],
    ["editor.version.compatible", de.editor.version.compatible],
    ["editor.version.changeImage", de.editor.version.changeImage],
    ["editor.version.replaceImage", de.editor.version.replaceImage],
    ["editor.version.uploadImage", de.editor.version.uploadImage],
    ["editor.version.createTitle", de.editor.version.createTitle],
    ["editor.version.noPtLines", de.editor.version.noPtLines],
    ["map.pickHint", de.map.pickHint],
    ["map.clearSelection", de.map.clearSelection],
  ];

  it.each(keys)("%s is set", (_name, value) => {
    expect(value).toBeTruthy();
  });

  it("uses du, not Sie", () => {
    const sentences = keys.map(([, value]) => value).join(" ");

    expect(sentences).not.toMatch(/\bSie\b/);
    expect(sentences).not.toMatch(/\bIhre?n?\b/);
  });
});

describe("the dialog close label", () => {
  it("exists, because every dialog renders it for screen readers", () => {
    expect(de.actions.close).toBe("Schließen");
  });
});
