import { describe, expect, it } from "vitest";

import { de, type GameEndReason } from "@/lib/de";

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

  it("covers exactly the refusals the host's endpoints can send", () => {
    // `SeatRefused` in backend/game/seats.py (full, ended, host, controlled)
    // plus `PauseRefused` in backend/game/pause.py (paused, not_running,
    // not_paused). Every one of them reaches a host as a 409.
    expect(Object.keys(de.host.failed).sort()).toEqual([
      "controlled",
      "ended",
      "full",
      "host",
      "not_paused",
      "not_running",
      "paused",
    ]);
  });

  it("covers exactly the refusals redeeming a seat code can send", () => {
    // `SeatCodeView.post` in backend/game/views_join.py. 404 is separate: it
    // means the code is gone, not that this browser may not use it.
    expect(Object.keys(de.resumeSeat.refused).sort()).toEqual([
      "ended",
      "host",
      "seated",
    ]);
  });

  it("names a seat without naming its player in the desk's own copy", () => {
    // The desk is the one screen that does say names out loud — it is the
    // teacher's own screen and the room is looking at it. What it must not do
    // is put one in a status line that also goes somewhere else.
    expect(de.host.playingSeat("Ana")).toBe("Platz von Ana");
    expect(de.host.curtainTitle("Ben")).toBe("Ben ist dran");
  });

  it("heads the summary's three lists with a superlative, not a metric", () => {
    // F6: the end screen is the same players three times in three orders. The
    // headings have to say what being at the top of one *means*, because the
    // order is the only thing that says it — the entries are not numbered.
    expect(de.summary.cleanest).toBe("Am wenigsten CO₂");
    expect(de.summary.cheapest).toBe("Am günstigsten");
    expect(de.summary.fastest).toBe("Am schnellsten");
  });

  it("crowns nobody at the end of a game", () => {
    // The research group's position (via Lukas, 2026-09-18): there is no
    // winner, or who won is what the class argues about afterwards. So the
    // closing line is a plain string and not a function — there is no way to
    // pass it a name, which is what would turn it into a verdict.
    expect(typeof de.summary.noWinner).toBe("string");
    expect(de.summary.noWinner).not.toMatch(/Sieger|Gewinner|gewonnen|Platz 1/);
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

/**
 * Added after the second full run (2026-09-19). Two things had gone wrong that
 * the checks above could not see: a reason the backend sends that the frontend
 * has no word for (a `Record` lookup that renders nothing), and figures that
 * skipped the German formatter — "10349 von 500000 kg" next to "10.349 kg"
 * everywhere else.
 */
describe("de.summary.reason", () => {
  /**
   * Listed once, checked by TypeScript against `GameEndReason`: adding a fifth
   * reason to the type without adding it here fails the build rather than the
   * test — the same trick the `Record` in `de.ts` plays on the dictionary.
   */
  const allEndReasons: readonly GameEndReason[] = [
    "co2_limit",
    "max_rounds",
    "host",
    "idle",
  ];

  it("covers exactly the reasons the backend can send", () => {
    expect(Object.keys(de.summary.reason).sort()).toEqual(
      [...allEndReasons].sort(),
    );
  });

  it("has a German sentence for every one of them", () => {
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
   * strings in English. These are the keys the components were wired to in the
   * pass that fixed it; a missing one means a component fell back to a
   * hardcoded string. The blank-string check in `describe("de")` above covers
   * their content, so these only assert that they exist.
   */
  const keys: [string, string][] = [
    ["editor.notFound", de.editor.notFound],
    ["editor.unsaved", de.editor.unsaved],
    ["editor.emptyMap", de.editor.emptyMap],
    ["editor.pickHint", de.editor.pickHint],
    ["editor.modify", de.editor.modify],
    ["editor.remove", de.editor.remove],
    ["editor.manage", de.editor.manage],
    ["editor.editMap", de.editor.editMap],
    ["editor.deleteMap", de.editor.deleteMap],
    ["editor.versionStep1", de.editor.versionStep1],
    ["editor.tools.addNodeHint", de.editor.tools.addNodeHint],
    ["editor.tools.addEdgeHint", de.editor.tools.addEdgeHint],
    ["editor.tools.selectHint", de.editor.tools.selectHint],
    ["editor.tools.proposeNodeHint", de.editor.tools.proposeNodeHint],
    ["editor.tools.proposeEdgeHint", de.editor.tools.proposeEdgeHint],
    ["editor.tools.editingPtLine", de.editor.tools.editingPtLine],
    ["editor.node.noTypes", de.editor.node.noTypes],
    ["editor.edge.direction", de.editor.edge.direction],
    ["editor.edge.whichDirection", de.editor.edge.whichDirection],
    ["editor.edge.accessibleBy", de.editor.edge.accessibleBy],
    ["editor.edge.maxLanes", de.editor.edge.maxLanes],
    ["editor.edge.distance", de.editor.edge.distance],
    ["editor.ptLine.flipDirection", de.editor.ptLine.flipDirection],
    ["editor.ptLine.extendHint", de.editor.ptLine.extendHint],
    ["editor.ptLine.none", de.editor.ptLine.none],
    ["editor.ptLine.addBus", de.editor.ptLine.addBus],
    ["editor.ptLine.addTrain", de.editor.ptLine.addTrain],
    ["editor.version.compatible", de.editor.version.compatible],
    ["editor.version.changeImage", de.editor.version.changeImage],
    ["editor.version.replaceImage", de.editor.version.replaceImage],
    ["editor.version.uploadImage", de.editor.version.uploadImage],
    ["editor.version.createTitle", de.editor.version.createTitle],
    ["editor.version.createLead", de.editor.version.createLead],
    ["editor.version.versionName", de.editor.version.versionName],
    ["editor.version.pollText", de.editor.version.pollText],
    ["editor.version.noPtLines", de.editor.version.noPtLines],
    ["editor.settings.scale", de.editor.settings.scale],
    ["map.pickHint", de.map.pickHint],
    ["map.clearSelection", de.map.clearSelection],
    ["map.noGraph", de.map.noGraph],
  ];

  it.each(keys)("%s is set", (_name, value) => {
    expect(value).toBeTruthy();
  });

  it("builds the line summary and the version label from their parts", () => {
    expect(de.editor.ptLine.summary(9, 5)).toBe("9 Kanten, alle 5 min");
    expect(de.editor.ptLine.countTitle(5)).toBe("Linien (5)");
    expect(de.editor.version.current("E2E Berlin - Base")).toBe(
      "Aktuell (E2E Berlin - Base)",
    );
  });
});

describe("the dialog close label", () => {
  it("exists, because every dialog renders it for screen readers", () => {
    expect(de.actions.close).toBe("Schließen");
  });
});
