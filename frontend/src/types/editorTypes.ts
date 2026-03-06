export type EditorMode = "settings" | "image" | "graph" | "pt-lines" | "version-diff";
export type GraphTool = "select" | "add-node" | "add-edge" | "delete";

export interface EditorState {
  mode: EditorMode;
  graphTool: GraphTool;
  selectedEdgeIds: Set<number>;
  selectedNodeId: number | null;
  edgeSourceNodeId: number | null;
  isDirty: boolean;
  versionDiffStep: 1 | 2;
  bidirectional: boolean;
}

export interface VersionMetadata {
  versionName: string;
  pollText: string;
  revertPollText: string;
  description: string;
}

export interface ImageTransformValues {
  image_offset_x: number;
  image_offset_y: number;
  image_scale: number;
  image_crop_top: number;
  image_crop_right: number;
  image_crop_bottom: number;
  image_crop_left: number;
}

export interface EdgeChange {
  edge_id: number;
  biking?: boolean;
  walking?: boolean;
  max_lanes?: number;
  speed_limit?: number;
  lanes?: number;
  dedicated_bus_lane?: boolean;
}

export interface PTLineChange {
  id?: number;
  action: "add" | "modify" | "remove";
  line_type: "bus" | "train";
  name?: string;
  interval?: number;
  capacity?: number;
  speed_kmh?: number;
  edge_ids?: number[];
}

export interface PTLineDraftInDiff {
  tempId: string;
  action: "add" | "modify";
  line_type: "bus" | "train";
  existingLineId?: number;
  name: string;
  interval: number;
  capacity: number;
  speed_kmh: number;
}

export interface VirtualNode {
  tempId: string;
  x_position: number;
  y_position: number;
}

export interface VirtualEdge {
  tempId: string;
  start_node: number | string;
  end_node: number | string;
  bidirectional: boolean;
  biking: boolean;
  walking: boolean;
  max_lanes: number;
  speed_limit?: number;
  lanes?: number;
}

export interface VersionDiffPayload {
  source_version_id: number;
  version_name: string;
  description?: string;
  poll_text: string;
  revert_poll_text?: string;
  is_base_version?: boolean;
  edge_changes: EdgeChange[];
  pt_line_changes: PTLineChange[];
  new_nodes?: Array<{ temp_id: string; x_position: number; y_position: number }>;
  new_edges?: Array<{
    temp_start_node: string | number;
    temp_end_node: string | number;
    bidirectional: boolean;
    biking: boolean;
    walking: boolean;
    max_lanes: number;
    speed_limit?: number;
    lanes?: number;
  }>;
  deleted_node_ids?: number[];
  deleted_edge_ids?: number[];
}

export type EditorAction =
  | { type: "SET_MODE"; mode: EditorMode }
  | { type: "SET_GRAPH_TOOL"; tool: GraphTool }
  | { type: "SET_EDGE_SOURCE"; nodeId: number }
  | { type: "CLEAR_EDGE_SOURCE" }
  | { type: "SELECT_NODE"; nodeId: number | null }
  | { type: "SELECT_EDGE"; edgeId: number }
  | { type: "DESELECT_EDGE"; edgeId: number }
  | { type: "TOGGLE_EDGE"; edgeId: number }
  | { type: "CLEAR_SELECTION" }
  | { type: "MARK_DIRTY" }
  | { type: "MARK_CLEAN" }
  | { type: "SET_VERSION_DIFF_STEP"; step: 1 | 2 }
  | { type: "SET_BIDIRECTIONAL"; value: boolean };
