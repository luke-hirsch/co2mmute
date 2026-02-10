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
  onCanvasClick: () => void;
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

const EditorCanvas = ({
  gameMap,
  mapGraph,
  state,
  ptLineEdgeIds,
  edgeChanges,
  onEdgeClick,
  onNodeClick,
  onCanvasClick,
}: EditorCanvasProps) => {
  if (!mapGraph || mapGraph.nodes.length === 0) {
    // Show empty canvas with background image if available
    const w = gameMap.x_dim * 100;
    const h = gameMap.y_dim * 100;
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-subtle dark:border-darksubtle overflow-hidden">
        <svg
          viewBox={`-60 -60 ${w + 120} ${h + 120}`}
          className="w-full"
          style={{ aspectRatio: `${w + 120}/${h + 120}`, minHeight: "500px" }}
          onClick={onCanvasClick}
        >
          <defs>
            <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
              <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect x="-60" y="-60" width={w + 120} height={h + 120} fill="url(#grid)" />
          {mapGraph?.background_image_url && (
            <image
              href={mapGraph.background_image_url}
              x={(mapGraph.image_offset_x ?? 0) * 100}
              y={(mapGraph.image_offset_y ?? 0) * 100}
              width={(mapGraph.x_dim ?? gameMap.x_dim) * 100 * (mapGraph.image_scale ?? 1)}
              height={(mapGraph.y_dim ?? gameMap.y_dim) * 100 * (mapGraph.image_scale ?? 1)}
              opacity={0.5}
              preserveAspectRatio="none"
              style={{
                clipPath: `inset(${mapGraph.image_crop_top ?? 0}% ${mapGraph.image_crop_right ?? 0}% ${mapGraph.image_crop_bottom ?? 0}% ${mapGraph.image_crop_left ?? 0}%)`,
              }}
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

  // Calculate SVG dimensions
  const padding = 60;
  const minX = Math.min(...mapGraph.nodes.map((n) => n.x_position * 100)) - padding;
  const minY = Math.min(...mapGraph.nodes.map((n) => n.y_position * 100)) - padding;
  const maxX = Math.max(...mapGraph.nodes.map((n) => n.x_position * 100)) + padding;
  const maxY = Math.max(...mapGraph.nodes.map((n) => n.y_position * 100)) + padding;
  const width = maxX - minX;
  const height = maxY - minY;

  // Build edge lookup for PT line overlay
  const nodeById = new Map(mapGraph.nodes.map((n) => [n.id, n]));
  const changedEdgeIds = new Set(edgeChanges.map((c) => c.edge_id));

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-subtle dark:border-darksubtle overflow-hidden">
      <svg
        viewBox={`${minX} ${minY} ${width} ${height}`}
        className="w-full"
        style={{ aspectRatio: `${width}/${height}`, minHeight: "500px" }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onCanvasClick();
        }}
      >
        <defs>
          <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
            <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect x={minX} y={minY} width={width} height={height} fill="url(#grid)" />

        {/* Background Image */}
        {mapGraph.background_image_url && (
          <image
            href={mapGraph.background_image_url}
            x={(mapGraph.image_offset_x ?? 0) * 100}
            y={(mapGraph.image_offset_y ?? 0) * 100}
            width={(mapGraph.x_dim ?? gameMap.x_dim) * 100 * (mapGraph.image_scale ?? 1)}
            height={(mapGraph.y_dim ?? gameMap.y_dim) * 100 * (mapGraph.image_scale ?? 1)}
            opacity={0.5}
            preserveAspectRatio="none"
            style={{
              clipPath: `inset(${mapGraph.image_crop_top ?? 0}% ${mapGraph.image_crop_right ?? 0}% ${mapGraph.image_crop_bottom ?? 0}% ${mapGraph.image_crop_left ?? 0}%)`,
            }}
          />
        )}

        {/* PT Line Overlay — existing lines */}
        {[...(mapGraph.bus_lines ?? []), ...(mapGraph.train_lines ?? [])].map(
          (line, lineIdx) => {
            const color = PT_LINE_COLORS[lineIdx % PT_LINE_COLORS.length];
            return (
              <g key={`ptline-${line.type}-${line.id}`}>
                {line.edges.map((edgeId: number) => {
                  const edge = mapGraph.edges.find((e) => e.id === edgeId);
                  if (!edge) return null;
                  const sn = nodeById.get(edge.start_node);
                  const en = nodeById.get(edge.end_node);
                  if (!sn || !en) return null;
                  return (
                    <line
                      key={`ptline-edge-${line.id}-${edgeId}`}
                      x1={sn.x_position * 100}
                      y1={sn.y_position * 100}
                      x2={en.x_position * 100}
                      y2={en.y_position * 100}
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
          return (
            <g key={`ptline-new-${edgeId}`}>
              <line
                x1={sn.x_position * 100}
                y1={sn.y_position * 100}
                x2={en.x_position * 100}
                y2={en.y_position * 100}
                stroke="#fbbf24"
                strokeWidth="8"
                opacity={0.6}
                strokeLinecap="round"
                strokeDasharray="10,5"
              />
              <text
                x={(sn.x_position * 100 + en.x_position * 100) / 2}
                y={(sn.y_position * 100 + en.y_position * 100) / 2 - 8}
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

          const x1 = startNode.x_position * 100;
          const y1 = startNode.y_position * 100;
          const x2 = endNode.x_position * 100;
          const y2 = endNode.y_position * 100;
          const isSelected = state.selectedEdgeIds.has(edge.id);
          const isInPtRoute = ptLineEdgeIds.includes(edge.id);
          const isChanged = changedEdgeIds.has(edge.id);
          const { stroke, strokeDasharray } = getEdgeColorAndStyle(edge);

          return (
            <g key={`edge-${edge.id}`}>
              {/* Diff highlight */}
              {isChanged && state.mode === "version-diff" && (
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="#fbbf24"
                  strokeWidth="8"
                  opacity={0.4}
                  strokeLinecap="round"
                />
              )}
              <line
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={stroke}
                strokeWidth={isSelected ? "3" : "2"}
                strokeDasharray={strokeDasharray}
                opacity={isSelected || isInPtRoute ? 1 : 0.6}
                className="cursor-pointer hover:opacity-100 transition-all"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdgeClick(edge.id);
                }}
              />
            </g>
          );
        })}

        {/* Nodes */}
        {mapGraph.nodes.map((node) => {
          const x = node.x_position * 100;
          const y = node.y_position * 100;
          const isSelected = state.selectedNodeId === node.id;
          const radius = isSelected ? 14 : 10;

          return (
            <g key={`node-${node.id}`}>
              <circle
                cx={x}
                cy={y}
                r={radius}
                fill={getNodeColor(node.node_type)}
                stroke={isSelected ? "#000" : "none"}
                strokeWidth={isSelected ? "2" : "0"}
                className="cursor-pointer transition-all"
                onClick={(e) => {
                  e.stopPropagation();
                  onNodeClick(node.id);
                }}
              />
              {isSelected && (
                <text
                  x={x} y={y + radius + 15}
                  textAnchor="middle" fontSize="11" fill="currentColor"
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
  );
};

export default EditorCanvas;
