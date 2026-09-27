/**
 * The morning, drawn.
 *
 * ### Why this is a third renderer
 *
 * `GameMapViewer` carries routes, Dijkstra, selection and a heatmap;
 * `MapViewer` carries selection; this one carries a clock, a few hundred moving
 * things and no interaction at all. The two existing viewers were deliberately
 * not merged because they share *concerns* and not a shape, and the argument is
 * stronger here — extending one of them would produce a component with the union
 * of three prop sets. So this shares the extracted concern (`lib/map/view-box.ts`)
 * and nothing else.
 *
 * ### Why an animation and not the heatmap
 *
 * A heatmap has no time axis, so "how bad" has to become hue — and a hue ramp is
 * exactly what a two-colour palette does not have. `getCongestionColor` sits in
 * `GameMapViewer` in open violation of the design rules, unused because nothing
 * ever passed the prop.
 *
 * An animation needs no ramp. **A jam is dots that stop moving.** Motion carries
 * congestion, which frees colour to carry mode — the one categorical axis this
 * project allows. So: link occupancy is stroke weight, a crowd is a cluster at a
 * node, and nothing about congestion is ever a colour.
 *
 * ### Nobody's dots are anybody's
 *
 * Lukas, 2026-09-27: the class needs to see *the traffic* — that it jams here,
 * that people are queuing for a bus there — and not where each person came from.
 * So every dot is drawn alike, the whole room's together, and no dot is marked as
 * belonging to this device. That is also why nothing here reads `dot.agent`.
 *
 * ### What the frame loop may and may not do
 *
 * `draw()` is called from a `requestAnimationFrame` loop and **never touches React
 * state**. It writes `transform` and a handful of geometry attributes straight onto
 * elements React rendered once. No CSS transitions either: five hundred transitions
 * is the same WebKit cliff by another route, and positions come from the warp every
 * frame anyway, so there is nothing for the browser to interpolate.
 */

import { useCallback, useImperativeHandle, useMemo, useRef, type Ref } from "react";

import { imageRect, viewBox, type ImageFields } from "@/lib/map/view-box";
import { modeStyle } from "@/components/metro/mode";
import {
  makeCursors,
  positionAt,
  resetCursors,
  type ReplayPosition,
} from "@/lib/replay/positions";
import {
  doorNodeByEdge,
  waitingByNode,
  type StreetFill,
} from "@/lib/replay/street-fill";
import { designMode, type Replay, type ReplayDot } from "@/lib/replay/types";
import { de } from "@/lib/de";
import type { ExtendedMapGraph } from "@/types/routeTypes";

export type ReplayCanvasHandle = {
  draw: (minute: number, jumped: boolean) => void;
};

/** Map units. The view box is `x_dim × 100`, so the shipped map is ~1300 across. */
const NODE_R = 7;
const DOT_R = 8;
const VEHICLE_W = 26;
const VEHICLE_H = 15;
const TRAIN_W = 36;

/**
 * A crowd's radius from the number of people in it, absolutely and not relative to
 * the round's own peak: 400 people have to look like 400 people in round 1 and in
 * round 5, because comparing the rounds is the game.
 */
const CROWD_BASE_R = 9;
const CROWD_PER_SQRT_PERSON = 1.6;
const CROWD_MAX_R = 90;
/** Below this the halo is drawn without a number — a label per node is noise. */
const CROWD_LABEL_MIN = 120;

/** How wide a link gets between empty and packed to its storage capacity. */
const FILL_MIN_W = 3;
const FILL_MAX_EXTRA_W = 15;

/** `133 × car_lanes × km` — the storage capacity of the link queue model. */
const VEHICLES_PER_LANE_KM = 133;

/** Golden angle, so scattered dots never line up however many there are. */
const GOLDEN_ANGLE = 2.399963229728653;

type EdgeGeometry = {
  x1: number;
  y1: number;
  dx: number;
  dy: number;
  /** Unit perpendicular, for spreading a queue across the street. */
  px: number;
  py: number;
  startNode: number;
  endNode: number;
  /** Vehicles this link holds when it is full. */
  storage: number;
  isRail: boolean;
};

/** Everything the frame loop mutates. Sized to the round, reused every frame. */
type Scratch = {
  personShown: Uint8Array;
  vehicleShown: Uint8Array;
  crowdShown: Uint8Array;
  /** The number last written into a crowd's label, so the text is not rewritten. */
  crowdLabel: Float64Array;
  fillShown: Uint8Array;
  vehiclePositions: Map<number, { x: number; y: number }>;
  standingDots: Map<number, number>;
};

function makeScratch(
  persons: number,
  vehicles: number,
  nodes: number,
  fillEdges: number,
): Scratch {
  return {
    personShown: new Uint8Array(persons),
    vehicleShown: new Uint8Array(vehicles),
    crowdShown: new Uint8Array(nodes),
    crowdLabel: new Float64Array(nodes).fill(-1),
    fillShown: new Uint8Array(fillEdges),
    vehiclePositions: new Map(),
    standingDots: new Map(),
  };
}

export function ReplayCanvas({
  graph,
  replay,
  fill,
  ref,
}: {
  graph: ExtendedMapGraph;
  replay: Replay;
  fill: StreetFill;
  ref?: Ref<ReplayCanvasHandle>;
}) {
  const nodes = useMemo(
    () =>
      graph.nodes.map((node) => ({
        id: node.id,
        x: node.x_position * 100,
        y: node.y_position * 100,
        isStop: node.node_type.some(
          (type) => type.name === "station" || type.name === "bus_stop",
        ),
      })),
    [graph.nodes],
  );

  const nodeById = useMemo(() => {
    const map = new Map<number, { x: number; y: number }>();
    for (const node of nodes) map.set(node.id, node);
    return map;
  }, [nodes]);

  const edgeGeometry = useMemo(() => {
    const map = new Map<number, EdgeGeometry>();
    for (const edge of graph.edges) {
      const start = nodeById.get(edge.start_node);
      const end = nodeById.get(edge.end_node);
      if (!start || !end) continue;

      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const length = Math.hypot(dx, dy) || 1;

      // A bus lane and a bike lane each take a car lane, floored at zero — and
      // zero is legal: the street becomes a gate, closed to cars and open to
      // buses, bikes and pedestrians. A gate still carries buses, so it is
      // scaled as if it had one lane rather than dividing by nothing.
      const street = edge.street_edge;
      const lanes = street?.lanes ?? 1;
      const taken =
        (street?.dedicated_bus_lane ? 1 : 0) + (edge.bike_lane ? 1 : 0);
      const carLanes = Math.max(lanes - taken, 1);
      const km = (edge.distance_m ?? 0) / 1000;

      map.set(edge.id, {
        x1: start.x,
        y1: start.y,
        dx,
        dy,
        px: -dy / length,
        py: dx / length,
        startNode: edge.start_node,
        endNode: edge.end_node,
        storage: Math.max(VEHICLES_PER_LANE_KM * carLanes * km, 1),
        isRail: !!edge.train_edge && !edge.street_edge,
      });
    }
    return map;
  }, [graph.edges, nodeById]);

  /** People, and line vehicles, kept apart because they are drawn differently. */
  const { persons, vehicles } = useMemo(() => {
    const persons: ReplayDot[] = [];
    const vehicles: ReplayDot[] = [];
    for (const dot of replay.dots) {
      (dot.line === null ? persons : vehicles).push(dot);
    }
    return { persons, vehicles };
  }, [replay.dots]);

  /** Per-dot scatter, drawn from the id so a dot never swaps places with another. */
  const scatter = useMemo(() => {
    const angle = new Float64Array(persons.length);
    const ring = new Float64Array(persons.length);
    const lateral = new Float64Array(persons.length);
    for (let i = 0; i < persons.length; i++) {
      const id = persons[i].id;
      const fraction = (id * 0.6180339887) % 1;
      angle[i] = GOLDEN_ANGLE * id;
      ring[i] = 13 + 12 * fraction;
      lateral[i] = (fraction - 0.5) * 13;
    }
    return { angle, ring, lateral };
  }, [persons]);

  /** Which node a link's front-door queue stands at — the dots know, the tick rows do not. */
  const doorNodeOf = useMemo(() => {
    const learned = doorNodeByEdge(replay.dots);
    return (edgeId: number) =>
      learned.get(edgeId) ?? edgeGeometry.get(edgeId)?.startNode ?? null;
  }, [replay.dots, edgeGeometry]);

  /** Only links that both appear in the recording and exist on this map version. */
  const fillEdges = useMemo(
    () => fill.edgeIds.filter((edgeId) => edgeGeometry.has(edgeId)),
    [fill.edgeIds, edgeGeometry],
  );

  const cursors = useMemo(() => makeCursors(replay.dots), [replay.dots]);

  const personEls = useRef<(SVGCircleElement | null)[]>([]);
  const vehicleEls = useRef<(SVGGElement | null)[]>([]);
  const crowdEls = useRef<(SVGGElement | null)[]>([]);
  const crowdLabelEls = useRef<(SVGTextElement | null)[]>([]);
  const fillEls = useRef<(SVGLineElement | null)[]>([]);

  /**
   * The frame loop's scratch space, in one ref.
   *
   * Two things live in here. **Visibility is tracked** rather than written every
   * frame — five hundred attribute writes for a value that changes twice a round is
   * the cheapest thing to skip — and **the per-frame collections are reused**, so a
   * frame allocates nothing per dot.
   *
   * It is sized inside `draw` and never during render: a ref read while rendering
   * is a real bug in React's own terms, and the sizes only matter to the loop.
   */
  const scratch = useRef<Scratch | null>(null);

  const draw = useCallback(
    (minute: number, jumped: boolean) => {
      if (jumped) resetCursors(cursors);

      let space = scratch.current;
      if (
        !space ||
        space.personShown.length !== persons.length ||
        space.vehicleShown.length !== vehicles.length ||
        space.crowdShown.length !== nodes.length ||
        space.fillShown.length !== fillEdges.length
      ) {
        space = makeScratch(
          persons.length,
          vehicles.length,
          nodes.length,
          fillEdges.length,
        );
        scratch.current = space;
      }
      const {
        personShown,
        vehicleShown,
        crowdShown,
        crowdLabel,
        fillShown,
        vehiclePositions,
        standingDots,
      } = space;

      /** Where a position lands on the map, or null when it is not on screen. */
      const place = (
        position: ReplayPosition,
        index: number,
      ): { x: number; y: number } | null => {
        if (position.kind === "edge") {
          const geometry = edgeGeometry.get(position.edgeId);
          if (!geometry) return null;
          // Direction comes from the leg, never from the edge: an edge is stored
          // in either direction, so reading start_node would draw half the map's
          // traffic backwards. A null entry node is undirected — drawn forwards
          // rather than guessed at.
          const forward =
            position.fromNode === null || position.fromNode !== geometry.endNode;
          const along = forward ? position.progress : 1 - position.progress;
          const lateral = index >= 0 ? scatter.lateral[index] : 0;
          return {
            x: geometry.x1 + geometry.dx * along + geometry.px * lateral,
            y: geometry.y1 + geometry.dy * along + geometry.py * lateral,
          };
        }

        const nodeId =
          position.kind === "node" || position.kind === "waiting"
            ? position.nodeId
            : null;
        if (nodeId === null) return null;
        const node = nodeById.get(nodeId);
        if (!node) return null;
        if (index < 0) return node;
        // Scattered on a ring, so a hundred people standing at one stop read as a
        // crowd instead of one thick dot.
        const radius = scatter.ring[index];
        return {
          x: node.x + Math.cos(scatter.angle[index]) * radius,
          y: node.y + Math.sin(scatter.angle[index]) * radius,
        };
      };

      const show = (
        element: SVGGraphicsElement | null,
        shown: Uint8Array,
        index: number,
        at: { x: number; y: number } | null,
      ) => {
        if (!element) return;
        if (at === null) {
          if (shown[index]) {
            element.setAttribute("visibility", "hidden");
            shown[index] = 0;
          }
          return;
        }
        element.setAttribute(
          "transform",
          `translate(${at.x.toFixed(1)} ${at.y.toFixed(1)})`,
        );
        if (!shown[index]) {
          element.setAttribute("visibility", "visible");
          shown[index] = 1;
        }
      };

      // ── line vehicles first: a rider's position IS its vehicle's ────────────
      const positions = vehiclePositions;
      positions.clear();
      for (let i = 0; i < vehicles.length; i++) {
        const dot = vehicles[i];
        const cursor = cursors.get(dot.id);
        if (!cursor) continue;
        const at = place(positionAt(dot, minute, cursor), -1);
        show(vehicleEls.current[i], vehicleShown, i, at);
        if (at) positions.set(dot.id, at);
      }

      // ── people ─────────────────────────────────────────────────────────────
      const standing = standingDots;
      standing.clear();
      for (let i = 0; i < persons.length; i++) {
        const dot = persons[i];
        const cursor = cursors.get(dot.id);
        if (!cursor) continue;
        const position = positionAt(dot, minute, cursor);

        if (position.kind === "node") {
          standing.set(position.nodeId, (standing.get(position.nodeId) ?? 0) + 1);
        }

        // Aboard a vehicle, nobody is drawn: a bus with forty people is one thing
        // on the street, and the boarding story is told at the stop, not in
        // transit.
        const at = position.kind === "riding" ? null : place(position, i);
        show(personEls.current[i], personShown, i, at);
      }

      // ── the street, as stroke weight and nothing else ───────────────────────
      for (let i = 0; i < fillEdges.length; i++) {
        const element = fillEls.current[i];
        if (!element) continue;
        const edgeId = fillEdges[i];
        const { vehicles: onLink } = fill.fillAt(edgeId, minute);
        if (onLink < 0.5) {
          if (fillShown[i]) {
            element.setAttribute("visibility", "hidden");
            fillShown[i] = 0;
          }
          continue;
        }
        const geometry = edgeGeometry.get(edgeId);
        const share = Math.min(1, onLink / (geometry?.storage ?? 1));
        element.setAttribute(
          "stroke-width",
          (FILL_MIN_W + FILL_MAX_EXTRA_W * share).toFixed(1),
        );
        if (!fillShown[i]) {
          element.setAttribute("visibility", "visible");
          fillShown[i] = 1;
        }
      }

      // ── the crowds, at the node and never on the link ───────────────────────
      const crowds = waitingByNode(fill, minute, doorNodeOf);
      for (const [nodeId, count] of standing) {
        crowds.set(
          nodeId,
          (crowds.get(nodeId) ?? 0) + count * replay.people_per_dot,
        );
      }
      for (let i = 0; i < nodes.length; i++) {
        const element = crowdEls.current[i];
        if (!element) continue;
        const people = crowds.get(nodes[i].id) ?? 0;
        if (people < 1) {
          if (crowdShown[i]) {
            element.setAttribute("visibility", "hidden");
            crowdLabelEls.current[i]?.setAttribute("visibility", "hidden");
            crowdLabel[i] = -1;
            crowdShown[i] = 0;
          }
          continue;
        }
        const radius = Math.min(
          CROWD_MAX_R,
          CROWD_BASE_R + CROWD_PER_SQRT_PERSON * Math.sqrt(people),
        );
        // Children in JSX order: filled halo, ring.
        (element.children[0] as SVGCircleElement).setAttribute(
          "r",
          radius.toFixed(1),
        );
        (element.children[1] as SVGCircleElement).setAttribute(
          "r",
          radius.toFixed(1),
        );
        if (!crowdShown[i]) {
          element.setAttribute("visibility", "visible");
          crowdShown[i] = 1;
        }

        // The number sits clear of its own crowd rather than inside it, and only
        // the crowds worth naming get one — a label on every node is noise.
        const label = crowdLabelEls.current[i];
        if (!label) continue;
        const rounded = people >= CROWD_LABEL_MIN ? Math.round(people) : 0;
        if (crowdLabel[i] !== rounded) {
          crowdLabel[i] = rounded;
          label.textContent = rounded > 0 ? de.replay.crowd(rounded) : "";
          label.setAttribute("visibility", rounded > 0 ? "visible" : "hidden");
        }
        if (rounded > 0) {
          label.setAttribute("y", (nodes[i].y - radius - 12).toFixed(1));
        }
      }
    },
    [
      cursors,
      doorNodeOf,
      edgeGeometry,
      fill,
      fillEdges,
      nodeById,
      nodes,
      persons,
      replay.people_per_dot,
      scatter,
      vehicles,
    ],
  );

  useImperativeHandle(ref, () => ({ draw }), [draw]);

  const padding = 40;
  const box = viewBox({
    nodes: graph.nodes,
    mapWidth: (graph.x_dim ?? 10) * 100,
    mapHeight: (graph.y_dim ?? 10) * 100,
    image: imageRect(graph as ImageFields),
    padding,
  });
  const image = imageRect(graph as ImageFields);

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <svg
        viewBox={`${box.minX} ${box.minY} ${box.width} ${box.height}`}
        className="w-full"
        style={{ aspectRatio: `${box.width}/${box.height}` }}
        role="img"
        aria-label={de.replay.mapLabel}
      >
        {/* The place the graph sits on. Quieter than the map screens draw it: the
            dots are the subject here and a 40%-opacity photograph competes. */}
        {image ? (
          <image
            href={graph.background_image_url ?? undefined}
            x={image.x}
            y={image.y}
            width={image.width}
            height={image.height}
            opacity={0.22}
            preserveAspectRatio="xMinYMin meet"
          />
        ) : null}

        {/* The network, in ink. No mode colours on the links — colour belongs to
            the dots, and a coloured network would compete with them. */}
        <g className="text-foreground/25" fill="none" stroke="currentColor">
          {graph.edges.map((edge) => {
            const geometry = edgeGeometry.get(edge.id);
            if (!geometry) return null;
            return (
              <line
                key={edge.id}
                x1={geometry.x1}
                y1={geometry.y1}
                x2={geometry.x1 + geometry.dx}
                y2={geometry.y1 + geometry.dy}
                strokeWidth={5}
                strokeLinecap="round"
                strokeDasharray={geometry.isRail ? "16,9" : undefined}
              />
            );
          })}
        </g>

        {/* How full each link is, as weight. Never as a colour: a jam is dots
            that have stopped, which is the whole reason this replaced a heatmap. */}
        <g className="text-mode-car" fill="none" stroke="currentColor" opacity={0.4}>
          {fillEdges.map((edgeId, index) => {
            const geometry = edgeGeometry.get(edgeId)!;
            return (
              <line
                key={edgeId}
                ref={(element) => {
                  fillEls.current[index] = element;
                }}
                x1={geometry.x1}
                y1={geometry.y1}
                x2={geometry.x1 + geometry.dx}
                y2={geometry.y1 + geometry.dy}
                strokeWidth={FILL_MIN_W}
                strokeLinecap="round"
                visibility="hidden"
              />
            );
          })}
        </g>

        <g className="text-foreground/40" fill="currentColor">
          {nodes.map((node) => (
            <circle
              key={node.id}
              cx={node.x}
              cy={node.y}
              r={node.isStop ? NODE_R + 2 : NODE_R}
            />
          ))}
        </g>

        {/* The crowds: people at their own front door because the street is full,
            and people at a stop waiting for a line. Size is the quantity — the
            same language the link fill speaks, and no new colour. The number
            itself is drawn last, above the dots (see the bottom of this file):
            here it would be painted over by the very crowd it counts. */}
        <g className="text-foreground">
          {nodes.map((node, index) => (
            <g
              key={node.id}
              ref={(element) => {
                crowdEls.current[index] = element;
              }}
              transform={`translate(${node.x} ${node.y})`}
              visibility="hidden"
            >
              <circle r={0} fill="currentColor" opacity={0.16} />
              <circle
                r={0}
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                opacity={0.45}
              />
            </g>
          ))}
        </g>

        {/* Buses and trains. A box, because a vehicle is not a person — and one
            box however many people are aboard it. */}
        <g className="text-mode-pt" fill="currentColor">
          {vehicles.map((dot, index) => {
            const width = dot.mode === "train" ? TRAIN_W : VEHICLE_W;
            return (
              <g
                key={dot.id}
                ref={(element) => {
                  vehicleEls.current[index] = element;
                }}
                visibility="hidden"
              >
                <rect
                  x={-width / 2}
                  y={-VEHICLE_H / 2}
                  width={width}
                  height={VEHICLE_H}
                  rx={5}
                />
              </g>
            );
          })}
        </g>

        {/* People. Every dot alike, the whole room's traffic together: what the
            class reads off this is where it jams and who is queuing, not whose
            commuter is whose. */}
        {persons.map((dot, index) => {
          const mode = designMode(dot.mode);
          // Filled means "in the queue model". Walking is the one mode that is
          // deliberately outside it — pedestrians never queue and never block —
          // so it is the one drawn hollow. It also separates the two dark marks:
          // on light ground the bike's muted blue and walking's ink are close
          // enough to read as one dot, and a dot cannot carry the stroke pattern
          // that separates the two lines everywhere else.
          const hollow = mode === "walk";
          return (
            <circle
              key={dot.id}
              ref={(element) => {
                personEls.current[index] = element;
              }}
              className={modeStyle[mode].text}
              r={hollow ? DOT_R - 1 : DOT_R}
              fill={hollow ? "none" : "currentColor"}
              stroke={hollow ? "currentColor" : undefined}
              strokeWidth={hollow ? 3 : undefined}
              visibility="hidden"
            />
          );
        })}

        {/* How many people are standing at a node, above everything else and
            outlined in the card colour so it reads over the crowd, the map and
            both themes. */}
        <g className="text-foreground">
          {nodes.map((node, index) => (
            <text
              key={node.id}
              ref={(element) => {
                crowdLabelEls.current[index] = element;
              }}
              x={node.x}
              y={node.y}
              textAnchor="middle"
              fontSize={32}
              className="font-mono"
              style={{
                fill: "currentColor",
                stroke: "var(--color-card)",
                strokeWidth: 7,
                paintOrder: "stroke",
              }}
              visibility="hidden"
            />
          ))}
        </g>
      </svg>
    </div>
  );
}
