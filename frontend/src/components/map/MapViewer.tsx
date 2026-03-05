import { useState } from "react";
import type { GameMap, MapGraph } from "../../types/mapTypes";

interface SelectedElement {
  type: "node" | "edge";
  id: number;
}

interface MapViewerProps {
  gameMap: GameMap;
  mapGraph: MapGraph | null;
  isLoading?: boolean;
  error?: string | null;
}

const MapViewer = ({
  gameMap,
  mapGraph,
  isLoading = false,
  error = null,
}: MapViewerProps) => {
  const [selectedElement, setSelectedElement] =
    useState<SelectedElement | null>(null);

  /**
   * Determine edge color and style based on edge type and properties
   * - Plain edges (park paths): green (walk) or blue (bike) or purple (both)
   * - Street edges: gray for regular streets
   * - Train edges: red for train tracks
   * - Mixed (street + train): orange
   */
  const getEdgeColorAndStyle = (edge: any) => {
    const hasStreetEdge = edge.street_edge !== null;
    const hasTrainEdge = edge.train_edge !== null;

    // Train-only edge
    if (hasTrainEdge && !hasStreetEdge) {
      return {
        stroke: "#ef4444", // Red
        strokeDasharray: "5,5", // Dashed for train
      };
    }

    // Street + Train edge
    if (hasStreetEdge && hasTrainEdge) {
      return {
        stroke: "#f97316", // Orange
        strokeDasharray: "0", // Solid
      };
    }

    // Street-only edge
    if (hasStreetEdge) {
      return {
        stroke: "#6b7280", // Gray
        strokeDasharray: "0", // Solid
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

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-main mx-auto mb-4"></div>
            <p className="text-muted dark:text-darkmutedtext">Loading map...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-red-800 dark:text-red-200 mb-2">
            Error Loading Map
          </h3>
          <p className="text-red-700 dark:text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (!mapGraph) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 border border-subtle dark:border-darksubtle">
          <p className="text-muted dark:text-darkmutedtext">
            No graph data available
          </p>
        </div>
      </div>
    );
  }

  // Calculate SVG dimensions with padding
  const padding = 60;
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

  const getNodeColor = (nodeTypes: any[]) => {
    const typeNames = nodeTypes.map((t) => t.name);
    if (typeNames.includes("home")) return "#10b981"; // Green
    if (typeNames.includes("workplace")) return "#3b82f6"; // Blue
    if (typeNames.includes("station")) return "#f59e0b"; // Amber
    if (typeNames.includes("bus_stop")) return "#ef4444"; // Red
    return "#6b7280"; // Gray
  };

  const selectedNode =
    selectedElement?.type === "node"
      ? mapGraph.nodes.find((n) => n.id === selectedElement.id)
      : null;
  const selectedEdge =
    selectedElement?.type === "edge"
      ? mapGraph.edges.find((e) => e.id === selectedElement.id)
      : null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-main dark:text-darktext mb-2">
          {gameMap.name}
        </h1>
        {gameMap.description && (
          <p className="text-muted dark:text-darkmutedtext">
            {gameMap.description}
          </p>
        )}
      </div>

      {/* Map Info */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 mb-8 border border-subtle dark:border-darksubtle">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Max Players
            </p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {gameMap.max_player}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Dimensions
            </p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {gameMap.x_dim} × {gameMap.y_dim}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">Author</p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {gameMap.author.username}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Created
            </p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {new Date(gameMap.created).toLocaleDateString()}
            </p>
          </div>
        </div>
      </div>

      {/* Graph Stats */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 mb-8 border border-subtle dark:border-darksubtle">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">Nodes</p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {mapGraph.node_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">Edges</p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {mapGraph.edge_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Version
            </p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {mapGraph.version_name}
            </p>
          </div>
        </div>
      </div>

      {/* Main content: SVG map + info panel */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 mb-8">
        {/* SVG Map */}
        <div className="lg:col-span-3">
          <div className="bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-subtle dark:border-darksubtle overflow-hidden">
            <svg
              viewBox={`${minX} ${minY} ${width} ${height}`}
              className="w-full"
              style={{ aspectRatio: `${width}/${height}`, minHeight: "500px" }}
            >
              {/* Grid background */}
              <defs>
                <pattern
                  id="grid"
                  width="100"
                  height="100"
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d={`M 100 0 L 0 0 0 100`}
                    fill="none"
                    stroke="#e5e7eb"
                    strokeWidth="0.5"
                  />
                </pattern>
              </defs>
              <rect width={width} height={height} fill="url(#grid)" />

              {/* Edges */}
              {mapGraph.edges.map((edge) => {
                const startNode = mapGraph.nodes.find(
                  (n) => n.id === edge.start_node
                );
                const endNode = mapGraph.nodes.find(
                  (n) => n.id === edge.end_node
                );

                if (!startNode || !endNode) return null;

                const x1 = startNode.x_position * 100;
                const y1 = startNode.y_position * 100;
                const x2 = endNode.x_position * 100;
                const y2 = endNode.y_position * 100;
                const isSelected = selectedElement?.id === edge.id;
                const { stroke, strokeDasharray } = getEdgeColorAndStyle(edge);

                return (
                  <g key={`edge-${edge.id}`}>
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={stroke}
                      strokeWidth={isSelected ? "5" : "3"}
                      strokeDasharray={strokeDasharray}
                      opacity={isSelected ? "1" : "0.6"}
                      className="cursor-pointer hover:opacity-100 transition-all"
                      onClick={() =>
                        setSelectedElement({ type: "edge", id: edge.id })
                      }
                    />
                  </g>
                );
              })}

              {/* Nodes */}
              {mapGraph.nodes.map((node) => {
                const x = node.x_position * 100;
                const y = node.y_position * 100;
                const isSelected = selectedElement?.id === node.id;
                const radius = isSelected ? 14 : 10;

                return (
                  <g key={`node-${node.id}`}>
                    {/* Node circle */}
                    <circle
                      cx={x}
                      cy={y}
                      r={radius}
                      fill={getNodeColor(node.node_type)}
                      stroke={isSelected ? "#000" : "none"}
                      strokeWidth={isSelected ? "2" : "0"}
                      className="cursor-pointer transition-all"
                      onClick={() =>
                        setSelectedElement({ type: "node", id: node.id })
                      }
                    />
                    {/* Tooltip on hover (text only shows on selection) */}
                    {isSelected && (
                      <text
                        x={x}
                        y={y + radius + 15}
                        textAnchor="middle"
                        fontSize="11"
                        fill="currentColor"
                        className="text-main dark:text-darktext pointer-events-none font-semibold"
                      >
                        {node.name}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Info Panel */}
        <div className="lg:col-span-1">
          <div className="sticky top-8 bg-subtle dark:bg-darksubtle rounded-lg p-6 border border-subtle dark:border-darksubtle">
            <h3 className="text-lg font-semibold text-main dark:text-darktext mb-4">
              Details
            </h3>

            {selectedNode ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    Node
                  </p>
                  <p className="font-semibold text-main dark:text-darktext">
                    {selectedNode.name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    Position
                  </p>
                  <p className="text-sm text-main dark:text-darktext">
                    ({selectedNode.x_position}, {selectedNode.y_position})
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    Types
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedNode.node_type.map((t) => (
                      <span
                        key={t.id}
                        className="inline-block bg-main dark:bg-darktext text-white dark:text-black text-xs px-2 py-1 rounded"
                      >
                        {t.short}
                      </span>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => setSelectedElement(null)}
                  className="w-full mt-4 px-4 py-2 bg-main dark:bg-darktext text-white dark:text-black rounded hover:opacity-80 transition-opacity text-sm"
                >
                  Clear Selection
                </button>
              </div>
            ) : selectedEdge ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    Edge
                  </p>
                  <p className="font-semibold text-main dark:text-darktext">
                    {selectedEdge.name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    Edge Type
                  </p>
                  <div className="flex flex-col gap-2 mt-1">
                    {selectedEdge.street_edge ? (
                      <span className="text-xs bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-100 px-2 py-1 rounded">
                        Street ({selectedEdge.street_edge.speed_limit} km/h,{" "}
                        {selectedEdge.street_edge.lanes} lane
                        {selectedEdge.street_edge.lanes !== 1 ? "s" : ""})
                        {selectedEdge.street_edge.dedicated_bus_lane && (
                          <span className="ml-1">+ Bus Lane</span>
                        )}
                      </span>
                    ) : null}
                    {selectedEdge.train_edge ? (
                      <span className="text-xs bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 px-2 py-1 rounded">
                        Train
                      </span>
                    ) : null}
                    {!selectedEdge.street_edge && !selectedEdge.train_edge ? (
                      <span className="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 px-2 py-1 rounded">
                        Path
                      </span>
                    ) : null}
                  </div>
                </div>
                {(selectedEdge.biking || selectedEdge.walking) && (
                  <div>
                    <p className="text-xs text-muted dark:text-darkmutedtext">
                      Accessible By
                    </p>
                    <div className="flex gap-2 mt-1">
                      {selectedEdge.biking && (
                        <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 px-2 py-1 rounded">
                          Biking
                        </span>
                      )}
                      {selectedEdge.walking && (
                        <span className="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 px-2 py-1 rounded">
                          Walking
                        </span>
                      )}
                    </div>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    Max Lanes
                  </p>
                  <p className="text-sm text-main dark:text-darktext">
                    {selectedEdge.max_lanes}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedElement(null)}
                  className="w-full mt-4 px-4 py-2 bg-main dark:bg-darktext text-white dark:text-black rounded hover:opacity-80 transition-opacity text-sm"
                >
                  Clear Selection
                </button>
              </div>
            ) : (
              <p className="text-sm text-muted dark:text-darkmutedtext">
                Click on a node or edge to view details
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 border border-subtle dark:border-darksubtle">
        <h2 className="text-lg font-semibold text-main dark:text-darktext mb-4">
          Legend
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-main dark:text-darktext mb-3">
              Node Types
            </h3>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-green-500"></div>
                <span className="text-muted dark:text-darkmutedtext">Home</span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-blue-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Workplace
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-amber-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Station
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-red-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Bus Stop
                </span>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-main dark:text-darktext mb-3">
              Edge Types
            </h3>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-green-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Walking Path
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-blue-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Biking Path
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-purple-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Walking & Biking
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-gray-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Street
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div
                  className="w-8 h-0.5 bg-red-500"
                  style={{ strokeDasharray: "5,5" }}
                ></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Train Line
                </span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-orange-500"></div>
                <span className="text-muted dark:text-darkmutedtext">
                  Street + Train
                </span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapViewer;
