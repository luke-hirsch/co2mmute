import { useReducer, useState, useCallback } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useGameMap, useMapGraph, useMapVersions } from "../../../hooks/mapHooks";
import Loading from "../../Loading";
import EditorToolbar from "./EditorToolbar";
import EditorCanvas from "./EditorCanvas";
import EditorSidebar from "./EditorSidebar";
import type {
  EditorState,
  EditorAction,
  EditorMode,
  EdgeChange,
  PTLineChange,
} from "../../../types/editorTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type { MapVersion } from "../../../types/mapTypes";

const initialState: EditorState = {
  mode: "image",
  selectedEdgeIds: new Set(),
  selectedNodeId: null,
  isDirty: false,
};

function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "SET_MODE":
      return {
        ...state,
        mode: action.mode,
        selectedEdgeIds: new Set(),
        selectedNodeId: null,
      };
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
      return { ...state, selectedEdgeIds: new Set(), selectedNodeId: null };
    case "MARK_DIRTY":
      return { ...state, isDirty: true };
    case "MARK_CLEAN":
      return { ...state, isDirty: false };
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

  // PT line creation state
  const [ptLineEdgeIds, setPtLineEdgeIds] = useState<number[]>([]);
  const [ptLineCreating, setPtLineCreating] = useState<"bus" | "train" | null>(null);

  // Version diff state
  const [edgeChanges, setEdgeChanges] = useState<EdgeChange[]>([]);
  const [ptLineChanges, setPtLineChanges] = useState<PTLineChange[]>([]);

  const handleModeChange = useCallback((mode: EditorMode) => {
    dispatch({ type: "SET_MODE", mode });
    setPtLineEdgeIds([]);
    setPtLineCreating(null);
    setEdgeChanges([]);
    setPtLineChanges([]);
  }, []);

  const handleEdgeClick = useCallback(
    (edgeId: number) => {
      if (state.mode === "pt-lines" && ptLineCreating) {
        // Toggle edge in PT line route
        setPtLineEdgeIds((prev) =>
          prev.includes(edgeId)
            ? prev.filter((id) => id !== edgeId)
            : [...prev, edgeId]
        );
      } else if (state.mode === "version-diff") {
        // Select edge for modification
        dispatch({ type: "SELECT_EDGE", edgeId });
      } else {
        // Graph mode: select single edge
        dispatch({ type: "CLEAR_SELECTION" });
        dispatch({ type: "SELECT_EDGE", edgeId });
      }
    },
    [state.mode, ptLineCreating]
  );

  const handleNodeClick = useCallback(
    (nodeId: number) => {
      dispatch({ type: "SELECT_NODE", nodeId });
    },
    []
  );

  const handleCanvasClick = useCallback(() => {
    dispatch({ type: "CLEAR_SELECTION" });
  }, []);

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
          ptLineCreating={ptLineCreating}
          onStartPtLine={(type) => {
            setPtLineCreating(type);
            setPtLineEdgeIds([]);
          }}
          onCancelPtLine={() => {
            setPtLineCreating(null);
            setPtLineEdgeIds([]);
          }}
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
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapEditor;
