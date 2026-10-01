/**
 * The map on the round screen: the network, one passenger's route, and where it
 * jammed last time.
 *
 * ### What changed in S6, and why
 *
 * This was the last screen in the game still painting its own palette. Base
 * edges were four hardcoded hexes including a green (`#34d399`), nodes were
 * green / blue / amber / violet by type, the home pin was green and the
 * destination pin red — and the route was drawn in accent amber for **every**
 * mode, which is the same amber the picker draws Bus & Bahn in. So a walking
 * route and the PT line were the same colour, and the rulebook's "no green, no
 * red, pattern not hue" held everywhere except the one screen players spend the
 * round on.
 *
 * Now: the network is neutral ink at low opacity, and colour is spent only on
 * the route, which carries its own mode's colour **and stroke pattern** from
 * `components/metro/mode.ts` — car solid, bike dashed, walk dotted, PT solid
 * amber. That is the same language the legend, the agent row, the replay and the
 * landing page already speak, and it survives a colour-blind reader.
 *
 * ### The jam overlay is weight, and since S24 a step towards the accent
 *
 * `trafficHeatmap` used to take a congestion ratio and run it through a
 * green→yellow→orange→red ramp. A two-colour palette has no hue ramp, and weight
 * alone — S6's answer — turned out too quiet: the difference between two loaded
 * streets was a pixel on a phone. So a loaded street is drawn heavier **and**
 * moves from ink towards the accent (`jamTint`), slowly at first and mostly
 * accent by half speed. Amber is also the PT line's colour; that is accepted —
 * a route is a line from a home, and an amber street with nothing beginning on it
 * is a jam. Still one hue pair, no green, no red.
 *
 * `previous_round_traffic` is what "schnellste" routes on, so the picture and the
 * router cannot disagree.
 *
 * ### What was deleted
 *
 * Every Dijkstra-visualisation prop (`showDijkstraViz`, `pathfindingVisited`,
 * `pathfindingExploredEdges`, `pathfindingRelaxedEdge`, `pathfindingDistances`,
 * `pathfindingFinalPath`, `pathfindingPreviousEdges`), `highlightedNodes`,
 * `error` and `showRouteLegend`. `route-map.tsx` is the only consumer and passed
 * none of them — the legend was English, which nothing player-facing may be any
 * more, and it was never rendered because the one call site passed `false`.
 */

import { useEffect, useMemo, useState } from "react";

import { imageRect, viewBox, type ImageFields } from "@/lib/map/view-box";
import { de } from "@/lib/de";
import { modeStyle } from "@/components/metro/mode";
import { jamTint, type EdgeLoad } from "@/lib/map/traffic";
import { traceStepMs, type SearchTrace } from "@/lib/map/search-trace";
import type { Edge, MapGraph, Node } from "@/types/mapTypes";
import type {
  ExtendedMapGraph,
  RouteSegment,
  SegmentMode,
} from "@/types/routeTypes";

interface GameMapViewerProps {
  mapGraph: MapGraph | ExtendedMapGraph | null;
  isLoading?: boolean;
  compact?: boolean;
  homeNodeId?: number;
  destinationNodeId?: number;
  routeSegments?: RouteSegment[];
  /**
   * Last round's measured load per link. Drawn as weight and a step towards the
   * accent — see the note above about why this is not a heatmap.
   */
  jam?: EdgeLoad[];
  /**
   * What the router examined to find `routeSegments`, played back once as the
   * route appears. The only thing on screen that shows the routing doing
   * anything (S24).
   */
  search?: SearchTrace | null;
}

/**
 * The four design lines a route segment can be drawn in.
 *
 * Bus and train are both "Bus & Bahn" on screen — the palette has four lines and
 * the mode picker offers four choices, so a train is not a fifth colour.
 */
function designMode(mode: SegmentMode) {
  return mode === "bus" || mode === "train" ? "public" : mode;
}

/**
 * The dash pattern that separates the lines when colour cannot — car solid, bike
 * dashed, walk dotted, as everywhere else. Scaled with the map for the same
 * reason the marks are: a fixed pattern on a wide map is a solid line.
 */
function routeDash(
  mode: SegmentMode,
  u: (fraction: number) => number,
): string | undefined {
  if (mode === "bike") return `${u(0.014)},${u(0.009)}`;
  if (mode === "walk") return `${u(0.001)},${u(0.017)}`;
  return undefined;
}

/**
 * Everything drawn on the map is sized as a fraction of the map's own width.
 *
 * The SVG is in map units × 100, so a 13-unit-wide map renders a 1380-unit view
 * box into roughly 370 CSS pixels on a phone — a scale of 0.27. Fixed unit sizes
 * therefore come out four times smaller than they look in the source: the home
 * and destination marks were `r=13`, which is **3.5 CSS pixels**, and that is the
 * roadmap's "two 4px dots among 55 on a phone". A map drawn in different units
 * would scale them differently again.
 *
 * So the numbers below are a fraction of the view box, tuned against Berlin
 * Mitte-West at 390px, and any map gets marks of the same apparent size.
 */
const SIZES = {
  /** The network underneath. Context, so it stays thin. */
  edge: 0.0045,
  /** An ordinary node: present, not a target. */
  node: 0.006,
  /** The chosen route and the halo that lifts it off the background image. */
  route: 0.011,
  routeHalo: 0.02,
  /** Home and destination: thumb-sized, because they are what you look for. */
  markRing: 0.024,
  markDot: 0.01,
  markStroke: 0.006,
  label: 0.032,
  labelHalo: 0.009,
  /**
   * Free flow to gridlock. The top end is deliberately below the route's own
   * weight: a jammed network must not out-shout the line the player is tracing
   * through it.
   */
  /** The links the router examined: lighter than the route that wins. */
  search: 0.008,
  jamMin: 0.005,
  jamMax: 0.015,
} as const;

const GameMapViewer = ({
  mapGraph,
  isLoading = false,
  compact = false,
  homeNodeId,
  destinationNodeId,
  routeSegments,
  jam,
  search,
}: GameMapViewerProps) => {
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  const nodeMap = useMemo(() => {
    const map = new Map<number, Node>();
    mapGraph?.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [mapGraph?.nodes]);

  const jamMap = useMemo(() => {
    if (!jam?.length) return null;
    const map = new Map<number, number>();
    // Only what actually slowed down is worth drawing. A link at free flow is
    // the baseline the network is already drawn at, and painting 170 of them
    // thicker would say "busy everywhere".
    for (const load of jam) {
      if (load.congestionRatio > 0.05) map.set(load.edgeId, load.congestionRatio);
    }
    return map.size ? map : null;
  }, [jam]);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-muted-foreground">{de.map.loading}</p>
      </div>
    );
  }

  if (!mapGraph) {
    return (
      <div className="rounded-lg border border-border p-4">
        <p className="text-sm text-muted-foreground">{de.app.empty}</p>
      </div>
    );
  }

  // A route segment replaces the base edge under it, so the network does not
  // show through a line drawn on top of it. `-1` is the sentinel for a leg with
  // no edge of its own (a walk between two stops).
  const routeEdgeIds = new Set(
    (routeSegments ?? []).map((s) => s.edgeId).filter((id) => id >= 0),
  );

  // The view box covers the nodes, the map box AND the image's drawn rectangle
  // (K-02): the old version floored at the origin and stopped at the nominal
  // map size, so an image at a negative offset or scaled past 1 was cut off.
  // Shared with MapViewer and EditorCanvas — see lib/map/view-box.ts.
  const mapW = ("x_dim" in mapGraph ? (mapGraph.x_dim ?? 10) : 10) * 100;
  const mapH = ("y_dim" in mapGraph ? (mapGraph.y_dim ?? 10) : 10) * 100;
  const { minX, minY, width, height } = viewBox({
    nodes: mapGraph.nodes,
    mapWidth: mapW,
    mapHeight: mapH,
    image: imageRect(mapGraph as ImageFields),
    padding: 40,
  });

  const selectedNode = selectedNodeId
    ? mapGraph.nodes.find((n) => n.id === selectedNodeId)
    : null;

  const img = imageGeometry(mapGraph);
  const at = (nodeId: number) => {
    const node = nodeMap.get(nodeId);
    return node ? { x: node.x_position * 100, y: node.y_position * 100 } : null;
  };
  /** A size from `SIZES`, in this map's own units. */
  const u = (fraction: number) => fraction * width;

  return (
    <div className="w-full">
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <svg
          viewBox={`${minX} ${minY} ${width} ${height}`}
          className="w-full"
          style={{
            aspectRatio: `${width}/${height}`,
            minHeight: compact ? "200px" : "400px",
          }}
        >
          <defs>
            {img?.hasCrop && (
              <clipPath id="game-bg-img-clip">
                <rect
                  x={img.clipX}
                  y={img.clipY}
                  width={img.clipW}
                  height={img.clipH}
                />
              </clipPath>
            )}
          </defs>

          {img && (
            <image
              href={(mapGraph as ExtendedMapGraph).background_image_url!}
              x={img.imgX}
              y={img.imgY}
              width={img.imgW}
              height={img.imgH}
              opacity={0.4}
              preserveAspectRatio="xMinYMin meet"
              clipPath={img.hasCrop ? "url(#game-bg-img-clip)" : undefined}
            />
          )}

          {/*
            The network. Neutral ink at low opacity, so the one route drawn on
            top of it is the only coloured thing on the map. Rail keeps its long
            dash — that is a map convention, not a mode colour.
          */}
          <g className="text-foreground/25" fill="none" stroke="currentColor">
            {mapGraph.edges.map((edge) => {
              if (routeEdgeIds.has(edge.id)) return null;
              const a = at(edge.start_node);
              const b = at(edge.end_node);
              if (!a || !b) return null;
              return (
                <line
                  key={`edge-${edge.id}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  strokeWidth={u(SIZES.edge)}
                  strokeLinecap="round"
                  strokeDasharray={
                    isRailOnly(edge) ? `${u(0.012)},${u(0.007)}` : undefined
                  }
                />
              );
            })}
          </g>

          {/*
            Where it stopped last round: heavier, and from ink towards the accent.

            Never the car's blue: congestion is a property of the street and
            reads the same under a route of any mode, and in the car's colour it
            competed with the car route sitting on top of it. The tint is a
            colour-mix of two tokens, so it follows the colour mode.
          */}
          {jamMap && (
            <g fill="none">
              {mapGraph.edges.map((edge) => {
                const ratio = jamMap.get(edge.id);
                if (ratio === undefined) return null;
                const a = at(edge.start_node);
                const b = at(edge.end_node);
                if (!a || !b) return null;
                return (
                  <line
                    key={`jam-${edge.id}`}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    strokeWidth={u(
                      SIZES.jamMin + ratio * (SIZES.jamMax - SIZES.jamMin),
                    )}
                    strokeLinecap="round"
                    style={{
                      stroke: `color-mix(in srgb, var(--color-brandaccent) ${Math.round(jamTint(ratio) * 100)}%, var(--color-foreground))`,
                      strokeOpacity: 0.35 + 0.6 * jamTint(ratio),
                    }}
                  />
                );
              })}
            </g>
          )}

          {search && mapGraph && (
            <SearchLayer
              key={search.id}
              steps={search.steps}
              edges={mapGraph.edges}
              at={at}
              u={u}
            />
          )}

          {/* The chosen route, in its own mode's colour and stroke. */}
          {routeSegments?.map((segment, index) => {
            const a = at(segment.startNode);
            const b = at(segment.endNode);
            if (!a || !b) return null;
            const style = modeStyle[designMode(segment.mode)];
            return (
              <g
                key={`route-${index}`}
                className={style.text}
                fill="none"
                stroke="currentColor"
              >
                {/* A halo in the card's own colour, so the line reads over the
                    background image as well as over the network. */}
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="var(--color-card)"
                  strokeWidth={u(SIZES.routeHalo)}
                  strokeLinecap="round"
                  opacity={0.85}
                />
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  strokeWidth={u(SIZES.route)}
                  strokeLinecap="round"
                  strokeDasharray={routeDash(segment.mode, u)}
                />
              </g>
            );
          })}

          {/* The network's nodes: present, not identified. Type is what the
              home and destination marks below say, for the two that matter. */}
          <g className="text-foreground/40" fill="currentColor">
            {mapGraph.edges.length > 0 &&
              mapGraph.nodes.map((node) => (
                <circle
                  key={`node-${node.id}`}
                  cx={node.x_position * 100}
                  cy={node.y_position * 100}
                  r={u(SIZES.node) * (selectedNodeId === node.id ? 1.6 : 1)}
                  className="cursor-pointer"
                  onClick={() =>
                    setSelectedNodeId(selectedNodeId === node.id ? null : node.id)
                  }
                />
              ))}
          </g>

          {/*
            Home and destination.

            These were two 4px dots among 55 on a phone — the roadmap's own
            words — so the one thing a player has to find on the map was the
            hardest thing on it to see. Now they are labelled marks at thumb
            scale: a ring for home, a filled disc for the destination, both in
            ink with a halo, and the name written beside them. Filled vs hollow
            is the same "presence" language the roster and the track use, and it
            costs no colour, which the route needs all of.
          */}
          <PlaceMark
            point={at(homeNodeId ?? -1)}
            label={de.round.home}
            u={u}
            box={{ minX, width }}
            hollow
          />
          <PlaceMark
            point={at(destinationNodeId ?? -1)}
            label={nodeMap.get(destinationNodeId ?? -1)?.name}
            u={u}
            box={{ minX, width }}
            below
          />
        </svg>
      </div>

      {selectedNode && (
        <div className="mt-2 rounded border border-border px-3 py-2 text-sm">
          {selectedNode.name}
        </div>
      )}

      {jamMap ? (
        <p className="mt-3 max-w-(--measure-body) text-sm text-muted-foreground">
          {de.round.jamHint}
        </p>
      ) : null}
    </div>
  );
};

/** How long the finished search stays before it fades, and how long it fades. */
const SEARCH_HOLD_MS = 350;
const SEARCH_FADE_MS = 600;

/**
 * The router's search, drawn one step at a time and then let go (S24).
 *
 * Links appear in the accent as the search reaches them, so you watch it spread
 * out from home and favour the direction of the destination, then fade and leave
 * the route. Attention is the accent's job in this palette; the route on top is
 * in its own mode's colour and never competes.
 *
 * The step counter is state, but there are only about fifty steps over a second
 * and a half — nothing like the replay's per-frame dots, which is why this does
 * not need that file's direct-attribute drawing. **Nothing is drawn under
 * `prefers-reduced-motion`**: the route is already there, and a flourish that
 * moves is the thing the setting exists to refuse.
 */
function SearchLayer({
  steps,
  edges,
  at,
  u,
}: {
  steps: number[][];
  edges: Edge[];
  at: (nodeId: number) => { x: number; y: number } | null;
  u: (fraction: number) => number;
}) {
  const [shown, setShown] = useState(0);
  const [fading, setFading] = useState(false);
  // Decided once, on mount: the layer is keyed per search, so a new search is a
  // new mount and the preference is read again.
  const [gone, setGone] = useState(
    () =>
      steps.length === 0 ||
      (typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches),
  );

  useEffect(() => {
    if (gone) return;

    const timers: number[] = [];
    const interval = window.setInterval(() => {
      setShown((count) => {
        if (count + 1 >= steps.length) window.clearInterval(interval);
        return Math.min(count + 1, steps.length);
      });
    }, traceStepMs(steps.length));
    timers.push(
      window.setTimeout(
        () => setFading(true),
        traceStepMs(steps.length) * steps.length + SEARCH_HOLD_MS,
      ),
      window.setTimeout(
        () => setGone(true),
        traceStepMs(steps.length) * steps.length + SEARCH_HOLD_MS + SEARCH_FADE_MS,
      ),
    );
    return () => {
      window.clearInterval(interval);
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [steps, gone]);

  if (gone || shown === 0) return null;

  const examined = new Set(steps.slice(0, shown).flat());
  return (
    <g
      fill="none"
      stroke="var(--color-brandaccent)"
      strokeLinecap="round"
      strokeWidth={u(SIZES.search)}
      aria-hidden="true"
      style={{
        opacity: fading ? 0 : 0.75,
        transition: `opacity ${SEARCH_FADE_MS}ms ease-out`,
      }}
    >
      {edges.map((edge) => {
        if (!examined.has(edge.id)) return null;
        const a = at(edge.start_node);
        const b = at(edge.end_node);
        if (!a || !b) return null;
        return <line key={edge.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
      })}
    </g>
  );
}

/**
 * One end of the commute, drawn big enough to find.
 *
 * The label sits above the mark with a halo behind it rather than a filled
 * plate: a plate at this size covers the streets the player is trying to read.
 */
function PlaceMark({
  point,
  label,
  u,
  box,
  hollow = false,
  below = false,
}: {
  point: { x: number; y: number } | null;
  label?: string;
  u: (fraction: number) => number;
  /** The view box, so a long name can be kept inside it. */
  box: { minX: number; width: number };
  hollow?: boolean;
  /** Below the mark rather than above it, so the two never collide. */
  below?: boolean;
}) {
  if (!point) return null;
  const r = u(SIZES.markRing);

  // A name as long as "Arbeit Justizministerium" centred on a mark near the
  // edge runs straight out of the box. Anchoring it inwards near either side
  // keeps it on the map without measuring the text.
  const third = box.width / 3;
  const anchor =
    point.x < box.minX + third
      ? "start"
      : point.x > box.minX + 2 * third
        ? "end"
        : "middle";

  return (
    <g className="text-foreground pointer-events-none">
      <circle
        cx={point.x}
        cy={point.y}
        r={r}
        fill="var(--color-card)"
        stroke="currentColor"
        strokeWidth={u(SIZES.markStroke)}
      />
      {!hollow && (
        <circle cx={point.x} cy={point.y} r={u(SIZES.markDot)} fill="currentColor" />
      )}
      {label && (
        // `xmlSpace` because SVG collapses runs of whitespace by XML rules, and
        // "zu Hause" rendered as "zuHause" without it.
        <text
          x={point.x}
          y={below ? point.y + r + u(0.05) : point.y - r - u(0.014)}
          textAnchor={anchor}
          fontSize={u(SIZES.label)}
          fontWeight={500}
          fill="currentColor"
          stroke="var(--color-card)"
          strokeWidth={u(SIZES.labelHalo)}
          paintOrder="stroke"
          xmlSpace="preserve"
        >
          {label}
        </text>
      )}
    </g>
  );
}

/** A rail alignment with no street under it — drawn with a sleeper dash. */
function isRailOnly(edge: Edge): boolean {
  return edge.train_edge != null && edge.street_edge == null;
}

function imageGeometry(mapGraph: MapGraph | ExtendedMapGraph) {
  if (!("background_image_url" in mapGraph) || !mapGraph.background_image_url) {
    return null;
  }
  const imgW = (mapGraph.x_dim ?? 10) * 100 * (mapGraph.image_scale ?? 1);
  const imgH = (mapGraph.y_dim ?? 10) * 100 * (mapGraph.image_scale ?? 1);
  const imgX = (mapGraph.image_offset_x ?? 0) * 100;
  const imgY = (mapGraph.image_offset_y ?? 0) * 100;
  const ct = (mapGraph.image_crop_top ?? 0) / 100;
  const cr = (mapGraph.image_crop_right ?? 0) / 100;
  const cb = (mapGraph.image_crop_bottom ?? 0) / 100;
  const cl = (mapGraph.image_crop_left ?? 0) / 100;
  return {
    imgX,
    imgY,
    imgW,
    imgH,
    hasCrop: ct > 0 || cr > 0 || cb > 0 || cl > 0,
    clipX: imgX + imgW * cl,
    clipY: imgY + imgH * ct,
    clipW: imgW * (1 - cl - cr),
    clipH: imgH * (1 - ct - cb),
  };
}

export default GameMapViewer;
