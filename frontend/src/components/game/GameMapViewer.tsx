import { useState, useMemo } from "react";
import type { MapGraph, Node } from "../../types/mapTypes";
import type { RouteSegment, SegmentMode, ExtendedMapGraph } from "../../types/routeTypes";

interface GameMapViewerProps {
  mapGraph: MapGraph | ExtendedMapGraph | null;
  isLoading?: boolean;
  error?: string | null;
  compact?: boolean;
  homeNodeId?: number;
  destinationNodeId?: number;
  routeSegments?: RouteSegment[];
  highlightedNodes?: Set<number>;
  pathfindingVisited?: Set<number>;
  pathfindingCurrent?: number | null;
  // Dijkstra visualization props
  pathfindingExploredEdges?: Set<number>;
  pathfindingRelaxedEdge?: number | null;
  pathfindingDistances?: Map<number, number>;
  pathfindingFinalPath?: number[] | null;
  pathfindingPreviousEdges?: Map<number, number>;
  showDijkstraViz?: boolean;
  // Traffic heatmap overlay
  trafficHeatmap?: { edgeId: number; congestionRatio: number }[];
}

// Colors for different transport modes on route segments
const ROUTE_COLORS: Record<SegmentMode, string> = {
  car: "#ef4444", // Red
  bus: "#f97316", // Orange
  train: "#8b5cf6", // Purple
  bike: "#10b981", // Green
  walk: "#3b82f6", // Blue
};

/** Interpolate congestion ratio (0–1) to a green→yellow→orange→red color */
function getCongestionColor(ratio: number): string {
  const r = Math.max(0, Math.min(1, ratio));
  // 4-stop gradient: green(0) → yellow(0.33) → orange(0.66) → red(1)
  const stops = [
    { pos: 0, color: [34, 197, 94] },    // #22c55e green
    { pos: 0.33, color: [234, 179, 8] },  // #eab308 yellow
    { pos: 0.66, color: [249, 115, 22] }, // #f97316 orange
    { pos: 1, color: [239, 68, 68] },     // #ef4444 red
  ];
  let lo = stops[0], hi = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (r >= stops[i].pos && r <= stops[i + 1].pos) {
      lo = stops[i]; hi = stops[i + 1]; break;
    }
  }
  const t = lo.pos === hi.pos ? 0 : (r - lo.pos) / (hi.pos - lo.pos);
  const rgb = lo.color.map((c, i) => Math.round(c + t * (hi.color[i] - c)));
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

/** Stroke width scales with congestion: 3px (free flow) → 8px (gridlock) */
function getCongestionStrokeWidth(ratio: number): number {
  return 3 + Math.max(0, Math.min(1, ratio)) * 5;
}

/**
 * Simplified map viewer for gameplay - shows the map with route visualization
 */
const GameMapViewer = ({
  mapGraph,
  isLoading = false,
  error = null,
  compact = false,
  homeNodeId,
  destinationNodeId,
  routeSegments,
  highlightedNodes,
  pathfindingVisited,
  pathfindingCurrent,
  pathfindingExploredEdges,
  pathfindingRelaxedEdge,
  pathfindingDistances,
  pathfindingFinalPath,
  pathfindingPreviousEdges,
  showDijkstraViz = false,
  trafficHeatmap,
}: GameMapViewerProps) => {
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  // Build node lookup map for performance
  const nodeMap = useMemo(() => {
    const map = new Map<number, Node>();
    mapGraph?.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [mapGraph?.nodes]);

  // Build heatmap lookup map for O(1) access by edge ID
  const heatmapMap = useMemo(() => {
    if (!trafficHeatmap) return null;
    const map = new Map<number, number>();
    trafficHeatmap.forEach((e) => map.set(e.edgeId, e.congestionRatio));
    return map;
  }, [trafficHeatmap]);

  /**
   * Determine edge color and style based on edge type and properties.
   * Colors use a blue/slate palette to avoid colliding with the traffic
   * heatmap (green → yellow → orange → red) and route overlays.
   */
  const getEdgeColorAndStyle = (edge: any): {
    stroke: string;
    strokeDasharray: string;
    isTrain: boolean;
  } => {
    const hasStreetEdge = edge.street_edge !== null;
    const hasTrainEdge = edge.train_edge !== null;

    // Train-only edge — deep blue, long-dash pattern (railroad feel)
    if (hasTrainEdge && !hasStreetEdge) {
      return { stroke: "#3b82f6", strokeDasharray: "14,7", isTrain: true };
    }

    // Street + Train edge — medium blue, solid
    if (hasStreetEdge && hasTrainEdge) {
      return { stroke: "#60a5fa", strokeDasharray: "0", isTrain: true };
    }

    // Street-only edge — slate blue-gray
    if (hasStreetEdge) {
      return { stroke: "#94a3b8", strokeDasharray: "0", isTrain: false };
    }

    // Plain path — bike or walk or both
    if (edge.biking && !edge.walking) {
      return { stroke: "#34d399", strokeDasharray: "0", isTrain: false };
    }
    if (edge.walking && !edge.biking) {
      return { stroke: "#6ee7b7", strokeDasharray: "0", isTrain: false };
    }
    return { stroke: "#a5b4fc", strokeDasharray: "0", isTrain: false }; // indigo-200
  };

  const getNodeColor = (nodeTypes: any[]) => {
    const typeNames = nodeTypes.map((t) => t.name);
    if (typeNames.includes("home")) return "#10b981"; // Green
    if (typeNames.includes("workplace")) return "#3b82f6"; // Blue
    if (typeNames.includes("station")) return "#f59e0b"; // Amber
    if (typeNames.includes("bus_stop")) return "#a78bfa"; // Violet (was red, conflicts with heatmap)
    return "#64748b"; // Slate-500
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-2"></div>
          <p className="text-sm text-muted dark:text-darkmutedtext">
            Loading map...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
        <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
      </div>
    );
  }

  if (!mapGraph) {
    return (
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
        <p className="text-sm text-muted dark:text-darkmutedtext">
          No map data available
        </p>
      </div>
    );
  }

  // Build a set of real edge IDs that are part of the route (skip sentinel -1)
  const routeEdgeIds = new Set(
    (routeSegments ?? []).map((s) => s.edgeId).filter((id) => id >= 0)
  );

  console.log("[GameMapViewer] Rendering with:", {
    mapNodes: mapGraph?.nodes.length,
    mapEdges: mapGraph?.edges.length,
    routeSegments: routeSegments?.length ?? 0,
    routeEdgeIds: Array.from(routeEdgeIds),
    homeNodeId,
    destinationNodeId,
  });

  // Calculate SVG dimensions — always include map bounds so background image stays visible
  const padding = 40;
  const mapW = ("x_dim" in mapGraph ? (mapGraph.x_dim ?? 10) : 10) * 100;
  const mapH = ("y_dim" in mapGraph ? (mapGraph.y_dim ?? 10) : 10) * 100;
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

  const selectedNode = selectedNodeId
    ? mapGraph.nodes.find((n) => n.id === selectedNodeId)
    : null;

  // Compute background image geometry and optional SVG clip rect
  const getImageGeometry = () => {
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
    const hasCrop = ct > 0 || cr > 0 || cb > 0 || cl > 0;
    return {
      imgX, imgY, imgW, imgH, hasCrop,
      clipX: imgX + imgW * cl,
      clipY: imgY + imgH * ct,
      clipW: imgW * (1 - cl - cr),
      clipH: imgH * (1 - ct - cb),
    };
  };
  const img = getImageGeometry();

  return (
    <div className="w-full">
      {/* Map Container */}
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow border border-subtle dark:border-darksubtle overflow-hidden">
        <svg
          viewBox={`${minX} ${minY} ${width} ${height}`}
          className="w-full"
          style={{
            aspectRatio: `${width}/${height}`,
            minHeight: compact ? "200px" : "400px",
          }}
        >
          {/* Grid background */}
          <defs>
            <pattern
              id="gameGrid"
              width="100"
              height="100"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 100 0 L 0 0 0 100"
                fill="none"
                stroke="#e5e7eb"
                strokeWidth="0.5"
                className="dark:stroke-gray-700"
              />
            </pattern>
            {/* Glow filter for route edges */}
            <filter id="routeGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Glow filter for relaxed edge flash */}
            <filter id="relaxFlash" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Background image clip */}
            {img?.hasCrop && (
              <clipPath id="game-bg-img-clip">
                <rect x={img.clipX} y={img.clipY} width={img.clipW} height={img.clipH} />
              </clipPath>
            )}
          </defs>
          <rect
            x={minX}
            y={minY}
            width={width}
            height={height}
            fill="url(#gameGrid)"
          />

          {/* Background Image */}
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

          {/* Base Edges (non-route) */}
          {mapGraph.edges.map((edge) => {
            // Skip if this edge is part of the route (we'll render it separately)
            if (routeEdgeIds.has(edge.id)) return null;

            const startNode = nodeMap.get(edge.start_node);
            const endNode = nodeMap.get(edge.end_node);

            if (!startNode || !endNode) return null;

            const x1 = startNode.x_position * 100;
            const y1 = startNode.y_position * 100;
            const x2 = endNode.x_position * 100;
            const y2 = endNode.y_position * 100;
            const { stroke, strokeDasharray, isTrain } = getEdgeColorAndStyle(edge);

            // For train edges, compute tick positions along the edge
            const trainTicks: { tx: number; ty: number; angle: number }[] = [];
            if (isTrain) {
              const dx = x2 - x1;
              const dy = y2 - y1;
              const len = Math.sqrt(dx * dx + dy * dy);
              const angle = Math.atan2(dy, dx) * (180 / Math.PI);
              const tickSpacing = 24;
              const count = Math.floor(len / tickSpacing);
              for (let t = 1; t < count; t++) {
                const frac = (t * tickSpacing) / len;
                trainTicks.push({ tx: x1 + dx * frac, ty: y1 + dy * frac, angle });
              }
            }

            return (
              <g key={`edge-${edge.id}`}>
                {/* Dark border — slightly wider, rendered first */}
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="#0f172a"
                  strokeWidth="11"
                  strokeDasharray={strokeDasharray}
                  strokeLinecap="round"
                  opacity="0.35"
                />
                {/* Coloured main line */}
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={stroke}
                  strokeWidth="7"
                  strokeDasharray={strokeDasharray}
                  strokeLinecap="round"
                  opacity="0.65"
                />
                {/* Train tick marks (perpendicular lines = railroad sleepers) */}
                {trainTicks.map((tk, i) => (
                  <g key={i} transform={`translate(${tk.tx},${tk.ty}) rotate(${tk.angle + 90})`}>
                    <line x1="0" y1="-7" x2="0" y2="7" stroke={stroke} strokeWidth="4" opacity="0.8" />
                  </g>
                ))}
              </g>
            );
          })}

          {/* Traffic Heatmap overlay */}
          {heatmapMap && mapGraph.edges.map((edge) => {
            const ratio = heatmapMap.get(edge.id);
            if (ratio === undefined) return null;

            const sn = nodeMap.get(edge.start_node);
            const en = nodeMap.get(edge.end_node);
            if (!sn || !en) return null;

            return (
              <line
                key={`heatmap-${edge.id}`}
                x1={sn.x_position * 100}
                y1={sn.y_position * 100}
                x2={en.x_position * 100}
                y2={en.y_position * 100}
                stroke={getCongestionColor(ratio)}
                strokeWidth={getCongestionStrokeWidth(ratio)}
                strokeLinecap="round"
                opacity={0.8}
              />
            );
          })}

          {/* Dijkstra: Explored edges */}
          {showDijkstraViz && pathfindingExploredEdges && mapGraph.edges
            .filter((edge) => pathfindingExploredEdges.has(edge.id))
            .map((edge) => {
              const sn = nodeMap.get(edge.start_node);
              const en = nodeMap.get(edge.end_node);
              if (!sn || !en) return null;

              const x1 = sn.x_position * 100;
              const y1 = sn.y_position * 100;
              const x2 = en.x_position * 100;
              const y2 = en.y_position * 100;
              const isRelaxed = pathfindingRelaxedEdge === edge.id;
              const isOnTree = pathfindingPreviousEdges
                ? Array.from(pathfindingPreviousEdges.values()).includes(edge.id)
                : false;

              return (
                <line
                  key={`explored-edge-${edge.id}`}
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={isRelaxed ? "#fbbf24" : isOnTree ? "#34d399" : "#93c5fd"}
                  strokeWidth={isRelaxed ? "5" : "3"}
                  opacity={isRelaxed ? 1.0 : 0.6}
                  strokeLinecap="round"
                  filter={isRelaxed ? "url(#relaxFlash)" : undefined}
                />
              );
            })}

          {/* Dijkstra: Final shortest path highlight */}
          {showDijkstraViz && pathfindingFinalPath && pathfindingFinalPath.length > 1 &&
            pathfindingFinalPath.slice(0, -1).map((nId, i) => {
              const nextId = pathfindingFinalPath[i + 1];
              const sn = nodeMap.get(nId);
              const en = nodeMap.get(nextId);
              if (!sn || !en) return null;

              const x1 = sn.x_position * 100;
              const y1 = sn.y_position * 100;
              const x2 = en.x_position * 100;
              const y2 = en.y_position * 100;

              return (
                <g key={`final-path-${nId}-${nextId}`}>
                  <line
                    x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke="#f59e0b"
                    strokeWidth="10"
                    opacity={0.3}
                    strokeLinecap="round"
                  />
                  <line
                    x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke="#f59e0b"
                    strokeWidth="4"
                    opacity={1}
                    strokeLinecap="round"
                  />
                </g>
              );
            })}

          {/* Route Edges (highlighted) */}
          {routeSegments?.map((segment, index) => {
            const startNode = nodeMap.get(segment.startNode);
            const endNode = nodeMap.get(segment.endNode);

            if (!startNode || !endNode) return null;

            const x1 = startNode.x_position * 100;
            const y1 = startNode.y_position * 100;
            const x2 = endNode.x_position * 100;
            const y2 = endNode.y_position * 100;

            const color = ROUTE_COLORS[segment.mode] || "#6b7280";

            // Calculate arrow position (midpoint)
            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;

            // Calculate angle for direction arrow
            const angle = Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI);

            return (
              <g key={`route-segment-${index}`}>
                {/* Dark border for contrast against heatmap and base edges */}
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="#0f172a"
                  strokeWidth="14"
                  strokeLinecap="round"
                  opacity="0.45"
                />
                {/* Outer glow */}
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={color}
                  strokeWidth="12"
                  strokeLinecap="round"
                  opacity="0.25"
                />
                {/* Main line */}
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={color}
                  strokeWidth="6"
                  strokeLinecap="round"
                  strokeDasharray={segment.mode === "walk" ? "10,5" : "0"}
                  opacity="1"
                />
                {/* Direction arrow */}
                <g transform={`translate(${midX}, ${midY}) rotate(${angle})`}>
                  <polygon points="0,-5 10,0 0,5" fill={color} opacity="0.95" />
                </g>
                {/* Segment number label */}
                {routeSegments.length > 1 && (
                  <g transform={`translate(${midX}, ${midY})`}>
                    <circle r="9" fill="white" stroke={color} strokeWidth="2" opacity="0.95" />
                    <text
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="9"
                      fill={color}
                      fontWeight="bold"
                    >
                      {index + 1}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Pathfinding visualization - visited nodes */}
          {pathfindingVisited && Array.from(pathfindingVisited).map((nodeId) => {
            const node = nodeMap.get(nodeId);
            if (!node) return null;
            const x = node.x_position * 100;
            const y = node.y_position * 100;

            return (
              <circle
                key={`visited-${nodeId}`}
                cx={x}
                cy={y}
                r={12}
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
                opacity="0.5"
              />
            );
          })}

          {/* Dijkstra: Distance labels on visited nodes */}
          {showDijkstraViz && pathfindingDistances && pathfindingVisited &&
            Array.from(pathfindingVisited).map((nodeId) => {
              const node = nodeMap.get(nodeId);
              if (!node) return null;
              const dist = pathfindingDistances.get(nodeId);
              if (dist === undefined || dist === Infinity) return null;

              const x = node.x_position * 100;
              const y = node.y_position * 100;

              return (
                <g key={`dist-label-${nodeId}`}>
                  <rect
                    x={x + 10}
                    y={y - 16}
                    width={32}
                    height={14}
                    rx={3}
                    fill="white"
                    stroke="#cbd5e1"
                    strokeWidth="0.5"
                    opacity={0.85}
                  />
                  <text
                    x={x + 26}
                    y={y - 6}
                    textAnchor="middle"
                    fontSize="8"
                    fill="#475569"
                    fontFamily="monospace"
                    className="pointer-events-none"
                  >
                    {dist < 100 ? dist.toFixed(1) : Math.round(dist)}
                  </text>
                </g>
              );
            })}

          {/* Pathfinding visualization - current node */}
          {pathfindingCurrent && (() => {
            const node = nodeMap.get(pathfindingCurrent);
            if (!node) return null;
            const x = node.x_position * 100;
            const y = node.y_position * 100;

            return (
              <circle
                key="current-node"
                cx={x}
                cy={y}
                r={16}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="3"
                className="animate-pulse"
              />
            );
          })()}

          {/* Nodes */}
          {mapGraph.nodes.map((node) => {
            const x = node.x_position * 100;
            const y = node.y_position * 100;
            const isSelected = selectedNodeId === node.id;
            const isHomeNode = homeNodeId === node.id;
            const isDestinationNode = destinationNodeId === node.id;
            const isHighlighted = highlightedNodes?.has(node.id);
            const radius = isSelected || isHomeNode || isDestinationNode ? 12 : isHighlighted ? 10 : 8;

            return (
              <g key={`node-${node.id}`}>
                <circle
                  cx={x}
                  cy={y}
                  r={radius}
                  fill={getNodeColor(node.node_type)}
                  stroke={
                    isSelected
                      ? "#000"
                      : isHomeNode
                        ? "#10b981"
                        : isDestinationNode
                          ? "#ef4444"
                          : isHighlighted
                            ? "#f59e0b"
                            : "none"
                  }
                  strokeWidth={
                    isSelected || isHomeNode || isDestinationNode || isHighlighted ? "3" : "0"
                  }
                  className="cursor-pointer transition-all hover:opacity-80"
                  onClick={() => setSelectedNodeId(isSelected ? null : node.id)}
                />
                {isSelected && (
                  <text
                    x={x}
                    y={y + radius + 12}
                    textAnchor="middle"
                    fontSize="10"
                    fill="currentColor"
                    className="text-main dark:text-darktext pointer-events-none font-semibold"
                  >
                    {node.name}
                  </text>
                )}
              </g>
            );
          })}

          {/* Home pin marker */}
          {homeNodeId &&
            mapGraph.nodes.find((n) => n.id === homeNodeId) &&
            (() => {
              const homeNode = mapGraph.nodes.find((n) => n.id === homeNodeId)!;
              const x = homeNode.x_position * 100;
              const y = homeNode.y_position * 100;
              return (
                <g key="home-pin">
                  {/* Pin shape */}
                  <path
                    d={`M ${x} ${y - 30}
                      C ${x - 12} ${y - 30} ${x - 12} ${y - 18} ${x} ${y - 12}
                      C ${x + 12} ${y - 18} ${x + 12} ${y - 30} ${x} ${y - 30}
                      L ${x} ${y - 8}`}
                    fill="#10b981"
                    stroke="#065f46"
                    strokeWidth="1"
                  />
                  {/* Home icon */}
                  <text
                    x={x}
                    y={y - 18}
                    textAnchor="middle"
                    fontSize="10"
                    fill="white"
                    className="pointer-events-none"
                  >
                    H
                  </text>
                </g>
              );
            })()}

          {/* Destination pin marker */}
          {destinationNodeId &&
            mapGraph.nodes.find((n) => n.id === destinationNodeId) &&
            (() => {
              const destNode = mapGraph.nodes.find(
                (n) => n.id === destinationNodeId
              )!;
              const x = destNode.x_position * 100;
              const y = destNode.y_position * 100;
              return (
                <g key="dest-pin">
                  {/* Pin shape */}
                  <path
                    d={`M ${x} ${y - 30}
                      C ${x - 12} ${y - 30} ${x - 12} ${y - 18} ${x} ${y - 12}
                      C ${x + 12} ${y - 18} ${x + 12} ${y - 30} ${x} ${y - 30}
                      L ${x} ${y - 8}`}
                    fill="#ef4444"
                    stroke="#991b1b"
                    strokeWidth="1"
                  />
                  {/* Target icon */}
                  <text
                    x={x}
                    y={y - 18}
                    textAnchor="middle"
                    fontSize="10"
                    fill="white"
                    className="pointer-events-none"
                  >
                    D
                  </text>
                </g>
              );
            })()}
        </svg>
      </div>

      {/* Traffic Heatmap Legend */}
      {trafficHeatmap && trafficHeatmap.length > 0 && (
        <div className="mt-3 p-3 bg-subtle dark:bg-darksubtle rounded text-xs border border-gray-200 dark:border-gray-700">
          <div className="font-semibold mb-2">Traffic Congestion</div>
          <div className="flex items-center gap-2">
            <span className="text-muted dark:text-darkmutedtext">Free flow</span>
            <div
              className="flex-1 h-2.5 rounded"
              style={{
                background: "linear-gradient(to right, #22c55e, #eab308, #f97316, #ef4444)",
              }}
            />
            <span className="text-muted dark:text-darkmutedtext">Gridlock</span>
          </div>
        </div>
      )}

      {/* Selected Node Info (compact) */}
      {selectedNode && (
        <div className="mt-2 p-2 bg-subtle dark:bg-darksubtle rounded text-sm">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{selectedNode.name}</span>
            <div className="flex gap-1">
              {selectedNode.node_type.map((t) => (
                <span
                  key={t.id}
                  className="text-xs bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded"
                >
                  {t.short}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Route Legend */}
      {routeSegments && routeSegments.length > 0 && (
        <div className="mt-3 p-3 bg-subtle dark:bg-darksubtle rounded text-xs border border-gray-200 dark:border-gray-700">
          <div className="font-semibold mb-2 flex items-center justify-between">
            <span>Route ({routeSegments.length} segments)</span>
            <span className="text-muted dark:text-darkmutedtext font-normal">
              {(routeSegments.reduce((sum, s) => sum + s.distanceM, 0) / 1000).toFixed(1)} km
              {" | "}
              {Math.round(routeSegments.reduce((sum, s) => sum + s.estimatedTimeMin, 0))} min
            </span>
          </div>
          <div className="flex flex-wrap gap-3">
            {Array.from(new Set(routeSegments.map((s) => s.mode))).map((mode) => {
              const modeSegments = routeSegments.filter((s) => s.mode === mode);
              const modeDistance = modeSegments.reduce((sum, s) => sum + s.distanceM, 0);
              return (
                <div key={mode} className="flex items-center gap-1.5">
                  <div
                    className="w-5 h-1.5 rounded"
                    style={{ backgroundColor: ROUTE_COLORS[mode] }}
                  ></div>
                  <span className="capitalize font-medium">{mode}</span>
                  <span className="text-muted dark:text-darkmutedtext">
                    ({(modeDistance / 1000).toFixed(1)}km)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Compact Legend */}
      {!compact && !routeSegments && (
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted dark:text-darkmutedtext">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span>Home</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span>Work</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span>Station</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-violet-400"></div>
            <span>Bus stop</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default GameMapViewer;
