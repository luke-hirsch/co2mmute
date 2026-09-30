import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EdgeHitArea } from "@/components/map/edge-hit-area";
import { MapLegend } from "@/components/map/map-legend";
import { de } from "@/lib/de";
import { edgeLayers, editorPaint, nodeMark } from "@/lib/map/palette";
import { imageRect, viewBox, type ImageFields } from "@/lib/map/view-box";
import type { Edge, GameMap, MapGraph, Node } from "@/types/mapTypes";

/**
 * The graph on the map detail page: the network, and what you clicked on.
 *
 * ### What S18 changed
 *
 * It used to be the whole page — heading, four stat cards, the SVG, the panel
 * and the legend — with `MapDetail` bolting an action bar on top of it. The
 * page is `MapDetail`'s now and this is the graph, which is the one thing it
 * carries that `GameMapViewer` does not do better: **selection**. That is also
 * the reason the two viewers were never merged (they share concerns, not a
 * shape), and it is why the split runs here.
 *
 * ### The colours come from the palette
 *
 * Every hex is gone. This file held eleven of them and a legend restating six,
 * two of which did not match what it drew. `lib/map/palette.ts` is the one
 * answer now, and it answers for the editor as well — see the note there about
 * why an edge is drawn as its layers rather than as a colour per combination.
 */

interface SelectedElement {
  type: "node" | "edge";
  id: number;
}

/** How far a mark is drawn from a node's centre. Unchanged from before S18. */
const NODE_RADIUS = 10;
const NODE_RADIUS_SELECTED = 14;

const MapViewer = ({
  gameMap,
  mapGraph,
}: {
  gameMap: GameMap;
  mapGraph: MapGraph;
}) => {
  const [selectedElement, setSelectedElement] =
    useState<SelectedElement | null>(null);

  // Nodes, the map box and the image's drawn rectangle, from the shared module
  // (K-02). This viewer used to size itself from the nodes alone, which is why
  // it never showed the background at all and why an empty map gave it
  // Infinity.
  const bg = imageRect(gameMap as ImageFields);
  const { minX, minY, width, height } = viewBox({
    nodes: mapGraph.nodes,
    mapWidth: (gameMap.x_dim ?? 10) * 100,
    mapHeight: (gameMap.y_dim ?? 10) * 100,
    image: bg,
    padding: 60,
  });

  const selectedNode =
    selectedElement?.type === "node"
      ? mapGraph.nodes.find((n) => n.id === selectedElement.id)
      : null;
  const selectedEdge =
    selectedElement?.type === "edge"
      ? mapGraph.edges.find((e) => e.id === selectedElement.id)
      : null;

  return (
    <div className="grid gap-8 lg:grid-cols-4 lg:items-start">
      <div className="lg:col-span-3">
        <div className="overflow-hidden rounded-xl border bg-card">
          <svg
            viewBox={`${minX} ${minY} ${width} ${height}`}
            className="w-full"
            style={{ aspectRatio: `${width}/${height}`, minHeight: "500px" }}
          >
            {/* The background image, under everything. The detail page did not
                render it before F7, so a map calibrated in the editor looked
                different here than in the game. */}
            {bg && gameMap.background_image_url ? (
              <image
                href={gameMap.background_image_url}
                x={bg.x}
                y={bg.y}
                width={bg.width}
                height={bg.height}
                opacity={0.4}
                preserveAspectRatio="xMinYMin meet"
              />
            ) : null}

            <defs>
              <pattern
                id="viewer-grid"
                width="100"
                height="100"
                patternUnits="userSpaceOnUse"
              >
                <path
                  d="M 100 0 L 0 0 0 100"
                  fill="none"
                  stroke={editorPaint.grid}
                  strokeWidth="0.5"
                />
              </pattern>
            </defs>
            {/* The grid has to start where the view box does: with a negative
                minX it used to begin at the origin and leave the left and top
                of the map ungridded. */}
            <rect
              x={minX}
              y={minY}
              width={width}
              height={height}
              fill="url(#viewer-grid)"
            />

            {mapGraph.edges.map((edge) => {
              const startNode = mapGraph.nodes.find(
                (n) => n.id === edge.start_node,
              );
              const endNode = mapGraph.nodes.find((n) => n.id === edge.end_node);
              if (!startNode || !endNode) return null;

              const x1 = startNode.x_position * 100;
              const y1 = startNode.y_position * 100;
              const x2 = endNode.x_position * 100;
              const y2 = endNode.y_position * 100;
              const isSelected = selectedElement?.id === edge.id;

              return (
                <g key={`edge-${edge.id}`}>
                  {/* K-03: the click goes on the wide invisible stroke, not on
                      the 3-unit line, which was a one-pixel target. */}
                  <EdgeHitArea
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    onClick={() =>
                      setSelectedElement({ type: "edge", id: edge.id })
                    }
                  />
                  {/* One stroke per layer the corridor carries, so a street
                      with a railway over it shows both rather than a third
                      colour invented to name the pair. */}
                  {edgeLayers(edge).map((layer) => (
                    <line
                      key={layer.kind}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={layer.color}
                      strokeWidth={isSelected ? "5" : "3"}
                      strokeDasharray={layer.dash}
                      strokeLinecap="round"
                      opacity={isSelected ? "1" : "0.6"}
                      className="pointer-events-none transition-all"
                    />
                  ))}
                </g>
              );
            })}

            {mapGraph.nodes.map((node) => {
              const x = node.x_position * 100;
              const y = node.y_position * 100;
              const isSelected = selectedElement?.id === node.id;
              const mark = nodeMark(node.node_type);
              const radius =
                (isSelected ? NODE_RADIUS_SELECTED : NODE_RADIUS) * mark.scale;

              return (
                <g key={`node-${node.id}`}>
                  <circle
                    cx={x}
                    cy={y}
                    r={radius}
                    fill={mark.filled ? mark.color : editorPaint.surface}
                    stroke={isSelected ? editorPaint.ink : mark.color}
                    strokeWidth={isSelected ? 3 : 2.5}
                    className="cursor-pointer transition-all"
                    onClick={() =>
                      setSelectedElement({ type: "node", id: node.id })
                    }
                  />
                  {isSelected && (
                    <text
                      x={x}
                      y={y + radius + 15}
                      textAnchor="middle"
                      fontSize="11"
                      fill="currentColor"
                      className="pointer-events-none font-medium text-foreground"
                    >
                      {node.name}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          <MapLegend className="border-t px-5 py-4" />
        </div>
      </div>

      <aside className="lg:col-span-1">
        <div className="sticky top-8 rounded-xl border bg-card p-6">
          <h2 className="font-semibold">{de.map.details}</h2>

          {selectedNode ? (
            <NodeDetails
              node={selectedNode}
              onClear={() => setSelectedElement(null)}
            />
          ) : selectedEdge ? (
            <EdgeDetails
              edge={selectedEdge}
              onClear={() => setSelectedElement(null)}
            />
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              {de.map.pickHint}
            </p>
          )}
        </div>
      </aside>
    </div>
  );
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="mt-0.5 text-sm">{children}</div>
    </div>
  );
}

function NodeDetails({ node, onClear }: { node: Node; onClear: () => void }) {
  return (
    <div className="mt-4 space-y-4">
      <Field label={de.editor.node.title}>
        <span className="font-medium">{node.name}</span>
      </Field>
      <Field label={de.editor.node.position}>
        <span className="font-mono">
          ({node.x_position}, {node.y_position})
        </span>
      </Field>
      <Field label={de.editor.node.types}>
        <div className="flex flex-wrap gap-1.5">
          {node.node_type.map((t) => (
            <Badge key={t.id} variant="outline">
              {t.short}
            </Badge>
          ))}
        </div>
      </Field>
      <Button variant="outline" size="sm" className="w-full" onClick={onClear}>
        {de.map.clearSelection}
      </Button>
    </div>
  );
}

function EdgeDetails({ edge, onClear }: { edge: Edge; onClear: () => void }) {
  return (
    <div className="mt-4 space-y-4">
      <Field label={de.editor.edge.title}>
        <span className="font-medium">{edge.name}</span>
      </Field>

      <Field label={de.editor.edge.type}>
        {/* Outline badges throughout: what a corridor carries is a fact, not a
            state, and the palette spends its two colours on the graph itself. */}
        <div className="flex flex-col items-start gap-1.5">
          {edge.street_edge ? (
            <Badge variant="outline">
              {de.editor.edge.streetSummary(
                edge.street_edge.speed_limit,
                edge.street_edge.lanes,
              )}
              {edge.street_edge.dedicated_bus_lane
                ? ` ${de.editor.edge.busLaneSuffix}`
                : null}
            </Badge>
          ) : null}
          {edge.train_edge ? (
            <Badge variant="outline">{de.editor.edge.train}</Badge>
          ) : null}
          {!edge.street_edge && !edge.train_edge ? (
            <Badge variant="outline">{de.editor.edge.path}</Badge>
          ) : null}
        </div>
      </Field>

      {(edge.biking || edge.walking) && (
        <Field label={de.editor.edge.accessibleBy}>
          <div className="flex flex-wrap gap-1.5">
            {edge.biking && (
              <Badge variant="outline">{de.editor.edge.biking}</Badge>
            )}
            {edge.walking && (
              <Badge variant="outline">{de.editor.edge.walking}</Badge>
            )}
          </div>
        </Field>
      )}

      <Field label={de.editor.edge.maxLanes}>{edge.max_lanes}</Field>

      <Button variant="outline" size="sm" className="w-full" onClick={onClear}>
        {de.map.clearSelection}
      </Button>
    </div>
  );
}

export default MapViewer;
