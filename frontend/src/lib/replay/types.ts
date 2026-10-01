/**
 * The replay wire format, as `game/views_rest.py:RoundReplayView` serves it.
 *
 * Two layers in one fetch, which is the backend's decision and worth knowing
 * here: `ticks` is the **street** — how full each link was at the end of each
 * simulated tick — and `replay.dots` is the **people**, a sample of the
 * population with a continuous trajectory each. The animation draws both, and
 * they are measured differently: a tick is a bucket, a leg is a float.
 *
 * `replay` is null for every round simulated before the recorder existed
 * (`game/0015`). That round keeps its numbers and loses its animation; nothing
 * about it is an error.
 */

import type { TransportMode } from "@/lib/de";

/**
 * What a dot is doing between two of its events.
 *
 * - `"e"` — crossing edge `ref`, entered at node `fromNode`
 * - `"s"` — standing at node `ref`, waiting for a line
 * - `"r"` — riding vehicle `ref`, so its position IS that vehicle's
 */
export type ReplayLegKind = "e" | "s" | "r";

/**
 * `[kind, ref, fromMin, toMin, fromNode]`.
 *
 * A tuple rather than an object because there are up to five hundred of these
 * per dot and the payload is the biggest thing the game sends over school wifi.
 *
 * `fromNode` is the only thing that says which way a dot crosses a link — an
 * edge is stored in either direction, so reading `start_node` off the graph
 * draws half the map's traffic backwards. It is null where the route's edges did
 * not connect, and then the leg is drawn undirected rather than guessed at.
 */
export type ReplayLeg = [
  kind: ReplayLegKind,
  ref: number,
  fromMin: number,
  toMin: number,
  fromNode: number | null,
];

/**
 * How a trip ended.
 *
 * - `arrived` — got there
 * - `stranded` — never travelled at all, because the map data asks a line to
 *   serve a stop its edges do not reach. Since `pt-service-period` there is no
 *   service cap, so a full bus is a wait and never this.
 * - `unfinished` — was still moving when the clock stopped
 *
 * The beat card at the end of the animation may only say everybody made it when
 * every dot says `arrived`.
 */
export type ReplayEnd = "arrived" | "stranded" | "unfinished";

/**
 * The mode a dot is drawn in.
 *
 * A person carries their `AgentRoute.transport_mode`; a line vehicle carries
 * `"bus"` or `"train"`, because that is what the line is. Both collapse onto the
 * four design lines through `designMode` — the palette has four and only four.
 */
export type ReplayMode = TransportMode | "bus" | "train";

/** A person, or a line vehicle. `line` is what tells them apart. */
export type ReplayDot = {
  /** The simulator's vehicle id. Unique within the round; `"r"` legs name it. */
  id: number;
  /** `AgentRoute` pk, or null for a line vehicle. */
  route: number | null;
  /**
   * The Gruppe number on the route this dot came from.
   *
   * Carried because the payload carries it, and read by nothing on screen. The
   * animation deliberately does not say whose dot a dot is: what the class needs
   * to see is *the traffic* — where it jams, who is queuing for a bus — and
   * `AgentRoute.agent_id` is unique per submitted move anyway, so every player in
   * the room has a Gruppe 1 and the number alone could not answer the question.
   */
  agent: number | null;
  /** The line's name ("M1"), or null for a person. */
  line: string | null;
  mode: ReplayMode;
  /**
   * When this person wanted to leave. The gap between `wants` and `legs[0]` is
   * the queue at their own front door — people the street had no room for. No
   * instrument in this project could see that until `stau-sichtbar`, and it is
   * the most explanatory thing the animation draws.
   */
  wants: number;
  legs: ReplayLeg[];
  end: ReplayEnd;
};

/**
 * Who did not get there, in **people**, as the simulator booked them.
 *
 * `unfinished` includes the people still at their front door when the clock
 * stopped, who have no dot; `stranded` is the map-data ending (see `ReplayEnd`).
 */
export type ReplayEndings = { unfinished: number; stranded: number };

export type Replay = {
  /** `REPLAY_FORMAT_VERSION`. A payload from a newer format is not drawn. */
  version: number;
  /**
   * How many real people one person-dot stands for, as sampled — about ten
   * since S25 (fifty before), and a fraction when the stride does not divide a
   * Gruppe. Printed rounded (`lib/replay/counts.ts:dotScale`).
   */
  people_per_dot: number;
  /**
   * The simulator's own count of who did not arrive. Added inside format 1 in
   * S25, so a recording from before has none and the sample answers instead.
   */
  endings?: ReplayEndings;
  tick_duration_min: number;
  window_min: number;
  /**
   * The last moment anything happened, in minutes from the start of the
   * departure window. Since `pt-service-period` removed the service cap this
   * varies by a factor of six between rounds of the same game, which is exactly
   * why the playback budget normalises to it instead of assuming a span.
   */
  end_min: number;
  dots: ReplayDot[];
};

/** `[edge_id, vehicle_count, waiting_count, speed_kmh]`. */
export type ReplayEdgeRow = [
  edgeId: number,
  vehicles: number,
  waiting: number,
  speedKmh: number,
];

/** One simulated tick of the street layer. `t` is the tick index, not a minute. */
export type ReplayTick = { t: number; edges: ReplayEdgeRow[] };

export type ReplayPayload = {
  round_number: number;
  tick_duration_min: number;
  people_per_agent: number;
  replay: Replay | null;
  ticks: ReplayTick[];
};

/** The version this build knows how to draw. */
export const REPLAY_FORMAT_VERSION = 1;

/**
 * The four lines a mode can be drawn as.
 *
 * A bus and a train are both `public`: the palette is two colours and ink, and
 * `components/metro/mode.ts` is the only place a mode gets a look. Splitting the
 * PT line in two here would be a fifth colour by the back door.
 */
export function designMode(mode: ReplayMode): TransportMode {
  return mode === "bus" || mode === "train" ? "public" : mode;
}

/** True for a line vehicle — a bus or a train, not a person. */
export function isVehicleDot(dot: ReplayDot): boolean {
  return dot.line !== null;
}
