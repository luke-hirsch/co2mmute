import { useRef, useState, useCallback, useEffect } from "react";
import type { GameMap } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type { EditorState, EdgeChange } from "../../../types/editorTypes";

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
}

const getEdgeColorAndStyle = (edge: any) => {
  const hasStreetEdge = edge.street_edge !== null;
  const hasTrainEdge = edge.train_edge !== null;
  if (hasTrainEdge && !hasStreetEdge)
    return { stroke: "#ef4444", strokeDasharray: "5,5" };
  if (hasStreetEdge && hasTrainEdge)
    return { stroke: "#f97316", strokeDasharray: "0" };
  if (hasStreetEdge) return { stroke: "#6b7280", strokeDasharray: "0" };
  if (edge.biking && !edge.walking)
    return { stroke: "#3b82f6", strokeDasharray: "0" };
  if (edge.walking && !edge.biking)
    return { stroke: "#10b981", strokeDasharray: "0" };
  return { stroke: "#8b5cf6", strokeDasharray: "0" };
};

const getNodeColor = (nodeTypes: any[]) => {
  const typeNames = nodeTypes.map((t: any) => t.name);
  if (typeNames.includes("home")) return "#10b981";
  if (typeNames.includes("workplace")) return "#3b82f6";
  if (typeNames.includes("station")) return "#f59e0b";
  if (typeNames.includes("bus_stop")) return "#ef4444";
  return "#6b7280";
};

// Color palette for PT lines
const PT_LINE_COLORS = [
  "#8b5cf6", "#06b6d4", "#f59e0b", "#ec4899",
  "#14b8a6", "#f97316", "#6366f1", "#84cc16",
];

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
}: EditorCanvasProps) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const [dragOffset, setDragOffset] = useState<{ nodeId: number; dx: number; dy: number } | null>(null);

  const isDragMode = state.mode === "graph" && state.graphTool === "select";
  const isAddNodeMode = state.mode === "graph" && state.graphTool === "add-node";
  const isAddEdgeMode = state.mode === "graph" && state.graphTool === "add-edge";
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
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-subtle dark:border-darksubtle overflow-hidden">
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
              <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
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
            fill="#9ca3af"
          >
            Empty map — add nodes and edges in graph mode
          </text>
        </svg>
      </div>
    );
  }

  // Calculate SVG dimensions — always include map bounds so background image stays visible
  const padding = 60;
  const mapW = gameMap.x_dim * 100;
  const mapH = gameMap.y_dim * 100;
  const minX = Math.min(
    0 - padding,
    ...mapGraph.nodes.map((n) => n.x_position * 100 - padding)
  );
  const minY = Math.min(
    0 - padding,
    ...mapGraph.nodes.map((n) => n.y_position * 100 - padding)
  );
  const maxX = Math.max(
    mapW + padding,
    ...mapGraph.nodes.map((n) => n.x_position * 100 + padding)
  );
  const maxY = Math.max(
    mapH + padding,
    ...mapGraph.nodes.map((n) => n.y_position * 100 + padding)
  );
  const width = maxX - minX;
  const height = maxY - minY;

  // Build edge lookup for PT line overlay
  const nodeById = new Map(mapGraph.nodes.map((n) => [n.id, n]));
  const changedEdgeIds = new Set(edgeChanges.map((c) => c.edge_id));

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-subtle dark:border-darksubtle overflow-hidden">
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
                <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
              </pattern>
              {img.hasCrop && (
                <clipPath id="bg-img-clip">
                  <rect x={img.clipX} y={img.clipY} width={img.clipW} height={img.clipH} />
                </clipPath>
              )}
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

        {/* PT Line Overlay — existing lines */}
        {[...(mapGraph.bus_lines ?? []), ...(mapGraph.train_lines ?? [])].map(
          (line, lineIdx) => {
            const color = PT_LINE_COLORS[lineIdx % PT_LINE_COLORS.length];
            return (
              <g key={`ptline-${line.type}-${line.id}`} pointerEvents="none">
                {line.edges.map((edgeId: number) => {
                  const edge = mapGraph.edges.find((e) => e.id === edgeId);
                  if (!edge) return null;
                  const sn = nodeById.get(edge.start_node);
                  const en = nodeById.get(edge.end_node);
                  if (!sn || !en) return null;
                  const p1 = getNodePos(sn);
                  const p2 = getNodePos(en);
                  return (
                    <line
                      key={`ptline-edge-${line.id}-${edgeId}`}
                      x1={p1.x} y1={p1.y}
                      x2={p2.x} y2={p2.y}
                      stroke={color}
                      strokeWidth="6"
                      opacity={0.35}
                      strokeLinecap="round"
                    />
                  );
                })}
              </g>
            );
          }
        )}

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
                stroke="#fbbf24"
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
                fill="#fbbf24"
                fontWeight="bold"
              >
                {idx + 1}
              </text>
            </g>
          );
        })}

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
          const { stroke, strokeDasharray } = getEdgeColorAndStyle(edge);

          return (
            <g key={`edge-${edge.id}`}>
              {/* Diff highlight */}
              {isChanged && state.mode === "version-diff" && (
                <line
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  stroke="#fbbf24"
                  strokeWidth="8"
                  opacity={0.4}
                  strokeLinecap="round"
                />
              )}
              <line
                x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                stroke={stroke}
                strokeWidth={isSelected ? "3" : "2"}
                strokeDasharray={strokeDasharray}
                opacity={isSelected || isInPtRoute ? 1 : 0.6}
                className={`${edgesClickable ? "cursor-pointer hover:opacity-100" : ""} transition-all`}
                onClick={(e) => {
                  if (!edgesClickable) return;
                  e.stopPropagation();
                  onEdgeClick(edge.id);
                }}
              />
            </g>
          );
        })}

        {/* Nodes */}
        {mapGraph.nodes.map((node) => {
          const pos = getNodePos(node);
          const isSelected = state.selectedNodeId === node.id;
          const isDragging = dragOffset?.nodeId === node.id;
          const radius = isSelected ? 14 : 10;

          return (
            <g key={`node-${node.id}`}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r={radius}
                fill={getNodeColor(node.node_type)}
                stroke={isSelected ? "#000" : "none"}
                strokeWidth={isSelected ? "2" : "0"}
                className={
                  isDragMode
                    ? "cursor-grab active:cursor-grabbing"
                    : isVersionDiffMode
                      ? "cursor-default"
                      : "cursor-pointer"
                }
                style={{ transition: isDragging ? "none" : "all 0.15s" }}
                onPointerDown={(e) => {
                  if (isDragMode) handlePointerDown(node.id, e);
                }}
                onClick={(e) => {
                  if (isVersionDiffMode) return;
                  if (!isDragMode) {
                    e.stopPropagation();
                    onNodeClick(node.id);
                  }
                }}
              />
              {/* Edge source highlight */}
              {isAddEdgeMode && state.edgeSourceNodeId === node.id && (
                <circle
                  cx={pos.x} cy={pos.y} r={18}
                  fill="none" stroke="#f59e0b" strokeWidth="3"
                  strokeDasharray="6,3"
                  className="pointer-events-none"
                />
              )}
              {(isSelected || isDragging) && (
                <text
                  x={pos.x} y={pos.y + radius + 15}
                  textAnchor="middle" fontSize="11" fill="currentColor"
                  className="text-main dark:text-darktext pointer-events-none font-semibold"
                  style={{ transition: isDragging ? "none" : "all 0.15s" }}
                >
                  {node.name}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default EditorCanvas;
