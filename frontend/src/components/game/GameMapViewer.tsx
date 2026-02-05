import { useState } from "react";
import type { MapGraph } from "../../types/mapTypes";

interface GameMapViewerProps {
  mapGraph: MapGraph | null;
  isLoading?: boolean;
  error?: string | null;
  compact?: boolean;
  homeNodeId?: number;
  destinationNodeId?: number;
}

/**
 * Simplified map viewer for gameplay - shows the map without detailed info panels
 */
const GameMapViewer = ({
  mapGraph,
  isLoading = false,
  error = null,
  compact = false,
  homeNodeId,
  destinationNodeId,
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
          </defs>
          <rect
            x={minX}
            y={minY}
            width={width}
            height={height}
            fill="url(#gameGrid)"
          />

          {/* Edges */}
          {mapGraph.edges.map((edge) => {
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
                opacity="0.6"
              />
            );
          })}

          {/* Nodes */}
          {mapGraph.nodes.map((node) => {
            const x = node.x_position * 100;
            const y = node.y_position * 100;
            const isSelected = selectedNodeId === node.id;
            const isHomeNode = homeNodeId === node.id;
            const isDestinationNode = destinationNodeId === node.id;
            const radius = isSelected || isHomeNode || isDestinationNode ? 12 : 8;

            return (
              <g key={`node-${node.id}`}>
                <circle
                  cx={x}
                  cy={y}
                  r={radius}
                  fill={getNodeColor(node.node_type)}
                  stroke={isSelected ? "#000" : isHomeNode ? "#10b981" : isDestinationNode ? "#ef4444" : "none"}
                  strokeWidth={isSelected || isHomeNode || isDestinationNode ? "3" : "0"}
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
          {homeNodeId && mapGraph.nodes.find((n) => n.id === homeNodeId) && (() => {
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
                  🏠
                </text>
              </g>
            );
          })()}

          {/* Destination pin marker */}
          {destinationNodeId && mapGraph.nodes.find((n) => n.id === destinationNodeId) && (() => {
            const destNode = mapGraph.nodes.find((n) => n.id === destinationNodeId)!;
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
                  📍
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

      {/* Compact Legend */}
      {!compact && (
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
