import { describe, expect, it } from "vitest";

import {
  TRACE_DURATION_MS,
  createTraceRecorder,
  traceStepMs,
} from "@/lib/map/search-trace";
import { dijkstra } from "@/utils/pathfinding";
import type { MapGraph } from "@/types/mapTypes";
import type { PathfindingState } from "@/types/routeTypes";

const state = (edges: number[]) =>
  ({ exploredEdges: new Set(edges) }) as unknown as PathfindingState;

describe("createTraceRecorder", () => {
  it("records only what is new at each step, in order", () => {
    const recorder = createTraceRecorder(7);
    recorder.onStateChange(state([1, 2]));
    recorder.onStateChange(state([1, 2, 5]));
    recorder.onStateChange(state([1, 2, 5, 3, 4]));
    const trace = recorder.trace();
    expect(trace.agentId).toBe(7);
    expect(trace.steps).toEqual([[1, 2], [5], [3, 4]]);
  });

  it("does not make a step of a settled node that examined nothing new", () => {
    const recorder = createTraceRecorder(1);
    recorder.onStateChange(state([1]));
    recorder.onStateChange(state([1]));
    expect(recorder.trace().steps).toEqual([[1]]);
  });
});

it("gives every search its own id", () => {
  expect(createTraceRecorder(1).trace().id).not.toBe(createTraceRecorder(1).trace().id);
});

describe("traceStepMs", () => {
  it("spreads a short search over the whole replay, at a pace you can follow", () => {
    expect(traceStepMs(20)).toBe(70);
    expect(traceStepMs(4) * 4).toBe(TRACE_DURATION_MS);
  });

  it("does not blink through a very short one (F3)", () => {
    // At 120 ms a step, a commute of two or three links was over in a quarter
    // of a second, which is what "missing or too fast" was.
    expect(traceStepMs(2)).toBe(350);
    expect(traceStepMs(2) * 2).toBeGreaterThanOrEqual(TRACE_DURATION_MS / 2);
  });

  it("hurries a big search up to one frame a step, no further", () => {
    expect(traceStepMs(5000)).toBe(16);
    // Past ~87 steps the one-frame floor wins and the replay runs long; the
    // shipped map settles about fifty nodes, so it never gets there.
    expect(traceStepMs(50) * 50).toBeLessThanOrEqual(TRACE_DURATION_MS);
  });

  it("has nothing to play for an empty trace", () => {
    expect(traceStepMs(0)).toBe(0);
  });
});

describe("against the real router", () => {
  // 1 → 2 → 3 along the street, and a dead-end spur 2 → 4 that Dijkstra still
  // has to look at before it can say 3 is the nearest thing left.
  const node = (id: number, x: number) => ({ id, x_position: x, y_position: 0 });
  const street = (id: number, from: number, to: number) => ({
    id,
    start_node: from,
    end_node: to,
    distance_m: 100,
    street_edge: { speed_limit: 50, lanes: 1, dedicated_bus_lane: false },
  });
  const graph = {
    nodes: [node(1, 0), node(2, 1), node(3, 2), node(4, 1)],
    edges: [street(10, 1, 2), street(11, 2, 3), street(12, 2, 4)],
  } as unknown as MapGraph;

  it("replays every link it examined, and the route is among them", async () => {
    const recorder = createTraceRecorder(1);
    const result = await dijkstra(graph, 1, 3, "car", {
      onStateChange: recorder.onStateChange,
    });
    expect(result.success).toBe(true);
    const examined = recorder.trace().steps.flat();
    for (const segment of result.segments) {
      expect(examined).toContain(segment.edgeId);
    }
    expect(new Set(examined).size).toBe(examined.length);
  });
});
