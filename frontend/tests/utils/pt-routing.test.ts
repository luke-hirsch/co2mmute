import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";

import { findPTRoute } from "@/utils/ptRouting";
import { buildGraph, raw } from "./shipped-map";

/**
 * "Bus & Bahn" on the map people actually play.
 *
 * `ptRouting.ts` is the router a student meets: pick a Gruppe, pick a mode,
 * and this is what decides whether the answer is a route or "keine Verbindung
 * gefunden". Every other test in this tree builds a toy graph, so nothing ever
 * asked the question that matters — can you get from this map's homes to this
 * map's workplaces by public transport at all?
 *
 * On the shipped file before the S5 data pass, six of thirty-six pairs could
 * not: bus line `100` had no edges, so nothing served Brandenburger Tor, and
 * U Potsdamer Platz — the only other station within two kilometres — has no
 * street edge at all, so it cannot be walked to either. `101` broke mid-chain
 * and lost four of its nine stops the same way.
 *
 * The graph is assembled here the way `MapVersionGraphView` assembles it, stop
 * lists included, because the file is the thing under test: a fixture copied
 * out of it would go stale the first time the map changed.
 *
 * ### One version at a time
 *
 * Since S14 the file carries **all eight** versions of the map, and a line's
 * route is written per route rather than per version (`chains`). So a graph is
 * a filter over the file and this builder needs to be told which version to
 * cut: nodes, edges and lines each carry their own `versions`, and a line takes
 * the one chain that names the version being built.
 *
 * This file stopped running entirely when that format landed — `raw_line.edges`
 * became `undefined` and the `.map` over it threw at import, so vitest reported
 * a failed *suite* and every assertion below silently left the count. That is
 * the failure mode CLAUDE.md names: read the test count, not OK/FAILED.
 */


/** The base version — the one a game starts on before the class votes. */
const BASE = raw.versions.findIndex((v) => v.base_version) >= 0
  ? raw.versions.findIndex((v) => v.base_version)
  : 0;
const graph = buildGraph(raw, BASE);

/** The six `home` nodes and the six `workplace` nodes, by name. */
const HOMES = Object.fromEntries(
  raw.nodes
    .filter((n) => (n.types ?? []).includes("home"))
    .map((n) => [n.name, Number(n.id)]),
);
const WORKPLACES = Object.fromEntries(
  raw.nodes
    .filter((n) => (n.types ?? []).includes("workplace"))
    .map((n) => [n.name, Number(n.id)]),
);

describe("bus & bahn on Berlin Mitte-West", () => {
  // The router narrates itself to the console on every call, and 36 of them
  // bury the run. Silenced here rather than in the source: a student's browser
  // console is the one place those lines are worth something.
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
    quiet.push(vi.spyOn(console, "warn").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  it("knows the map it is testing", () => {
    expect(Object.keys(HOMES)).toHaveLength(6);
    expect(Object.keys(WORKPLACES)).toHaveLength(6);
    expect(graph.bus_lines.map((l) => l.name)).toEqual([
      "100",
      "100 reverse",
      "101",
      "101 reverse",
    ]);
  });

  it("finds a route from every home to every workplace", async () => {
    const failures: string[] = [];
    for (const [home, from] of Object.entries(HOMES)) {
      for (const [work, to] of Object.entries(WORKPLACES)) {
        const result = await findPTRoute(graph, from, to, { scale: graph.scale });
        if (!result.success) failures.push(`${home} → ${work}: ${result.error}`);
      }
    }

    expect(failures).toEqual([]);
  });

  it("puts a bus on the road, not just trains", async () => {
    // Brandenburger Tor is the case the empty `100` cost: a bus stop, a
    // workplace beside it, and no rail within walking distance.
    const result = await findPTRoute(
      graph,
      HOMES["Wohnort 1"],
      WORKPLACES["Arbeit Brandenburger Tor"],
      { scale: graph.scale },
    );

    expect(result.success).toBe(true);
    const lines = result.ptSegments
      .filter((segment) => segment.mode === "bus")
      .map((segment) => segment.ptLineId);
    const bus = graph.bus_lines.find((l) => lines.includes(l.id));
    expect(bus?.name).toBe("100");
  });

  it("rides every line only from one of its stops to the next", async () => {
    // A bus and a train can share an id — they are rows of two tables — and
    // the router once took them for one line: the way home from Brandenburger
    // Tor rode bus `100 reverse` to S Tiergarten and stayed "on line 2" over
    // the Stadtbahn's tracks to Charlottenburg, every segment labelled bus.
    // The simulation then carried those riders to the bus's own terminus.
    const wrong: string[] = [];
    for (const from of [...Object.values(HOMES), ...Object.values(WORKPLACES)]) {
      const targets = Object.values(HOMES).includes(from) ? WORKPLACES : HOMES;
      for (const to of Object.values(targets)) {
        const result = await findPTRoute(graph, from, to, { scale: graph.scale });
        for (const segment of result.ptSegments) {
          const pool = segment.mode === "bus" ? graph.bus_lines : graph.train_lines;
          const line = pool.find((l) => l.id === segment.ptLineId);
          const at = line?.stops.indexOf(segment.startNode) ?? -1;
          if (at < 0 || line?.stops[at + 1] !== segment.endNode) {
            wrong.push(
              `${from} → ${to}: ${segment.mode} ${line?.name ?? segment.ptLineId} ` +
                `${segment.startNode} → ${segment.endNode}`,
            );
          }
        }
      }
    }

    expect(wrong).toEqual([]);
  });
});

/**
 * The same question, asked of every version the class can vote its way into.
 *
 * Until S16 the box's map had one version in the repo and the other seven only
 * in a database, so this could not be asked at all — and the two bugs S15 fixed
 * are exactly the ones it catches. A line's chain was not version-scoped, so
 * drawing `Busspuren` moved buslinie `100` onto the cloned street in *every*
 * version and left the base one reaching 0 of its 7 edges; and
 * `GenerateCombinationsView` never copied `TrainLine`, so a generated
 * combination had no rail at all.
 *
 * Both are the kind of damage a player meets as "keine Verbindung gefunden" on
 * a map that looks right on screen. Per version, so a failure names the ballot
 * option that broke rather than the map.
 */
describe("every version of the map keeps its public transport", () => {
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
    quiet.push(vi.spyOn(console, "warn").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  it("has the eight versions S16 put in the repo", () => {
    expect(raw.versions.map((v) => v.name)).toEqual([
      "Berlin Mitte-West - Base",
      "Busspuren",
      "Buslinie",
      "Umgehungsstraßen",
      "Buslinie + Umgehungsstraßen",
      "Busspuren + Umgehungsstraßen",
      "Buslinie + Busspuren",
      "Buslinie + Busspuren + Umgehungsstraßen",
    ]);
  });

  it.each(raw.versions.map((v, index) => [index, v.name] as const))(
    "connects every home to every workplace in version %i (%s)",
    async (version) => {
      const versionGraph = buildGraph(raw, version);

      // A line in the version must have a route in it. This is the assertion
      // that fails on a chain the cloning moved somewhere else.
      const routeless = [
        ...versionGraph.bus_lines,
        ...versionGraph.train_lines,
      ].filter((line) => line.edges.length === 0);
      expect(routeless.map((l) => l.name)).toEqual([]);

      // And rail has to survive a generated combination, which is the second
      // bug: `Buslinie + Busspuren` and friends were built without any.
      expect(versionGraph.train_lines.length).toBeGreaterThan(0);

      const failures: string[] = [];
      for (const [home, from] of Object.entries(HOMES)) {
        for (const [work, to] of Object.entries(WORKPLACES)) {
          const result = await findPTRoute(versionGraph, from, to, {
            scale: versionGraph.scale,
          });
          if (!result.success) failures.push(`${home} → ${work}: ${result.error}`);
        }
      }
      expect(failures).toEqual([]);
    },
  );
});
