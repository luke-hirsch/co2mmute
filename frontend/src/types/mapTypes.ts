/**
 * Map-related types for the application
 */

export interface User {
  id: number;
  username: string;
}

export interface NodeType {
  id: number;
  name: string;
  short: string;
}

export interface Node {
  id: number;
  name: string;
  x_position: number;
  y_position: number;
  node_type: NodeType[];
}

export interface Edge {
  id: number;
  name: string;
  start_node: number;
  end_node: number;
  biking?: boolean;
  walking?: boolean;
  max_lanes?: number;
  distance_m?: number; // Euclidean distance in meters (computed from nodes * scale)
  street_edge?: {
    id: number;
    speed_limit: number;
    lanes: number;
    dedicated_bus_lane: boolean;
  } | null;
  train_edge?: {
    id: number;
  } | null;
}

export interface GameMap {
  id: number;
  name: string;
  description?: string;
  x_dim: number;
  y_dim: number;
  scale: number;
  max_player: number;
  walk_speed_kmh: number;
  bike_speed_kmh: number;
  default_car_speed_kmh: number;
  created: string;
  updated: string;
  author: User;
  updated_by?: User;
  background_image_url?: string | null;
  image_offset_x?: number;
  image_offset_y?: number;
  image_scale?: number;
  image_crop_top?: number;
  image_crop_right?: number;
  image_crop_bottom?: number;
  image_crop_left?: number;
}

export interface MapVersion {
  id: number;
  game_map: number;
  name: string;
  description?: string;
  base_version: boolean;
  poll_text: string;
  revert_poll_text: string;
}

export interface MapGraph {
  map_id: number;
  version_id: number;
  version_name: string;
  version_description?: string;
  nodes: Node[];
  edges: Edge[];
  node_count: number;
  edge_count: number;
}

/**
 * Cytoscape element data for visualization
 */
export interface CytoscapeNode {
  data: {
    id: string;
    label: string;
    x: number;
    y: number;
    types: string[];
  };
}

export interface CytoscapeEdge {
  data: {
    id: string;
    source: string;
    target: string;
    label: string;
  };
}

export type CytoscapeElement = CytoscapeNode | CytoscapeEdge;
