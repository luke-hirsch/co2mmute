import type { PathfindingState } from "@/types/routeTypes";

/**
 * What the router looked at, in the order it looked (S24).
 *
 * `dijkstra` already reports its progress through `onStateChange`. The route is
 * found at once — a 170-link map is a few milliseconds — and the *picture* of the
 * search is played afterwards, so nothing waits on an animation: the route, the
 * summary and the send button are all there from the first frame. Slowing the
 * search itself (`animationDelayMs`) would have put three seconds between a tap
 * and an answer.
 *
 * One step is the links first examined while settling one node; a step that
 * examined nothing new is not a step.
 */
export type SearchTrace = {
  /** Distinct per search, so a viewer can tell a new one from a re-render. */
  id: number;
  agentId: number;
  steps: number[][];
};

let nextId = 0;

export function createTraceRecorder(agentId: number) {
  const id = ++nextId;
  const steps: number[][] = [];
  let seen = 0;

  return {
    onStateChange(state: PathfindingState) {
      if (state.exploredEdges.size <= seen) return;
      // A Set iterates in insertion order, so what is new is what is past `seen`.
      steps.push([...state.exploredEdges].slice(seen));
      seen = state.exploredEdges.size;
    },
    trace(): SearchTrace {
      return { id, agentId, steps };
    },
  };
}

/** The whole replay lasts about this long, however big the map is. */
export const TRACE_DURATION_MS = 1400;

/** Never faster than a frame, never slower than a person can follow. */
export function traceStepMs(steps: number): number {
  if (steps <= 0) return 0;
  return Math.min(120, Math.max(16, TRACE_DURATION_MS / steps));
}
