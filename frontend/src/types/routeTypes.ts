/**
 * Route types for traffic simulation pathfinding
 */

// Transport modes
export type TransportMode = "car" | "public" | "bike" | "walk";
export type SegmentMode = "car" | "bus" | "train" | "bike" | "walk";
export type CarOptimization = "time" | "distance" | "co2";

// Route segment representing one edge in the path
export interface RouteSegment {
  edgeId: number;
  startNode: number;
  endNode: number;
  mode: SegmentMode;
  ptLineId?: number; // For bus/train segments
  distanceM: number;
  estimatedTimeMin: number;
}

// Complete route for an agent
export interface AgentRoute {
  agentId: number;
  transportMode: TransportMode;
  optimization?: CarOptimization;
  totalDistanceM: number;
  estimatedTimeMin: number;
  segments: RouteSegment[];
}

// Payload for route submission to backend
export interface RouteSubmissionPayload {
  agents: AgentRouteSubmission[];
}

export interface AgentRouteSubmission {
  id: number; // agent_id
  transport_mode: TransportMode;
  optimization?: CarOptimization;
  route: {
    total_distance_m: number;
    estimated_time_min: number;
    segments: RouteSegmentSubmission[];
  };
}

export interface RouteSegmentSubmission {
  edge_id: number;
  start_node: number;
  end_node: number;
  mode: SegmentMode;
  pt_line_id?: number;
}

// Pathfinding visualization state
export interface PathfindingState {
  isRunning: boolean;
  visitedNodes: Set<number>;
  currentNode: number | null;
  tentativeDistances: Map<number, number>;
  previousNodes: Map<number, number>; // For reconstructing path
  finalPath: number[] | null;
  isComplete: boolean;
}

// Traffic data from previous rounds (for car time optimization)
export interface EdgeTrafficData {
  edgeId: number;
  avgSpeedKmh: number;
  congestionLevel: "low" | "medium" | "high";
}

// Public transport line info
export interface PTLine {
  id: number;
  name: string;
  type: "bus" | "train";
  interval: number; // Minutes between vehicles
  capacity: number;
  edges: number[]; // Ordered edge IDs
  stops: number[]; // Ordered node IDs (stations/bus_stops)
}

// Extended map graph with PT lines
export interface ExtendedMapGraph {
  map_id: number;
  version_id: number;
  version_name: string;
  version_description?: string;
  nodes: import("./mapTypes").Node[];
  edges: import("./mapTypes").Edge[];
  node_count: number;
  edge_count: number;
  bus_lines: PTLine[];
  train_lines: PTLine[];
  scale: number; // Meters per coordinate unit
  previous_round_traffic?: EdgeTrafficData[];
  // Background image
  x_dim?: number;
  y_dim?: number;
  background_image_url?: string | null;
  image_offset_x?: number;
  image_offset_y?: number;
  image_scale?: number;
  image_crop_top?: number;
  image_crop_right?: number;
  image_crop_bottom?: number;
  image_crop_left?: number;
}

// Pathfinding options
export interface PathfindingOptions {
  mode: TransportMode;
  optimization?: CarOptimization; // Only for car mode
  trafficData?: EdgeTrafficData[]; // From previous round
  animationSpeed?: number; // ms per step, 0 = no animation
}

// Pathfinding result
export interface PathfindingResult {
  success: boolean;
  path: number[]; // Node IDs
  segments: RouteSegment[];
  totalDistanceM: number;
  estimatedTimeMin: number;
  error?: string;
}

// PT routing result with walking segments
export interface PTRoutingResult {
  success: boolean;
  walkToStation: RouteSegment[];
  ptSegments: RouteSegment[]; // May include transfers
  walkFromStation: RouteSegment[];
  totalDistanceM: number;
  totalTimeMin: number;
  waitTimeMin: number;
  error?: string;
}

// Agent selection state for UI
export interface AgentSelectionState {
  agentId: number;
  destinationNode: number;
  selectedMode: TransportMode | null;
  selectedOptimization?: CarOptimization;
  route: AgentRoute | null;
  isPathfinding: boolean;
  pathfindingState: PathfindingState | null;
}
