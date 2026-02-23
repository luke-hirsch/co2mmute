import { useReducer, useState, useCallback } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useGameMap, useMapGraph, useMapVersions } from "../../../hooks/mapHooks";
import {
  useUpdateNodePosition,
  useCreateNode,
  useDeleteNode,
  useCreateEdge,
  useDeleteEdge,
} from "../../../hooks/mapEditorHooks";
import Loading from "../../Loading";
import EditorToolbar from "./EditorToolbar";
import EditorCanvas from "./EditorCanvas";
import EditorSidebar from "./EditorSidebar";
import type {
  EditorState,
  EditorAction,
  EditorMode,
  GraphTool,
  EdgeChange,
  PTLineChange,
  VersionMetadata,
} from "../../../types/editorTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type { MapVersion } from "../../../types/mapTypes";

const initialState: EditorState = {
  mode: "image",
  graphTool: "select",
  selectedEdgeIds: new Set(),
  selectedNodeId: null,
  edgeSourceNodeId: null,
  isDirty: false,
  versionDiffStep: 1,
};

const initialVersionMetadata: VersionMetadata = {
  versionName: "",
  pollText: "",
  revertPollText: "",
  description: "",
};

function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "SET_MODE":
      return {
        ...state,
        mode: action.mode,
        graphTool: "select",
        selectedEdgeIds: new Set(),
        selectedNodeId: null,
        edgeSourceNodeId: null,
        versionDiffStep: 1,
      };
    case "SET_GRAPH_TOOL":
      return {
        ...state,
        graphTool: action.tool,
        selectedEdgeIds: new Set(),
        selectedNodeId: null,
        edgeSourceNodeId: null,
      };
    case "SET_EDGE_SOURCE":
      return { ...state, edgeSourceNodeId: action.nodeId };
    case "CLEAR_EDGE_SOURCE":
      return { ...state, edgeSourceNodeId: null };
    case "SELECT_NODE":
      return { ...state, selectedNodeId: action.nodeId, selectedEdgeIds: new Set() };
    case "SELECT_EDGE": {
      const newSet = new Set(state.selectedEdgeIds);
      newSet.add(action.edgeId);
      return { ...state, selectedEdgeIds: newSet, selectedNodeId: null };
    }
    case "DESELECT_EDGE": {
      const newSet = new Set(state.selectedEdgeIds);
      newSet.delete(action.edgeId);
      return { ...state, selectedEdgeIds: newSet };
    }
    case "TOGGLE_EDGE": {
      const newSet = new Set(state.selectedEdgeIds);
      if (newSet.has(action.edgeId)) {
        newSet.delete(action.edgeId);
      } else {
        newSet.add(action.edgeId);
      }
      return { ...state, selectedEdgeIds: newSet };
    }
    case "CLEAR_SELECTION":
      return { ...state, selectedEdgeIds: new Set(), selectedNodeId: null, edgeSourceNodeId: null };
    case "MARK_DIRTY":
      return { ...state, isDirty: true };
    case "MARK_CLEAN":
      return { ...state, isDirty: false };
    case "SET_VERSION_DIFF_STEP":
      return { ...state, versionDiffStep: action.step };
    default:
      return state;
  }
}

const MapEditor = () => {
  const { mapId } = useParams({ from: "/maps/$mapId/editor" });
  const { data: gameMap, isLoading: mapLoading } = useGameMap(mapId);
  const { data: versions } = useMapVersions(mapId) as { data: MapVersion[] | undefined };

  // Track which version we're viewing/editing
  const [selectedVersionId, setSelectedVersionId] = useState<number | undefined>(
    undefined
  );
  const { data: mapGraph, isLoading: graphLoading } = useMapGraph(
    mapId,
    selectedVersionId
  );

  const [state, dispatch] = useReducer(editorReducer, initialState);

  // PT line creation/editing state
  const [ptLineEdgeIds, setPtLineEdgeIds] = useState<number[]>([]);
  const [ptLineCreating, setPtLineCreating] = useState<"bus" | "train" | null>(null);

  // Version diff state
  const [edgeChanges, setEdgeChanges] = useState<EdgeChange[]>([]);
  const [ptLineChanges, setPtLineChanges] = useState<PTLineChange[]>([]);
  const [versionMetadata, setVersionMetadata] = useState<VersionMetadata>(initialVersionMetadata);

  const handleModeChange = useCallback((mode: EditorMode) => {
    dispatch({ type: "SET_MODE", mode });
    setPtLineEdgeIds([]);
    setPtLineCreating(null);
    setEdgeChanges([]);
    setPtLineChanges([]);
    setVersionMetadata(initialVersionMetadata);
  }, []);

  const handleGraphToolChange = useCallback((tool: GraphTool) => {
    dispatch({ type: "SET_GRAPH_TOOL", tool });
  }, []);

  const handleEdgeClick = useCallback(
    (edgeId: number) => {
      // Version-diff step 1: no edge interaction
      if (state.mode === "version-diff" && state.versionDiffStep === 1) return;

      if (state.mode === "pt-lines" && (ptLineCreating || state.selectedNodeId === null)) {
        // Toggle edge in PT line route
        setPtLineEdgeIds((prev) =>
          prev.includes(edgeId)
            ? prev.filter((id) => id !== edgeId)
            : [...prev, edgeId]
        );
      } else if (state.mode === "version-diff") {
        dispatch({ type: "SELECT_EDGE", edgeId });
      } else {
        // Graph mode: select single edge
        dispatch({ type: "CLEAR_SELECTION" });
        dispatch({ type: "SELECT_EDGE", edgeId });
      }
    },
    [state.mode, state.versionDiffStep, ptLineCreating, state.selectedNodeId]
  );

  const handleNodeClick = useCallback(
    (nodeId: number) => {
      // Nodes not interactive in version-diff mode
      if (state.mode === "version-diff") return;

      if (state.mode === "graph" && state.graphTool === "add-edge") {
        if (state.edgeSourceNodeId === null) {
          dispatch({ type: "SET_EDGE_SOURCE", nodeId });
        } else if (state.edgeSourceNodeId !== nodeId) {
          // Create edge between source and this node
          handleCreateEdge(state.edgeSourceNodeId, nodeId);
          dispatch({ type: "CLEAR_EDGE_SOURCE" });
        }
      } else {
        dispatch({ type: "SELECT_NODE", nodeId });
      }
    },
    [state.mode, state.graphTool, state.edgeSourceNodeId]
  );

  const handleCanvasClick = useCallback(
    (x?: number, y?: number) => {
      if (
        state.mode === "graph" &&
        state.graphTool === "add-node" &&
        x !== undefined &&
        y !== undefined
      ) {
        handleAddNode(x, y);
      } else {
        dispatch({ type: "CLEAR_SELECTION" });
      }
    },
    [state.mode, state.graphTool]
  );

  // Mutations
  const updateNodeMutation = useUpdateNodePosition(mapId);
  const createNodeMutation = useCreateNode(mapId);
  const deleteNodeMutation = useDeleteNode(mapId);
  const createEdgeMutation = useCreateEdge(mapId);
  const deleteEdgeMutation = useDeleteEdge(mapId);
  const qc = useQueryClient();

  const versionId = selectedVersionId ?? mapGraph?.version_id;

  const handleNodeDragEnd = useCallback(
    (nodeId: number, x: number, y: number) => {
      qc.setQueryData(
        ["mapGraph", mapId, selectedVersionId],
        (old: ExtendedMapGraph | undefined) => {
          if (!old) return old;
          return {
            ...old,
            nodes: old.nodes.map((n) =>
              n.id === nodeId ? { ...n, x_position: x, y_position: y } : n
            ),
          };
        }
      );
      updateNodeMutation.mutate(
        { nodeId, x_position: x, y_position: y },
        {
          onError: () => {
            qc.invalidateQueries({ queryKey: ["mapGraph", mapId] });
          },
        }
      );
    },
    [mapId, selectedVersionId, qc, updateNodeMutation]
  );

  const handleAddNode = useCallback(
    (x: number, y: number) => {
      createNodeMutation.mutate({
        x_position: x,
        y_position: y,
        map_versions: versionId ? [versionId] : [],
      });
    },
    [createNodeMutation, versionId]
  );

  const handleCreateEdge = useCallback(
    (startNodeId: number, endNodeId: number) => {
      createEdgeMutation.mutate({
        start_node: startNodeId,
        end_node: endNodeId,
        map_versions: versionId ? [versionId] : [],
      });
    },
    [createEdgeMutation, versionId]
  );

  const handleDeleteSelected = useCallback(() => {
    if (state.selectedNodeId) {
      if (confirm("Delete this node and all its connected edges?")) {
        deleteNodeMutation.mutate(state.selectedNodeId);
        dispatch({ type: "CLEAR_SELECTION" });
      }
    } else if (state.selectedEdgeIds.size === 1) {
      const edgeId = [...state.selectedEdgeIds][0];
      if (confirm("Delete this edge?")) {
        deleteEdgeMutation.mutate(edgeId);
        dispatch({ type: "CLEAR_SELECTION" });
      }
    }
  }, [state.selectedNodeId, state.selectedEdgeIds, deleteNodeMutation, deleteEdgeMutation]);

  if (mapLoading || graphLoading) return <Loading />;
  if (!gameMap) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-red-600 dark:text-red-400">Map not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-b from-body to-surface dark:from-darkbody dark:to-darksurface">
      <div className="max-w-[1600px] mx-auto px-4 py-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <Link
              to="/maps/$mapId"
              params={{ mapId }}
              className="text-sm text-muted dark:text-darkmutedtext hover:text-main dark:hover:text-darktext"
            >
              &larr; Back to map
            </Link>
            <h1 className="text-2xl font-bold text-main dark:text-darktext">
              Edit: {gameMap.name}
            </h1>
          </div>
          {state.isDirty && (
            <span className="text-sm text-amber-600 dark:text-amber-400">
              Unsaved changes
            </span>
          )}
        </div>

        {/* Toolbar */}
        <EditorToolbar
          mode={state.mode}
          onModeChange={handleModeChange}
          mapId={mapId}
          gameMap={gameMap}
          graphTool={state.graphTool}
          onGraphToolChange={handleGraphToolChange}
          hasSelection={state.selectedNodeId !== null || state.selectedEdgeIds.size > 0}
          onDeleteSelected={handleDeleteSelected}
          ptLineCreating={ptLineCreating}
          onStartPtLine={(type) => {
            setPtLineCreating(type);
            setPtLineEdgeIds([]);
          }}
          onCancelPtLine={() => {
            setPtLineCreating(null);
            setPtLineEdgeIds([]);
          }}
          versionDiffStep={state.versionDiffStep}
        />

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mt-4">
          {/* Canvas */}
          <div className="lg:col-span-3">
            <EditorCanvas
              gameMap={gameMap}
              mapGraph={mapGraph as ExtendedMapGraph | undefined}
              state={state}
              ptLineEdgeIds={ptLineEdgeIds}
              edgeChanges={edgeChanges}
              onEdgeClick={handleEdgeClick}
              onNodeClick={handleNodeClick}
              onCanvasClick={handleCanvasClick}
              onNodeDragEnd={handleNodeDragEnd}
            />
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <EditorSidebar
              mapId={mapId}
              gameMap={gameMap}
              mapGraph={mapGraph as ExtendedMapGraph | undefined}
              state={state}
              versions={versions}
              selectedVersionId={selectedVersionId}
              onVersionChange={setSelectedVersionId}
              ptLineCreating={ptLineCreating}
              ptLineEdgeIds={ptLineEdgeIds}
              setPtLineEdgeIds={setPtLineEdgeIds}
              setPtLineCreating={setPtLineCreating}
              edgeChanges={edgeChanges}
              setEdgeChanges={setEdgeChanges}
              ptLineChanges={ptLineChanges}
              setPtLineChanges={setPtLineChanges}
              dispatch={dispatch}
              versionMetadata={versionMetadata}
              setVersionMetadata={setVersionMetadata}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapEditor;
