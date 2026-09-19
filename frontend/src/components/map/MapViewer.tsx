import { useState } from "react";
import type { GameMap, MapGraph } from "../../types/mapTypes";
import { imageRect, viewBox, type ImageFields } from "@/lib/map/view-box";
import { EdgeHitArea } from "@/components/map/edge-hit-area";
import { MapLegend } from "@/components/map/map-legend";
import { de } from "@/lib/de";

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
            <p className="text-mutedtext dark:text-darkmutedtext">{de.map.loading}</p>
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
            {de.map.loadFailed}
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
          <p className="text-mutedtext dark:text-darkmutedtext">
            {de.map.noGraph}
          </p>
        </div>
      </div>
    );
  }

  // Nodes, the map box and the image's drawn rectangle, from the shared module
  // (K-02). This viewer used to size itself from the nodes alone, which is why
  // it never showed the background at all and why an empty map gave it
  // Infinity.
  const padding = 60;
  const bg = imageRect(gameMap as ImageFields);
  const { minX, minY, width, height } = viewBox({
    nodes: mapGraph.nodes,
    mapWidth: (gameMap.x_dim ?? 10) * 100,
    mapHeight: (gameMap.y_dim ?? 10) * 100,
    image: bg,
    padding,
  });

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
          <p className="text-mutedtext dark:text-darkmutedtext">
            {gameMap.description}
          </p>
        )}
      </div>

      {/* Map Info */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 mb-8 border border-subtle dark:border-darksubtle">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">
              {de.editor.settings.maxPlayer}
            </p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {gameMap.max_player}
            </p>
          </div>
          <div>
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">
              {de.map.dimensions}
            </p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {gameMap.x_dim} × {gameMap.y_dim}
            </p>
          </div>
          <div>
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">{de.map.author}</p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {gameMap.author.username}
            </p>
          </div>
          <div>
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">
              {de.map.created}
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
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">{de.map.nodes}</p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {mapGraph.node_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">{de.map.edges}</p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {mapGraph.edge_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-mutedtext dark:text-darkmutedtext">
              {de.map.version}
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
              {/* The background image, under everything. The detail page did
                  not render it before F7, so a map calibrated in the editor
                  looked different here than in the game. */}
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
              {/* The grid has to start where the view box does: with a
                  negative minX it used to begin at the origin and leave the
                  left and top of the map ungridded. */}
              <rect x={minX} y={minY} width={width} height={height} fill="url(#grid)" />

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
                    {/* K-03: the click goes on the wide invisible stroke, not
                        on the 3-unit line, which was a one-pixel target. */}
                    <EdgeHitArea
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      onClick={() =>
                        setSelectedElement({ type: "edge", id: edge.id })
                      }
                    />
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={stroke}
                      strokeWidth={isSelected ? "5" : "3"}
                      strokeDasharray={strokeDasharray}
                      opacity={isSelected ? "1" : "0.6"}
                      className="pointer-events-none transition-all"
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
              {de.map.details}
            </h3>

            {selectedNode ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                    {de.editor.node.title}
                  </p>
                  <p className="font-semibold text-main dark:text-darktext">
                    {selectedNode.name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                    {de.editor.node.position}
                  </p>
                  <p className="text-sm text-main dark:text-darktext">
                    ({selectedNode.x_position}, {selectedNode.y_position})
                  </p>
                </div>
                <div>
                  <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                    {de.editor.node.types}
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
                  {de.map.clearSelection}
                </button>
              </div>
            ) : selectedEdge ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                    {de.editor.edge.title}
                  </p>
                  <p className="font-semibold text-main dark:text-darktext">
                    {selectedEdge.name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                    {de.editor.edge.type}
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
                        {de.editor.edge.train}
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
                    <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                      {de.editor.edge.accessibleBy}
                    </p>
                    <div className="flex gap-2 mt-1">
                      {selectedEdge.biking && (
                        <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 px-2 py-1 rounded">
                          {de.editor.edge.biking}
                        </span>
                      )}
                      {selectedEdge.walking && (
                        <span className="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 px-2 py-1 rounded">
                          {de.editor.edge.walking}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                <div>
                  <p className="text-xs text-mutedtext dark:text-darkmutedtext">
                    {de.editor.edge.maxLanes}
                  </p>
                  <p className="text-sm text-main dark:text-darktext">
                    {selectedEdge.max_lanes}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedElement(null)}
                  className="w-full mt-4 px-4 py-2 bg-main dark:bg-darktext text-white dark:text-black rounded hover:opacity-80 transition-opacity text-sm"
                >
                  {de.map.clearSelection}
                </button>
              </div>
            ) : (
              <p className="text-sm text-mutedtext dark:text-darkmutedtext">
                {de.map.pickHint}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* The shared legend (F7). This page had its own, in English and with
          colours hand-written next to the ones the SVG actually uses — the two
          had already drifted: the legend called a train line red and dashed
          while the renderer draws a dashed red one only when there is no
          street on the same edge. Now both come off `getEdgeColorAndStyle`. */}
      <MapLegend
        edges={[
          { color: "#6b7280", label: de.map.legend.street },
          { color: "#ef4444", label: de.map.legend.train, dash: "5,5" },
          { color: "#f97316", label: de.map.legend.streetAndTrain },
          { color: "#3b82f6", label: de.map.legend.bike },
          { color: "#22c55e", label: de.map.legend.walk },
          { color: "#a855f7", label: de.map.legend.bikeAndWalk },
        ]}
        nodes={[
          { color: "#22c55e", label: de.map.legend.home },
          { color: "#3b82f6", label: de.map.legend.workplace },
          { color: "#f59e0b", label: de.map.legend.station },
          { color: "#ef4444", label: de.map.legend.busStop },
        ]}
        className="rounded-lg border border-subtle bg-subtle p-6 dark:border-darksubtle dark:bg-darksubtle"
      />
    </div>
  );
};

export default MapViewer;
