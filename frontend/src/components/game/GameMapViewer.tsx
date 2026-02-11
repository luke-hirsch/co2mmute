import { useState } from "react";
import type { MapGraph } from "../../types/mapTypes";
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
}

// Colors for different transport modes on route segments
const ROUTE_COLORS: Record<SegmentMode, string> = {
  car: "#ef4444", // Red
  bus: "#f97316", // Orange
  train: "#8b5cf6", // Purple
  bike: "#10b981", // Green
  walk: "#3b82f6", // Blue
};

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
}: GameMapViewerProps) => {
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  /**
   * Determine edge color and style based on edge type and properties
   */
  const getEdgeColorAndStyle = (edge: any) => {
    const hasStreetEdge = edge.street_edge !== null;
    const hasTrainEdge = edge.train_edge !== null;

    // Train-only edge
    if (hasTrainEdge && !hasStreetEdge) {
      return {
        stroke: "#ef4444", // Red
        strokeDasharray: "5,5",
      };
    }

    // Street + Train edge
    if (hasStreetEdge && hasTrainEdge) {
      return {
        stroke: "#f97316", // Orange
        strokeDasharray: "0",
      };
    }

    // Street-only edge
    if (hasStreetEdge) {
      return {
        stroke: "#6b7280", // Gray
        strokeDasharray: "0",
      };
    }

    // Plain edge (park path) - use biking/walking flags
    if (edge.biking && !edge.walking) {
      return {
        stroke: "#3b82f6", // Blue for bike
        strokeDasharray: "0",
      };
    }
    if (edge.walking && !edge.biking) {
      return {
        stroke: "#10b981", // Green for walk
        strokeDasharray: "0",
      };
    }
    // Both biking and walking
    return {
      stroke: "#8b5cf6", // Purple for both
      strokeDasharray: "0",
    };
  };

  const getNodeColor = (nodeTypes: any[]) => {
    const typeNames = nodeTypes.map((t) => t.name);
    if (typeNames.includes("home")) return "#10b981"; // Green
    if (typeNames.includes("workplace")) return "#3b82f6"; // Blue
    if (typeNames.includes("station")) return "#f59e0b"; // Amber
    if (typeNames.includes("bus_stop")) return "#ef4444"; // Red
    return "#6b7280"; // Gray
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

  // Build a set of edge IDs that are part of the route
  const routeEdgeIds = new Set(routeSegments?.map((s) => s.edgeId) ?? []);

  console.log("[GameMapViewer] Rendering with:", {
    mapNodes: mapGraph?.nodes.length,
    mapEdges: mapGraph?.edges.length,
    routeSegments: routeSegments?.length ?? 0,
    routeEdgeIds: Array.from(routeEdgeIds),
    homeNodeId,
    destinationNodeId,
  });

  // Calculate SVG dimensions with padding
  const padding = 40;
  const minX =
    Math.min(...mapGraph.nodes.map((n) => n.x_position * 100)) - padding;
  const minY =
    Math.min(...mapGraph.nodes.map((n) => n.y_position * 100)) - padding;
  const maxX =
    Math.max(...mapGraph.nodes.map((n) => n.x_position * 100)) + padding;
  const maxY =
    Math.max(...mapGraph.nodes.map((n) => n.y_position * 100)) + padding;
  const width = maxX - minX;
  const height = maxY - minY;

  const selectedNode = selectedNodeId
    ? mapGraph.nodes.find((n) => n.id === selectedNodeId)
    : null;

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
          </defs>
          <rect
            x={minX}
            y={minY}
            width={width}
            height={height}
            fill="url(#gameGrid)"
          />

          {/* Background Image */}
          {"background_image_url" in mapGraph &&
            mapGraph.background_image_url && (
              <image
                href={mapGraph.background_image_url}
                x={(mapGraph.image_offset_x ?? 0) * 100}
                y={(mapGraph.image_offset_y ?? 0) * 100}
                width={
                  (mapGraph.x_dim ?? 10) * 100 * (mapGraph.image_scale ?? 1)
                }
                height={
                  (mapGraph.y_dim ?? 10) * 100 * (mapGraph.image_scale ?? 1)
                }
                opacity={0.4}
                preserveAspectRatio="none"
                style={{
                  clipPath: `inset(${mapGraph.image_crop_top ?? 0}% ${mapGraph.image_crop_right ?? 0}% ${mapGraph.image_crop_bottom ?? 0}% ${mapGraph.image_crop_left ?? 0}%)`,
                }}
              />
            )}

          {/* Base Edges (non-route) */}
          {mapGraph.edges.map((edge) => {
            // Skip if this edge is part of the route (we'll render it separately)
            if (routeEdgeIds.has(edge.id)) return null;

            const startNode = mapGraph.nodes.find(
              (n) => n.id === edge.start_node
            );
            const endNode = mapGraph.nodes.find((n) => n.id === edge.end_node);

            if (!startNode || !endNode) return null;

            const x1 = startNode.x_position * 100;
            const y1 = startNode.y_position * 100;
            const x2 = endNode.x_position * 100;
            const y2 = endNode.y_position * 100;
            const { stroke, strokeDasharray } = getEdgeColorAndStyle(edge);

            return (
              <line
                key={`edge-${edge.id}`}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={stroke}
                strokeWidth="2"
                strokeDasharray={strokeDasharray}
                opacity="0.4"
              />
            );
          })}

          {/* Route Edges (highlighted) */}
          {routeSegments?.map((segment, index) => {
            const edge = mapGraph.edges.find((e) => e.id === segment.edgeId);
            if (!edge) return null;

            const startNode = mapGraph.nodes.find(
              (n) => n.id === segment.startNode
            );
            const endNode = mapGraph.nodes.find(
              (n) => n.id === segment.endNode
            );

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
                {/* Outer glow for visibility */}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={color}
                  strokeWidth="12"
                  opacity="0.2"
                  strokeLinecap="round"
                />
                {/* Inner glow */}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={color}
                  strokeWidth="8"
                  opacity="0.4"
                  strokeLinecap="round"
                />
                {/* Main line */}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={color}
                  strokeWidth="4"
                  opacity="1"
                  strokeLinecap="round"
                  strokeDasharray={segment.mode === "walk" ? "8,4" : "0"}
                  className={segment.mode !== "walk" ? "animate-pulse" : ""}
                />
                {/* Direction arrow at midpoint */}
                <g transform={`translate(${midX}, ${midY}) rotate(${angle})`}>
                  <polygon
                    points="0,-4 8,0 0,4"
                    fill={color}
                    opacity="0.9"
                  />
                </g>
                {/* Segment number label */}
                {routeSegments.length > 1 && (
                  <g transform={`translate(${midX}, ${midY})`}>
                    <circle r="8" fill="white" stroke={color} strokeWidth="1.5" />
                    <text
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="8"
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
            const node = mapGraph.nodes.find((n) => n.id === nodeId);
            if (!node) return null;
            const x = node.x_position * 100;
            const y = node.y_position * 100;

            return (
              <circle
                key={`visited-${nodeId}`}
                cx={x}
                cy={y}
                r={14}
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
                opacity="0.5"
              />
            );
          })}

          {/* Pathfinding visualization - current node */}
          {pathfindingCurrent && (() => {
            const node = mapGraph.nodes.find((n) => n.id === pathfindingCurrent);
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
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span>Bus</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default GameMapViewer;
