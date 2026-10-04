import { useRef, useState, useCallback, useEffect } from "react";
import type { GameMap } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type { EditorState, EdgeChange, VirtualNode, VirtualEdge } from "../../../types/editorTypes";
import { imageRect, viewBox, type ImageFields } from "@/lib/map/view-box";
import { EdgeHitArea } from "@/components/map/edge-hit-area";
import { MapLegend } from "@/components/map/map-legend";
import {
  VersionDiffLayer,
  VersionDiffLegend,
} from "@/components/map/version-diff-layer";
import type { VersionDiff } from "@/lib/map/version-diff";
import { de } from "@/lib/de";
import {
  bundleKey,
  bundleLines,
  edgeLayers,
  editorPaint,
  nodeMark,
  offsetLine,
  PT_LINE_PAINT,
  type EdgeLayer,
} from "@/lib/map/palette";

interface EditorCanvasProps {
  gameMap: GameMap;
  mapGraph: ExtendedMapGraph | undefined;
  state: EditorState;
  ptLineEdgeIds: number[];
  edgeChanges: EdgeChange[];
  onEdgeClick: (edgeId: number) => void;
  onNodeClick: (nodeId: number) => void;
  onCanvasClick: (x?: number, y?: number) => void;
  onNodeDragEnd?: (nodeId: number, x: number, y: number) => void;
  newNodes?: VirtualNode[];
  newEdges?: VirtualEdge[];
  deletedNodeIds?: Set<number>;
  deletedEdgeIds?: Set<number>;
  edgeSourceTempId?: string | null;
  onVirtualNodeClick?: (tempId: string) => void;
  /**
   * What the version on the canvas changes against the one it is compared
   * with ("Verwalten"). Drawn over a veil, so the change is the only thing in
   * colour; nothing under it can be clicked while it is shown.
   */
  diff?: VersionDiff | null;
}

/**
 * The editor's own paint comes from `lib/map/palette.ts` now, like the detail
 * page's. This file used to carry eleven hexes, an eight-colour PT palette and
 * two legend arrays restating them — and its street was `#475569` where the
 * detail page drew `#6b7280`, the same edge in two colours depending on which
 * screen you had open.
 *
 * Two rules from the rulebook decide what is left:
 *
 * - **Primary is what you are adding**, accent is what you are removing or what
 *   the editor is waiting on. That replaces green-for-proposed, red-for-deleted
 *   and three separate ambers with one pair a reader can hold.
 * - **A line is not a colour.** Twelve lines on the shipped map had eight hues
 *   between them, and two lines sharing a street were drawn on the same
 *   coordinates — so whichever came last was the only one you could see, which
 *   is most corridors. They are all the accent and they sit side by side.
 */

/**
 * A change in "Verwalten", in the canvas's own fixed units: well over the 3 of
 * an edge and the 6 of a line, so one bus lane is found at a glance.
 */
const DIFF_SIZES = { line: 9, halo: 16, node: 12 };

/** The arrowhead for one layer, so a marker id is a name and not a hex. */
const ARROW_ID: Record<EdgeLayer["kind"] | "proposed", string> = {
  street: "arrow-street",
  rail: "arrow-rail",
  bikeway: "arrow-bikeway",
  footway: "arrow-footway",
  proposed: "arrow-proposed",
};

/** Every paint an arrowhead is needed in, with the id it is filed under. */
const ARROWS: { id: string; paint: string }[] = [
  ...(["street", "rail", "bikeway", "footway"] as const).map((kind) => ({
    id: ARROW_ID[kind],
    // One example of each kind, drawn by the same function the edges use.
    paint: edgeLayers(
      kind === "street"
        ? { street_edge: {} }
        : kind === "rail"
          ? { train_edge: {} }
          : kind === "bikeway"
            ? { biking: true }
            : { walking: true },
    )[0].color,
  })),
  { id: ARROW_ID.proposed, paint: editorPaint.proposed },
];

const shortenLine = (
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  shortenEnd: number = 12,
) => {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len < shortenEnd * 2) return { x2: p2.x, y2: p2.y };
  const ratio = shortenEnd / len;
  return {
    x2: p2.x - dx * ratio,
    y2: p2.y - dy * ratio,
  };
};

interface DragState {
  nodeId: number;
  startX: number;
  startY: number;
}

function clientToSvg(svg: SVGSVGElement, clientX: number, clientY: number) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return { x: 0, y: 0 };
  return {
    x: (clientX - ctm.e) / ctm.a,
    y: (clientY - ctm.f) / ctm.d,
  };
}

const EditorCanvas = ({
  gameMap,
  mapGraph,
  state,
  ptLineEdgeIds,
  edgeChanges,
  onEdgeClick,
  onNodeClick,
  onCanvasClick,
  onNodeDragEnd,
  newNodes = [],
  newEdges = [],
  deletedNodeIds = new Set(),
  deletedEdgeIds = new Set(),
  edgeSourceTempId,
  onVirtualNodeClick,
  diff,
}: EditorCanvasProps) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const [dragOffset, setDragOffset] = useState<{ nodeId: number; dx: number; dy: number } | null>(null);

  const isDragMode = state.mode === "graph" && state.graphTool === "select";
  const isAddNodeMode =
    (state.mode === "graph" || state.mode === "version-diff") &&
    state.graphTool === "add-node";
  const isAddEdgeMode =
    (state.mode === "graph" || state.mode === "version-diff") &&
    state.graphTool === "add-edge";
  const isVersionDiffMode = state.mode === "version-diff";
  const edgesClickable = !isVersionDiffMode || state.versionDiffStep === 2;

  const handlePointerDown = useCallback(
    (nodeId: number, e: React.PointerEvent) => {
      if (!isDragMode || !svgRef.current) return;
      e.stopPropagation();
      (e.target as SVGElement).setPointerCapture(e.pointerId);
      const pt = clientToSvg(svgRef.current, e.clientX, e.clientY);
      dragRef.current = { nodeId, startX: pt.x, startY: pt.y };
      setDragOffset({ nodeId, dx: 0, dy: 0 });
    },
    [isDragMode]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragRef.current || !svgRef.current) return;
      const pt = clientToSvg(svgRef.current, e.clientX, e.clientY);
      const dx = pt.x - dragRef.current.startX;
      const dy = pt.y - dragRef.current.startY;
      setDragOffset({ nodeId: dragRef.current.nodeId, dx, dy });
    },
    []
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!dragRef.current || !svgRef.current || !mapGraph) return;
      const drag = dragRef.current;
      const pt = clientToSvg(svgRef.current, e.clientX, e.clientY);
      const dx = pt.x - drag.startX;
      const dy = pt.y - drag.startY;
      dragRef.current = null;
      setDragOffset(null);

      // Only fire if actually moved (threshold: 2px in SVG space)
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        const node = mapGraph.nodes.find((n) => n.id === drag.nodeId);
        if (node && onNodeDragEnd) {
          const newX = node.x_position + dx / 100;
          const newY = node.y_position + dy / 100;
          onNodeDragEnd(drag.nodeId, newX, newY);
        }
      } else {
        // Treat as click
        onNodeClick(drag.nodeId);
      }
    },
    [mapGraph, onNodeDragEnd, onNodeClick]
  );

  // Clean up drag on escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && dragRef.current) {
        dragRef.current = null;
        setDragOffset(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Get position for a node, accounting for drag offset
  const getNodePos = useCallback(
    (node: { id: number; x_position: number; y_position: number }) => {
      const x = node.x_position * 100;
      const y = node.y_position * 100;
      if (dragOffset && dragOffset.nodeId === node.id) {
        return { x: x + dragOffset.dx, y: y + dragOffset.dy };
      }
      return { x, y };
    },
    [dragOffset]
  );

  // Compute background image geometry and optional SVG clip rect
  const getImageGeometry = (graph: ExtendedMapGraph) => {
    const imgW = (graph.x_dim ?? gameMap.x_dim) * 100 * (graph.image_scale ?? 1);
    const imgH = (graph.y_dim ?? gameMap.y_dim) * 100 * (graph.image_scale ?? 1);
    const imgX = (graph.image_offset_x ?? 0) * 100;
    const imgY = (graph.image_offset_y ?? 0) * 100;
    const ct = (graph.image_crop_top ?? 0) / 100;
    const cr = (graph.image_crop_right ?? 0) / 100;
    const cb = (graph.image_crop_bottom ?? 0) / 100;
    const cl = (graph.image_crop_left ?? 0) / 100;
    const hasCrop = ct > 0 || cr > 0 || cb > 0 || cl > 0;
    return {
      imgX, imgY, imgW, imgH, hasCrop,
      clipX: imgX + imgW * cl,
      clipY: imgY + imgH * ct,
      clipW: imgW * (1 - cl - cr),
      clipH: imgH * (1 - ct - cb),
    };
  };

  if (!mapGraph || mapGraph.nodes.length === 0) {
    // Show empty canvas with background image if available
    const w = gameMap.x_dim * 100;
    const h = gameMap.y_dim * 100;
    const img = mapGraph ? getImageGeometry(mapGraph) : null;
    return (
      <div className="overflow-hidden rounded-xl border bg-card">
        <svg
          ref={svgRef}
          viewBox={`-60 -60 ${w + 120} ${h + 120}`}
          className="w-full"
          style={{
            aspectRatio: `${w + 120}/${h + 120}`,
            minHeight: "500px",
            cursor: isAddNodeMode ? "crosshair" : undefined,
          }}
          onClick={(e) => {
            if (!svgRef.current) return;
            const pt = clientToSvg(svgRef.current, e.clientX, e.clientY);
            onCanvasClick(pt.x / 100, pt.y / 100);
          }}
        >
          <defs>
            <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
              <path
                d="M 100 0 L 0 0 0 100"
                fill="none"
                stroke={editorPaint.grid}
                strokeWidth="0.5"
              />
            </pattern>
            {img?.hasCrop && (
              <clipPath id="bg-img-clip">
                <rect x={img.clipX} y={img.clipY} width={img.clipW} height={img.clipH} />
              </clipPath>
            )}
          </defs>
          <rect x="-60" y="-60" width={w + 120} height={h + 120} fill="url(#grid)" />
          {mapGraph?.background_image_url && img && (
            <image
              href={mapGraph.background_image_url}
              x={img.imgX}
              y={img.imgY}
              width={img.imgW}
              height={img.imgH}
              opacity={0.5}
              preserveAspectRatio="xMinYMin meet"
              clipPath={img.hasCrop ? "url(#bg-img-clip)" : undefined}
              pointerEvents="none"
            />
          )}
          <text
            x={w / 2}
            y={h / 2}
            textAnchor="middle"
            fontSize="16"
            fill={editorPaint.muted}
          >
            {de.editor.emptyMap}
          </text>
        </svg>
      </div>
    );
  }

  // The view box, from the shared module (K-02). The editor is where the image
  // is placed against the graph, so this is the copy that mattered most: the
  // old floor at the origin meant an image dragged up or left was clipped
  // exactly while you were trying to line it up. Only the source of the box
  // changes here — the drag and save path below is untouched on purpose.
  const padding = 60;
  const mapW = gameMap.x_dim * 100;
  const mapH = gameMap.y_dim * 100;
  const { minX, minY, width, height } = viewBox({
    nodes: mapGraph.nodes,
    mapWidth: mapW,
    mapHeight: mapH,
    image: imageRect(gameMap as ImageFields),
    padding,
  });

  // Build edge lookup for PT line overlay
  const nodeById = new Map(mapGraph.nodes.map((n) => [n.id, n]));
  const changedEdgeIds = new Set(edgeChanges.map((c) => c.edge_id));
  const allPtLines = [
    ...(mapGraph.bus_lines ?? []),
    ...(mapGraph.train_lines ?? []),
  ];
  const ptBundles = bundleLines(allPtLines);

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <svg
        ref={svgRef}
        viewBox={`${minX} ${minY} ${width} ${height}`}
        className="w-full"
        style={{
          aspectRatio: `${width}/${height}`,
          minHeight: "500px",
          cursor: isAddNodeMode ? "crosshair" : undefined,
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            if (isAddNodeMode && svgRef.current) {
              const pt = clientToSvg(svgRef.current, e.clientX, e.clientY);
              onCanvasClick(pt.x / 100, pt.y / 100);
            } else {
              onCanvasClick();
            }
          }
        }}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {(() => {
          const img = getImageGeometry(mapGraph);
          return (
            <defs>
              <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                <path
                d="M 100 0 L 0 0 0 100"
                fill="none"
                stroke={editorPaint.grid}
                strokeWidth="0.5"
              />
              </pattern>
              {img.hasCrop && (
                <clipPath id="bg-img-clip">
                  <rect x={img.clipX} y={img.clipY} width={img.clipW} height={img.clipH} />
                </clipPath>
              )}
              {/* One arrowhead per paint, keyed by the layer's name. It used
                  to be keyed by the hex — `arrowhead-ef4444` — which a `var()`
                  cannot produce a legal id from, and which is why the palette
                  had to name its layers before this file could use it. */}
              {ARROWS.map((arrow) => (
                <marker
                  key={arrow.id}
                  id={arrow.id}
                  markerWidth="8"
                  markerHeight="6"
                  refX="7"
                  refY="3"
                  orient="auto"
                  markerUnits="strokeWidth"
                >
                  <polygon points="0 0, 8 3, 0 6" fill={arrow.paint} />
                </marker>
              ))}
            </defs>
          );
        })()}
        <rect
          x={minX} y={minY} width={width} height={height} fill="url(#grid)"
          onClick={(e) => {
            if (isAddNodeMode && svgRef.current) {
              e.stopPropagation();
              const pt = clientToSvg(svgRef.current, e.clientX, e.clientY);
              onCanvasClick(pt.x / 100, pt.y / 100);
            }
          }}
        />

        {/* Background Image */}
        {mapGraph.background_image_url && (() => {
          const img = getImageGeometry(mapGraph);
          return (
            <image
              href={mapGraph.background_image_url!}
              x={img.imgX}
              y={img.imgY}
              width={img.imgW}
              height={img.imgH}
              opacity={0.5}
              preserveAspectRatio="xMinYMin meet"
              clipPath={img.hasCrop ? "url(#bg-img-clip)" : undefined}
              pointerEvents="none"
            />
          );
        })()}

        {/* PT Line Overlay — existing lines.

            Every line is the accent; what tells two apart is where they run.
            `bundleLines` says how many lines share a link and which place this
            one has in the bundle, so several run beside each other on the same
            street instead of one hiding the rest. */}
        {allPtLines.map((line) => (
          <g key={`ptline-${line.type}-${line.id}`} pointerEvents="none">
            {line.edges.map((edgeId: number) => {
              const edge = mapGraph.edges.find((e) => e.id === edgeId);
              if (!edge) return null;
              const sn = nodeById.get(edge.start_node);
              const en = nodeById.get(edge.end_node);
              if (!sn || !en) return null;
              const place = ptBundles.get(bundleKey(line, edgeId));
              const at = offsetLine(
                getNodePos(sn),
                getNodePos(en),
                place?.index ?? 0,
                place?.count ?? 1,
              );
              return (
                <line
                  key={`ptline-edge-${line.id}-${edgeId}`}
                  x1={at.x1} y1={at.y1}
                  x2={at.x2} y2={at.y2}
                  stroke={PT_LINE_PAINT}
                  strokeWidth="6"
                  opacity={0.45}
                  strokeLinecap="round"
                />
              );
            })}
          </g>
        ))}

        {/* PT Line creation overlay — edges being selected */}
        {ptLineEdgeIds.map((edgeId, idx) => {
          const edge = mapGraph.edges.find((e) => e.id === edgeId);
          if (!edge) return null;
          const sn = nodeById.get(edge.start_node);
          const en = nodeById.get(edge.end_node);
          if (!sn || !en) return null;
          const p1 = getNodePos(sn);
          const p2 = getNodePos(en);
          return (
            <g key={`ptline-new-${edgeId}`} pointerEvents="none">
              <line
                x1={p1.x} y1={p1.y}
                x2={p2.x} y2={p2.y}
                stroke={editorPaint.routed}
                strokeWidth="8"
                opacity={0.6}
                strokeLinecap="round"
                strokeDasharray="10,5"
              />
              <text
                x={(p1.x + p2.x) / 2}
                y={(p1.y + p2.y) / 2 - 8}
                textAnchor="middle"
                fontSize="10"
                fill={editorPaint.routed}
                fontWeight="600"
              >
                {idx + 1}
              </text>
            </g>
          );
        })}

        {/* Virtual node position lookup */}
        {(() => {
          // Build a lookup for virtual node positions (used by virtual edges below)
          // This is rendered as a no-op element; the actual lookup is done inline
          return null;
        })()}

        {/* Edges */}
        {mapGraph.edges.map((edge) => {
          const startNode = nodeById.get(edge.start_node);
          const endNode = nodeById.get(edge.end_node);
          if (!startNode || !endNode) return null;

          const p1 = getNodePos(startNode);
          const p2 = getNodePos(endNode);
          const isSelected = state.selectedEdgeIds.has(edge.id);
          const isInPtRoute = ptLineEdgeIds.includes(edge.id);
          const isChanged = changedEdgeIds.has(edge.id);
          const isDeleted = deletedEdgeIds.has(edge.id);
          const layers = edgeLayers(edge);

          return (
            <g key={`edge-${edge.id}`}>
              {/* Diff highlight for modified edges */}
              {isChanged && state.mode === "version-diff" && !isDeleted && (
                <line
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  stroke={editorPaint.changed}
                  strokeWidth="10"
                  opacity={0.4}
                  strokeLinecap="round"
                />
              )}
              {/* What this version takes away: the accent, over an edge drawn
                  at a quarter opacity below. */}
              {isDeleted && state.mode === "version-diff" && (
                <line
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  stroke={editorPaint.removed}
                  strokeWidth="8"
                  opacity={0.5}
                  strokeLinecap="round"
                  strokeDasharray="6,4"
                  pointerEvents="none"
                />
              )}
              {/* The wide invisible hit target, now shared with the map
                  detail page, which had none at all (K-03). */}
              {edgesClickable && !isDeleted && (
                <EdgeHitArea
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdgeClick(edge.id);
                  }}
                />
              )}
              {(() => {
                const shortened = shortenLine(p1, p2);
                // One stroke per layer, and the arrowhead on the topmost one
                // only — two heads on one link read as two links.
                return layers.map((layer, index) => (
                  <line
                    key={layer.kind}
                    x1={p1.x} y1={p1.y} x2={shortened.x2} y2={shortened.y2}
                    stroke={layer.color}
                    strokeWidth={isSelected ? "5" : "3"}
                    strokeDasharray={layer.dash}
                    strokeLinecap="round"
                    opacity={isDeleted ? 0.25 : isSelected || isInPtRoute ? 1 : 0.7}
                    markerEnd={
                      isDeleted || index !== layers.length - 1
                        ? undefined
                        : `url(#${ARROW_ID[layer.kind]})`
                    }
                    className={`${edgesClickable && !isDeleted ? "cursor-pointer hover:opacity-100" : ""} transition-all`}
                    pointerEvents={edgesClickable && !isDeleted ? "auto" : "none"}
                    onClick={(e) => {
                      if (!edgesClickable || isDeleted) return;
                      e.stopPropagation();
                      onEdgeClick(edge.id);
                    }}
                  />
                ));
              })()}
              {/* Edge label */}
              {edge.name && !isDeleted && (
                <text
                  x={(p1.x + p2.x) / 2}
                  y={(p1.y + p2.y) / 2 - 6}
                  textAnchor="middle"
                  fontSize="8"
                  fill={layers[layers.length - 1].color}
                  className="pointer-events-none select-none"
                  opacity={0.8}
                >
                  {edge.name}
                </text>
              )}
            </g>
          );
        })}

        {/* Virtual (proposed) edges */}
        {newEdges.map((ve) => {
          const resolvePos = (nodeRef: number | string) => {
            if (typeof nodeRef === "number") {
              const n = nodeById.get(nodeRef);
              return n ? getNodePos(n) : null;
            }
            const vn = newNodes.find((n) => n.tempId === nodeRef);
            return vn ? { x: vn.x_position * 100, y: vn.y_position * 100 } : null;
          };
          const p1 = resolvePos(ve.start_node);
          const p2 = resolvePos(ve.end_node);
          if (!p1 || !p2) return null;
          const shortened = shortenLine(p1, p2);
          return (
            <g key={`virtual-edge-${ve.tempId}`} pointerEvents="none">
              <line
                x1={p1.x} y1={p1.y} x2={shortened.x2} y2={shortened.y2}
                stroke={editorPaint.proposed}
                strokeWidth="3"
                strokeDasharray="8,4"
                strokeLinecap="round"
                opacity={0.9}
                markerEnd={`url(#${ARROW_ID.proposed})`}
              />
            </g>
          );
        })}

        {/* Nodes */}
        {mapGraph.nodes.map((node) => {
          const pos = getNodePos(node);
          const isSelected = state.selectedNodeId === node.id;
          const isDragging = dragOffset?.nodeId === node.id;
          const isDeleted = deletedNodeIds.has(node.id);
          const mark = nodeMark(node.node_type);
          const radius = (isSelected ? 14 : 10) * mark.scale;

          return (
            <g key={`node-${node.id}`}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r={radius}
                fill={mark.filled ? mark.color : editorPaint.surface}
                stroke={isSelected ? editorPaint.ink : mark.color}
                strokeWidth={isSelected ? "3" : "2.5"}
                opacity={isDeleted ? 0.25 : 1}
                className={
                  isDragMode
                    ? "cursor-grab active:cursor-grabbing"
                    : isVersionDiffMode && !isDeleted
                      ? isAddEdgeMode || state.graphTool === "delete"
                        ? "cursor-pointer"
                        : "cursor-default"
                      : isVersionDiffMode
                        ? "cursor-default"
                        : "cursor-pointer"
                }
                style={{ transition: isDragging ? "none" : "all 0.15s" }}
                onPointerDown={(e) => {
                  if (isDragMode) handlePointerDown(node.id, e);
                }}
                onClick={(e) => {
                  if (isVersionDiffMode && !isDeleted) {
                    e.stopPropagation();
                    onNodeClick(node.id);
                    return;
                  }
                  if (isVersionDiffMode) return;
                  if (!isDragMode) {
                    e.stopPropagation();
                    onNodeClick(node.id);
                  }
                }}
              />
              {/* Red deletion overlay for deleted nodes */}
              {isDeleted && isVersionDiffMode && (
                <circle
                  cx={pos.x} cy={pos.y} r={radius + 2}
                  fill={editorPaint.removed}
                  opacity={0.5}
                  className="pointer-events-none"
                />
              )}
              {/* Edge source highlight */}
              {isAddEdgeMode && state.edgeSourceNodeId === node.id && (
                <circle
                  cx={pos.x} cy={pos.y} r={18}
                  fill="none" stroke={editorPaint.pending} strokeWidth="3"
                  strokeDasharray="6,3"
                  className="pointer-events-none"
                />
              )}
              {(isSelected || isDragging) && (
                <text
                  x={pos.x} y={pos.y + radius + 15}
                  textAnchor="middle" fontSize="11" fill="currentColor"
                  className="pointer-events-none font-medium text-foreground"
                  style={{ transition: isDragging ? "none" : "all 0.15s" }}
                >
                  {node.name}
                </text>
              )}
            </g>
          );
        })}

        {/* Virtual (proposed) nodes */}
        {newNodes.map((vn) => {
          const x = vn.x_position * 100;
          const y = vn.y_position * 100;
          const isEdgeSource = edgeSourceTempId === vn.tempId;
          return (
            <g
              key={`virtual-node-${vn.tempId}`}
              className="cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onVirtualNodeClick?.(vn.tempId);
              }}
            >
              <circle
                cx={x} cy={y} r={10}
                fill={editorPaint.surface}
                stroke={editorPaint.proposed}
                strokeWidth="2.5"
                strokeDasharray="5,3"
              />
              {isEdgeSource && (
                <circle
                  cx={x} cy={y} r={18}
                  fill="none" stroke={editorPaint.pending} strokeWidth="3"
                  strokeDasharray="6,3"
                  className="pointer-events-none"
                />
              )}
            </g>
          );
        })}

        {diff && (
          <>
            <rect
              data-layer="version-diff-veil"
              x={minX}
              y={minY}
              width={width}
              height={height}
              fill="var(--color-card)"
              opacity={0.75}
            />
            <VersionDiffLayer diff={diff} sizes={DIFF_SIZES} />
          </>
        )}
      </svg>

      {diff && !diff.empty && (
        <VersionDiffLegend diff={diff} className="border-t px-5 py-3" />
      )}

      {/* "Legende fehlt" on the old README list: you draw a map in six colours
          and nothing says which is a tram track and which is a footpath. */}
      <MapLegend className="border-t px-5 py-4" />
    </div>
  );
};

export default EditorCanvas;
