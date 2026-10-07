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
  /**
   * The infrastructure, not the access right: `biking` says a bike may use the
   * edge, this says it has a lane of its own. A bike lane takes a car lane from
   * the street, exactly as a bus lane does, which is why the replay reads it.
   */
  bike_lane?: boolean;
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

/**
 * A map's own row, as `GameMapSerializer` actually sends it.
 *
 * Two fields were wrong here until S18 and both rendered as nothing rather than
 * as an error: `author` is a **primary key**, not a nested user — the serializer
 * declares no nested one, so `gameMap.author.username` on the detail page read
 * `undefined` and printed an empty "Angelegt von" — and `description` is not a
 * column on `GameMap` at all, so the block that rendered it never ran. The
 * Django list template printed the same non-existent field.
 */
export interface GameMap {
  id: number;
  name: string;
  x_dim: number;
  y_dim: number;
  scale: number;
  max_player: number;
  walk_speed_kmh: number;
  bike_speed_kmh: number;
  default_car_speed_kmh: number;
  /** The calibration, per map because it is a property of the graph. */
  district_commuters: number;
  /** Whether that count was measured on this map, or is still the default. */
  calibrated: boolean;
  /** Whether a game on this map can ever reach a ballot. */
  offers_map_changes: boolean;
  created: string;
  updated: string;
  author: number | null;
  updated_by?: number | null;
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
  /**
   * The version this one was drawn from, for a change; empty for base and for a
   * generated combination, which records no members.
   */
  source_version: number | null;
  compatible_versions: number[];
  change_img_url: string | null;
}

/**
 * What deleting a version would take, and whether it may (F14) — the answer
 * to `GET api/maps/<id>/versions/<id>/deletion/`, asked before the dialog
 * offers the button. `goes` is what only this version holds.
 */
export interface VersionDeletion {
  version: { id: number; name: string };
  refusal: { reason: "base" | "running" | "played"; detail: string } | null;
  goes: {
    nodes: number;
    edges: number;
    streets: number;
    rails: number;
    bus_lines: string[];
    train_lines: string[];
    line_links: number;
  };
  /** The versions it is paired with on the ballot. Those pairs go too. */
  ballot: string[];
  /** The versions built on it, which keep its change. */
  keeps: string[];
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
