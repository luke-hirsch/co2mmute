import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";

import { findPTRoute } from "@/utils/ptRouting";
import type { Edge, Node } from "@/types/mapTypes";
import type { ExtendedMapGraph, PTLine } from "@/types/routeTypes";

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
 * On the shipped file before its data pass, six of thirty-six pairs could
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
 * The file carries **all eight** versions of the map, and a line's
 * route is written per route rather than per version (`chains`). So a graph is
 * a filter over the file and this builder needs to be told which version to
 * cut: nodes, edges and lines each carry their own `versions`, and a line takes
 * the one chain that names the version being built.
 *
 * This file stopped running entirely when that format landed — `raw_line.edges`
 * became `undefined` and the `.map` over it threw at import, so vitest reported
 * a failed *suite* and every assertion below silently left the count. That is
 * why a run is read by its test count, not by OK/FAILED.
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
 * Until 2026-09-28 the box's map had one version in the repo and the other
 * seven only in a database, so this could not be asked at all — and the two
 * versioning bugs fixed then are exactly the ones it catches. A line's chain
 * was not version-scoped, so drawing `Busspuren` moved buslinie `100` onto the
 * cloned street in *every* version and left the base one reaching 0 of its 7
 * edges; and `GenerateCombinationsView` never copied `TrainLine`, so a
 * generated combination had no rail at all.
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

  it("has the eight versions of the box's map", () => {
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

/**
 * A ride is as long as its track, not as the straight line between its stops.
 *
 * The simulation plays a ride over `Edge.length_m` — the straight line × the
 * map's scale × `circuity` — and the graph sends that as `distance_m`. A map
 * built from OSM gives its rail edges the bends of the real track, so a router
 * that priced a ride by the straight line would send a class onto a line the
 * simulation then plays three times as long.
 *
 * Two stations a kilometre apart, two ways between them: a train over a track
 * that bends to three kilometres, and a bus on a straight street.
 */
describe("a ride on a bent track", () => {
  const station = [{ id: 1, name: "station", short: "S" }];
  const S: Node = { id: 1, name: "S", x_position: 0, y_position: 0, node_type: station };
  const T: Node = { id: 2, name: "T", x_position: 1, y_position: 0, node_type: station };
  const track: Edge = {
    id: 20,
    name: "Gleis",
    start_node: 1,
    end_node: 2,
    walking: false,
    biking: false,
    circuity: 3,
    distance_m: 3000,
    street_edge: null,
    train_edge: { id: 20 },
  };
  const street: Edge = {
    id: 21,
    name: "Straße",
    start_node: 1,
    end_node: 2,
    walking: true,
    biking: true,
    circuity: 1,
    distance_m: 1000,
    street_edge: { id: 21, speed_limit: 50, lanes: 2, dedicated_bus_lane: false },
  };
  const train: PTLine = {
    id: 2, name: "S1", type: "train", interval: 10, capacity: 1000, speed_kmh: 40,
    edges: [20], stops: [1, 2],
  };
  const bus: PTLine = {
    id: 2, name: "100", type: "bus", interval: 10, capacity: 85, speed_kmh: 30,
    edges: [21], stops: [1, 2],
  };
  const graphWith = (lines: { bus: PTLine[]; train: PTLine[] }) =>
    ({
      nodes: [S, T],
      edges: [track, street],
      bus_lines: lines.bus,
      train_lines: lines.train,
      scale: 1000,
    }) as unknown as ExtendedMapGraph;

  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  it("takes as long as the track: 3 km at 40 km/h is 4.5 minutes", async () => {
    const result = await findPTRoute(graphWith({ bus: [], train: [train] }), 1, 2, {
      scale: 1000,
    });

    expect(result.success).toBe(true);
    expect(result.ptSegments).toHaveLength(1);
    expect(result.ptSegments[0].distanceM).toBe(3000);
    expect(result.ptSegments[0].estimatedTimeMin).toBeCloseTo(4.5);
  });

  it("takes the bus when the track's bends make the train slower", async () => {
    // By the straight line the train is 1.5 minutes and the bus 2; by the
    // track the train is 4.5.
    const result = await findPTRoute(graphWith({ bus: [bus], train: [train] }), 1, 2, {
      scale: 1000,
    });

    expect(result.success).toBe(true);
    expect(result.ptSegments.map((s) => s.mode)).toEqual(["bus"]);
  });
});

/** A toy map: nodes on a line, streets both ways, lines over them. */
const stopType = [{ id: 1, name: "bus_stop", short: "H" }];
const at = (id: number, x: number, stop = false): Node => ({
  id,
  name: `N${id}`,
  x_position: x,
  y_position: 0,
  node_type: stop ? stopType : [],
});
const street = (id: number, from: number, to: number, metres: number): Edge[] =>
  [
    [id, from, to],
    [id + 1, to, from],
  ].map(([edgeId, start, end]) => ({
    id: edgeId,
    name: `Straße ${id}`,
    start_node: start,
    end_node: end,
    walking: true,
    biking: true,
    circuity: 1,
    distance_m: metres,
    street_edge: { id: edgeId, speed_limit: 50, lanes: 2, dedicated_bus_lane: false },
  }));
const busLine = (id: number, name: string, stops: number[], edges: number[], kmh = 30): PTLine => ({
  id, name, type: "bus", interval: 10, capacity: 85, speed_kmh: kmh, edges, stops,
});
const toyGraph = (nodes: Node[], edges: Edge[], bus: PTLine[]) =>
  ({ nodes, edges, bus_lines: bus, train_lines: [], scale: 1000 }) as unknown as ExtendedMapGraph;

/**
 * The walk at the end of a trip is part of the search, not a check after it.
 *
 * Two lines leave the same stop. The fast one sets you down 2.5 km from the
 * workplace, further than the 2 km anybody walks from a stop; the slow one
 * 500 m from it. Checked only once the search was over, the fast line won the
 * search and was then refused, and the slow one that does arrive was never
 * offered: no route at all. On the built box that was 192 of 1 519 pairs.
 */
describe("the last walk", () => {
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  // home 1 (a stop) — fast to 2, 2.5 km from work 4; slow to 3, 500 m from it.
  const nodes = [at(1, 0, true), at(2, 1, true), at(3, 3, true), at(4, 3.5)];
  const edges = [
    ...street(10, 1, 2, 1_000),
    ...street(20, 1, 3, 10_000),
    ...street(30, 2, 4, 2_500),
    ...street(40, 3, 4, 500),
  ];
  const fast = busLine(1, "1", [1, 2], [10]);
  const slow = busLine(2, "2", [1, 3], [20], 15);

  it("takes the slower line when the faster one ends too far away", async () => {
    const result = await findPTRoute(toyGraph(nodes, edges, [fast, slow]), 1, 4, {
      scale: 1000,
    });

    expect(result.success).toBe(true);
    expect(result.ptSegments.map((s) => s.ptLineName)).toEqual(["2"]);
    expect(result.walkFromStation.reduce((m, s) => m + s.distanceM, 0)).toBe(500);
  });

  it("rides: getting on and off at the same stop is no trip", async () => {
    // Home 5 is 500 m from stop 1, work 6 is 1 km from it, and line 3 takes
    // 24 minutes to stop 3, 500 m from work. Getting on and straight off at
    // stop 1 and walking on was quicker, and the router answered a walk under
    // the Bus & Bahn label — the walk a player did not pick.
    const more = [...nodes, at(5, -0.5), at(6, 1)];
    const roads = [...edges, ...street(50, 5, 1, 500), ...street(60, 1, 6, 1_000),
      ...street(70, 3, 6, 500)];
    const crawl = busLine(3, "3", [1, 3], [20], 25);
    const result = await findPTRoute(toyGraph(more, roads, [crawl]), 5, 6, {
      scale: 1000,
    });

    expect(result.success).toBe(true);
    expect(result.ptSegments.map((s) => s.ptLineName)).toEqual(["3"]);
  });

  it("keeps the first walk within 2 km too", async () => {
    // Stop 2 is 1 km from home 1, stop 3 is 3 km, and only line 4 from stop 3
    // goes anywhere. Before the first ride the walk only reaches stops within
    // 2 km, after one it may go on; on and straight off at stop 2 made the
    // walk to stop 3 an after-a-ride one. On the built box 48 trips walked
    // 2.7 to 5.5 km to their first train that way.
    const ends = [at(1, 0), at(2, 1, true), at(3, 3, true), at(4, 8, true), at(5, 8.1)];
    const roads = [
      ...street(10, 1, 2, 1_000),
      ...street(20, 2, 3, 2_000),
      ...street(30, 3, 4, 5_000),
      ...street(40, 4, 5, 100),
    ];
    const nowhere = busLine(1, "1", [2, 1], [11]);
    const away = busLine(2, "4", [3, 4], [30]);
    const result = await findPTRoute(toyGraph(ends, roads, [nowhere, away]), 1, 5, {
      scale: 1000,
    });

    expect(result.success).toBe(false);
  });

  it("still finds nothing when every stop is too far away", async () => {
    const result = await findPTRoute(toyGraph(nodes, edges, [fast]), 1, 4, {
      scale: 1000,
    });

    expect(result.success).toBe(false);
  });
});

/**
 * A bus is boarded at its stops, and at the junctions where it meets another
 * line, so that a change there works. Its own way back is not another line.
 *
 * A line drawn both ways is two rows, `7` and `7 reverse`, and the router
 * counted them as two lines: every junction between two stops became a place
 * to get on and off, and a home beside one boarded at the door. Built maps
 * have dozens (box 6, Bremen 101, Berlin 136); the shipped map none.
 */
describe("where a bus can be boarded", () => {
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  // stop 1 — junction 2 — stop 3 on the line, 1 km and 5 km apart; home 4 is
  // 100 m from the junction, work 5 is 100 m from stop 3, too far to walk.
  const nodes = [at(1, 0, true), at(2, 1), at(3, 6, true), at(4, 1.1), at(5, 6.1)];
  const edges = [
    ...street(10, 1, 2, 1_000),
    ...street(20, 2, 3, 5_000),
    ...street(30, 4, 2, 100),
    ...street(40, 3, 5, 100),
  ];

  it.each(["7 reverse", "7 Reverse"])(
    "not at a junction only the line's way back (%s) passes",
    async (back) => {
      const there = busLine(1, "7", [1, 2, 3], [10, 20]);
      const home = busLine(2, back, [3, 2, 1], [21, 11]);
      const result = await findPTRoute(toyGraph(nodes, edges, [there, home]), 4, 5, {
        scale: 1000,
      });

      expect(result.success).toBe(true);
      expect(result.ptSegments[0].startNode).toBe(1);
    },
  );

  it("at a junction two lines share, both ways, so a change works", async () => {
    // Line 8 runs from the junction to stop 6; work is beside 6, home beside
    // stop 1. The only way is 7 to the junction and 8 from there.
    const more = [...nodes, at(6, 1, true), at(7, 1.1)];
    const roads = [...edges, ...street(50, 2, 6, 1_000), ...street(60, 6, 7, 100)];
    const lines = [
      busLine(1, "7", [1, 2, 3], [10, 20]),
      busLine(2, "7 reverse", [3, 2, 1], [21, 11]),
      busLine(3, "8", [2, 6], [50]),
      busLine(4, "8 reverse", [6, 2], [51]),
    ];
    const result = await findPTRoute(toyGraph(more, roads, lines), 1, 7, {
      scale: 1000,
    });

    expect(result.success).toBe(true);
    expect(result.ptSegments.map((s) => s.ptLineName)).toEqual(["7", "8"]);
  });
});

/**
 * A line can pass one stop twice, and a ride is on one pass of it.
 *
 * Bremen's 58 runs from Roland-Center out to Sodenmatt, round Huchting, back
 * through Sodenmatt and home. The router knew a ride only by the node it was
 * at, so from the second pass at Sodenmatt it rode on into the first, round
 * the loop again, a ride no bus makes. A line that ends where it starts goes
 * on round, and waits at its end for the timetable's next departure, like a
 * change (Lukas, 2026-10-14: "ring can be ring").
 */
describe("a line that passes a stop twice", () => {
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  // 1 → 2 → round 5 and 6 → 2 → 4, a kilometre a stretch, 2.5 km from 5 to
  // 6 and 3 km to 4. Home 8 is 100 m from 6, work 9 100 m from 5, too far to
  // walk to 5 and ride to 6 the right way. Only 5, 6 and 4 are stops, and
  // junction 2 when asked: the one way onto the pass to 5 is a change there.
  const loop = (junctionIsAStop: boolean) => {
    const nodes = [at(1, 0), at(2, 1, junctionIsAStop), at(5, 2, true),
      at(6, 1.5, true), at(4, 4, true), at(8, 1.6), at(9, 2.1)];
    const edges = [
      ...street(10, 1, 2, 1_000),
      ...street(20, 2, 5, 1_000),
      ...street(30, 5, 6, 2_500),
      ...street(40, 6, 2, 1_000),
      ...street(50, 2, 4, 3_000),
      ...street(60, 8, 6, 100),
      ...street(70, 9, 5, 100),
    ];
    return toyGraph(nodes, edges, [busLine(7, "7", [1, 2, 5, 6, 2, 4], [10, 20, 30, 40, 50])]);
  };

  it("does not ride on from one pass into the other", async () => {
    const result = await findPTRoute(loop(false), 8, 9, { scale: 1000 });

    expect(result.success).toBe(false);
  });

  it("changes at the stop to ride the other pass, and waits for it", async () => {
    const result = await findPTRoute(loop(true), 8, 9, { scale: 1000 });

    expect(result.success).toBe(true);
    expect(result.ptSegments.map((s) => [s.startNode, s.endNode])).toEqual([[6, 2], [2, 5]]);
    // Two boardings of a bus every ten minutes, five minutes each.
    expect(result.waitTimeMin).toBe(10);
  });

  it("goes on round a line that ends where it starts", async () => {
    // A ring 1 → 2 → 3 → 4 → 1, a kilometre a stretch. Home 6 is 100 m from
    // 3, work 7 100 m from 2: 3 → 4 → 1 → 2, on over 1, where it waits for
    // the next departure.
    const nodes = [at(1, 0, true), at(2, 1, true), at(3, 2, true), at(4, 1, true),
      at(6, 2.1), at(7, 1.1)];
    const edges = [
      ...street(10, 1, 2, 1_000),
      ...street(20, 2, 3, 1_000),
      ...street(30, 3, 4, 1_000),
      ...street(40, 4, 1, 1_000),
      ...street(50, 6, 3, 100),
      ...street(60, 7, 2, 100),
    ];
    const ring = busLine(9, "9", [1, 2, 3, 4, 1], [10, 20, 30, 40]);
    const result = await findPTRoute(toyGraph(nodes, edges, [ring]), 6, 7, { scale: 1000 });

    expect(result.success).toBe(true);
    expect(result.ptSegments.map((s) => [s.startNode, s.endNode])).toEqual([
      [3, 4],
      [4, 1],
      [1, 2],
    ]);
    expect(result.waitTimeMin).toBe(10);
  });
});

/**
 * "wenig umsteigen" is a preference of the search, not time anybody spends.
 *
 * Every boarding after the first costs it 30 extra minutes, so a route with a
 * change loses to one without. Those minutes went into the wait the screen
 * shows: one change between two buses read 22 minutes as "schnellste" and 52
 * as "wenig umsteigen", for the same route.
 */
describe("the change penalty", () => {
  const quiet: ReturnType<typeof vi.spyOn>[] = [];
  beforeAll(() => {
    quiet.push(vi.spyOn(console, "log").mockImplementation(() => {}));
  });
  afterAll(() => quiet.forEach((spy) => spy.mockRestore()));

  // Home is stop 1, work stop 3. Bus 1 runs 1 → 2, bus 2 runs 2 → 3, 3 km each
  // at 30 km/h, every ten minutes: 5 + 6 + 5 + 6 = 22 minutes, one change at 2.
  const nodes = [at(1, 0, true), at(2, 3, true), at(3, 6, true)];
  const edges = [...street(10, 1, 2, 3_000), ...street(20, 2, 3, 3_000)];
  const graph = toyGraph(nodes, edges, [
    busLine(1, "1", [1, 2], [10]),
    busLine(2, "2", [2, 3], [20]),
  ]);

  it("is not in the time of the route it picks", async () => {
    const fastest = await findPTRoute(graph, 1, 3, { scale: 1000, ptOptimization: "fastest" });
    const fewest = await findPTRoute(graph, 1, 3, {
      scale: 1000,
      ptOptimization: "fewest_transfers",
    });

    expect(fewest.ptSegments.map((s) => s.ptLineId)).toEqual([1, 2]);
    expect(fastest.totalTimeMin).toBe(22);
    expect(fewest.totalTimeMin).toBe(22);
    expect(fewest.waitTimeMin).toBe(10);
  });
});
