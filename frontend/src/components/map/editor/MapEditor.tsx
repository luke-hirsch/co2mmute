import { de } from "@/lib/de";
import { useReducer, useState, useCallback, useMemo, useRef } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  mapKeys,
  useGameMap,
  useMapGraph,
  useMapVersions,
} from "@/lib/queries/map-graph";
import {
  mapEditorKeys,
  useUpdateNodePosition,
  useCreateNode,
  useDeleteNode,
  useCreateEdge,
  useDeleteEdge,
} from "@/lib/queries/map-editor";
import { diffGraphs } from "@/lib/map/version-diff";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import Loading from "../../Loading";
import EditorToolbar from "./EditorToolbar";
import EditorCanvas from "./EditorCanvas";
import EditorSidebar from "./EditorSidebar";
import { EditorViewportGate } from "./viewport-gate";
import type {
  EditorState,
  EditorAction,
  EditorMode,
  GraphTool,
  EdgeChange,
  PTLineChange,
  VersionMetadata,
  PTLineDraftInDiff,
  VirtualNode,
  VirtualEdge,
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
  bidirectional: true,
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
      return {
        ...state,
        selectedNodeId: action.nodeId,
        selectedEdgeIds: new Set(),
      };
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
      return {
        ...state,
        selectedEdgeIds: new Set(),
        selectedNodeId: null,
        edgeSourceNodeId: null,
      };
    case "MARK_DIRTY":
      return { ...state, isDirty: true };
    case "MARK_CLEAN":
      return { ...state, isDirty: false };
    case "SET_VERSION_DIFF_STEP":
      return { ...state, versionDiffStep: action.step };
    case "SET_BIDIRECTIONAL":
      return { ...state, bidirectional: action.value };
    default:
      return state;
  }
}

const MapEditor = () => {
  const { mapId } = useParams({ from: "/maps/$mapId/editor" });
  const { data: gameMap, isLoading: mapLoading } = useGameMap(mapId);
  const { data: versions } = useMapVersions(mapId) as {
    data: MapVersion[] | undefined;
  };

  // Track which version we're viewing/editing
  const [selectedVersionId, setSelectedVersionId] = useState<
    number | undefined
  >(undefined);
  const { data: mapGraph, isLoading: graphLoading } = useMapGraph(
    mapId,
    selectedVersionId,
  );

  const [state, dispatch] = useReducer(editorReducer, initialState);

  // "Anlegen" or "Verwalten" in the versions mode. Up here rather than in the
  // sidebar because the canvas draws differently under each: Verwalten shows
  // what the version on the canvas changes.
  const [versionTab, setVersionTab] = useState<"create" | "manage">("create");
  /**
   * What the version on the canvas is compared with. `undefined` is "the
   * obvious one" — a change against the version it was drawn from, anything
   * else against base — and `null` is nothing.
   */
  const [compareVersionId, setCompareVersionId] = useState<
    number | null | undefined
  >(undefined);

  const shownVersion = versions?.find((v) => v.id === mapGraph?.version_id);
  const baseVersion = versions?.find((v) => v.base_version);
  const compareId =
    compareVersionId !== undefined
      ? compareVersionId
      : (shownVersion?.source_version ??
        (shownVersion && !shownVersion.base_version ? baseVersion?.id : null) ??
        null);
  const comparing =
    state.mode === "version-diff" &&
    versionTab === "manage" &&
    compareId !== null &&
    compareId !== mapGraph?.version_id;
  const { data: compareGraph } = useMapGraph(
    comparing ? mapId : undefined,
    compareId ?? undefined,
  );
  const diff = useMemo(
    () =>
      comparing && compareGraph && mapGraph
        ? diffGraphs(compareGraph, mapGraph)
        : null,
    [comparing, compareGraph, mapGraph],
  );

  // PT line creation/editing state
  const [ptLineEdgeIds, setPtLineEdgeIds] = useState<number[]>([]);
  const [ptLineCreating, setPtLineCreating] = useState<"bus" | "train" | null>(
    null,
  );

  // Version diff state
  const [edgeChanges, setEdgeChanges] = useState<EdgeChange[]>([]);
  const [ptLineChanges, setPtLineChanges] = useState<PTLineChange[]>([]);
  const [versionMetadata, setVersionMetadata] = useState<VersionMetadata>(
    initialVersionMetadata,
  );

  // Version diff PT line editing sub-mode
  const [versionDiffEditingPtLine, setVersionDiffEditingPtLine] =
    useState<PTLineDraftInDiff | null>(null);

  // Version diff structural changes (Task 3)
  const [newNodes, setNewNodes] = useState<VirtualNode[]>([]);
  const [newEdges, setNewEdges] = useState<VirtualEdge[]>([]);
  const [deletedNodeIds, setDeletedNodeIds] = useState<Set<number>>(new Set());
  const [deletedEdgeIds, setDeletedEdgeIds] = useState<Set<number>>(new Set());
  // Tracks which edge deletions were cascade-triggered by a node deletion
  const [cascadeDeletedEdgeIds, setCascadeDeletedEdgeIds] = useState<
    Map<number, Set<number>>
  >(new Map());
  // Edge source temp ID for virtual nodes in add-edge mode
  const [edgeSourceTempId, setEdgeSourceTempId] = useState<string | null>(null);
  const tempIdCounter = useRef(0);

  // Mutations — declared before callbacks that reference them
  const updateNodeMutation = useUpdateNodePosition(mapId);
  const createNodeMutation = useCreateNode(mapId);
  const deleteNodeMutation = useDeleteNode(mapId);
  const createEdgeMutation = useCreateEdge(mapId);
  const deleteEdgeMutation = useDeleteEdge(mapId);
  const qc = useQueryClient();

  const versionId = selectedVersionId ?? mapGraph?.version_id;
  // A node or an edge drawn on the canvas is pending until the graph that
  // draws it has arrived (`mapMutationOptions`). Until then the canvas takes no
  // second one: the editor used to show nothing for the ~1.8 s the graph took,
  // and Bellevue – Großer Stern got drawn twice.
  const canvasSaving =
    createNodeMutation.isPending || createEdgeMutation.isPending;

  const handleModeChange = useCallback((mode: EditorMode) => {
    dispatch({ type: "SET_MODE", mode });
    setPtLineEdgeIds([]);
    setPtLineCreating(null);
    setEdgeChanges([]);
    setPtLineChanges([]);
    setVersionMetadata(initialVersionMetadata);
    setVersionDiffEditingPtLine(null);
    setNewNodes([]);
    setNewEdges([]);
    setDeletedNodeIds(new Set());
    setDeletedEdgeIds(new Set());
    setCascadeDeletedEdgeIds(new Map());
    setEdgeSourceTempId(null);
  }, []);

  const handleGraphToolChange = useCallback((tool: GraphTool) => {
    dispatch({ type: "SET_GRAPH_TOOL", tool });
  }, []);

  const handleNodeDragEnd = useCallback(
    (nodeId: number, x: number, y: number) => {
      // No dragging in version-diff mode — topology must be preserved
      if (state.mode === "version-diff") return;
      // The key `useMapGraph` reads. It said `["mapGraph", …]`, the pre-F7
      // key nothing reads any more, so the dragged node jumped back to where
      // it had been until the refetch landed.
      qc.setQueryData(
        mapKeys.graph(mapId, selectedVersionId ?? null),
        (old: ExtendedMapGraph | undefined) => {
          if (!old) return old;
          return {
            ...old,
            nodes: old.nodes.map((n) =>
              n.id === nodeId ? { ...n, x_position: x, y_position: y } : n,
            ),
          };
        },
      );
      updateNodeMutation.mutate(
        { nodeId, x_position: x, y_position: y },
        {
          onError: () => {
            qc.invalidateQueries({ queryKey: mapEditorKeys.graph(mapId) });
          },
        },
      );
    },
    [mapId, selectedVersionId, qc, updateNodeMutation, state.mode],
  );

  const handleAddNode = useCallback(
    (x: number, y: number) => {
      if (state.mode === "version-diff") {
        const tempId = `new-node-${tempIdCounter.current++}`;
        setNewNodes((prev) => [...prev, { tempId, x_position: x, y_position: y }]);
        return;
      }
      if (canvasSaving) return;
      createNodeMutation.mutate({
        x_position: x,
        y_position: y,
        map_versions: versionId ? [versionId] : [],
      });
    },
    [createNodeMutation, versionId, state.mode, canvasSaving],
  );

  const handleCreateEdge = useCallback(
    (startNodeId: number | string, endNodeId: number | string) => {
      if (state.mode === "version-diff") {
        const tempId = `new-edge-${tempIdCounter.current++}`;
        setNewEdges((prev) => [
          ...prev,
          {
            tempId,
            start_node: startNodeId,
            end_node: endNodeId,
            bidirectional: state.bidirectional,
            biking: false,
            walking: false,
            max_lanes: 1,
          },
        ]);
        return;
      }
      if (canvasSaving) return;
      createEdgeMutation.mutate({
        start_node: startNodeId as number,
        end_node: endNodeId as number,
        map_versions: versionId ? [versionId] : [],
        bidirectional: state.bidirectional,
      });
    },
    [createEdgeMutation, versionId, state.bidirectional, state.mode, canvasSaving],
  );

  const handleEdgeClick = useCallback(
    (edgeId: number) => {
      // Version-diff step 1: no edge interaction
      if (state.mode === "version-diff" && state.versionDiffStep === 1) return;

      // Version-diff: PT line editing sub-mode — toggle edge in route
      if (state.mode === "version-diff" && versionDiffEditingPtLine !== null) {
        setPtLineEdgeIds((prev) =>
          prev.includes(edgeId)
            ? prev.filter((id) => id !== edgeId)
            : [...prev, edgeId],
        );
        return;
      }

      // Version-diff: delete tool — mark edge as deleted
      if (state.mode === "version-diff" && state.graphTool === "delete") {
        setDeletedEdgeIds((prev) => {
          const next = new Set(prev);
          next.add(edgeId);
          return next;
        });
        // Remove from edgeChanges if it was being modified
        setEdgeChanges((prev) => prev.filter((c) => c.edge_id !== edgeId));
        dispatch({ type: "CLEAR_SELECTION" });
        return;
      }

      if (
        state.mode === "pt-lines" &&
        (ptLineCreating || state.selectedNodeId === null)
      ) {
        // Toggle edge in PT line route
        setPtLineEdgeIds((prev) =>
          prev.includes(edgeId)
            ? prev.filter((id) => id !== edgeId)
            : [...prev, edgeId],
        );
      } else if (state.mode === "version-diff") {
        dispatch({ type: "SELECT_EDGE", edgeId });
      } else {
        // Graph mode: select single edge
        dispatch({ type: "CLEAR_SELECTION" });
        dispatch({ type: "SELECT_EDGE", edgeId });
      }
    },
    [
      state.mode,
      state.versionDiffStep,
      state.graphTool,
      versionDiffEditingPtLine,
      ptLineCreating,
      state.selectedNodeId,
    ],
  );

  const handleNodeClick = useCallback(
    (nodeId: number) => {
      if (state.mode === "version-diff") {
        if (state.graphTool === "delete") {
          // Mark node as deleted and cascade to connected edges
          setDeletedNodeIds((prev) => {
            const next = new Set(prev);
            next.add(nodeId);
            return next;
          });
          const connectedEdgeIds =
            mapGraph?.edges
              .filter((e) => e.start_node === nodeId || e.end_node === nodeId)
              .map((e) => e.id) ?? [];
          if (connectedEdgeIds.length > 0) {
            setDeletedEdgeIds((prev) => {
              const next = new Set(prev);
              connectedEdgeIds.forEach((id) => next.add(id));
              return next;
            });
            setCascadeDeletedEdgeIds((prev) => {
              const next = new Map(prev);
              next.set(nodeId, new Set(connectedEdgeIds));
              return next;
            });
            // Remove any property changes for cascaded edges
            setEdgeChanges((prev) =>
              prev.filter((c) => !connectedEdgeIds.includes(c.edge_id)),
            );
          }
          dispatch({ type: "CLEAR_SELECTION" });
        } else if (state.graphTool === "add-edge") {
          if (state.edgeSourceNodeId === null && edgeSourceTempId === null) {
            dispatch({ type: "SET_EDGE_SOURCE", nodeId });
          } else if (edgeSourceTempId !== null) {
            // Source was a virtual node, target is real
            handleCreateEdge(edgeSourceTempId, nodeId);
            setEdgeSourceTempId(null);
            dispatch({ type: "CLEAR_EDGE_SOURCE" });
          } else if (state.edgeSourceNodeId !== null && state.edgeSourceNodeId !== nodeId) {
            handleCreateEdge(state.edgeSourceNodeId, nodeId);
            dispatch({ type: "CLEAR_EDGE_SOURCE" });
          }
        }
        return;
      }

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
    [
      state.mode,
      state.graphTool,
      state.edgeSourceNodeId,
      edgeSourceTempId,
      handleCreateEdge,
      mapGraph?.edges,
    ],
  );

  // Handler for clicking virtual (pending) nodes in version-diff mode
  const handleVirtualNodeClick = useCallback(
    (tempId: string) => {
      if (state.mode !== "version-diff") return;
      if (state.graphTool === "delete") {
        setNewNodes((prev) => prev.filter((n) => n.tempId !== tempId));
        setNewEdges((prev) =>
          prev.filter((e) => e.start_node !== tempId && e.end_node !== tempId),
        );
      } else if (state.graphTool === "add-edge") {
        if (state.edgeSourceNodeId === null && edgeSourceTempId === null) {
          setEdgeSourceTempId(tempId);
        } else {
          const source =
            edgeSourceTempId !== null
              ? edgeSourceTempId
              : state.edgeSourceNodeId!;
          if (source !== tempId) {
            handleCreateEdge(source, tempId);
          }
          setEdgeSourceTempId(null);
          dispatch({ type: "CLEAR_EDGE_SOURCE" });
        }
      }
    },
    [
      state.mode,
      state.graphTool,
      state.edgeSourceNodeId,
      edgeSourceTempId,
      handleCreateEdge,
    ],
  );

  const handleCanvasClick = useCallback(
    (x?: number, y?: number) => {
      if (
        (state.mode === "graph" || state.mode === "version-diff") &&
        state.graphTool === "add-node" &&
        x !== undefined &&
        y !== undefined
      ) {
        handleAddNode(x, y);
      } else {
        dispatch({ type: "CLEAR_SELECTION" });
        setEdgeSourceTempId(null);
      }
    },
    [state.mode, state.graphTool, handleAddNode],
  );

  const handleDeleteSelected = useCallback(() => {
    if (state.selectedNodeId) {
      if (confirm(de.editor.node.removeConfirm)) {
        deleteNodeMutation.mutate(state.selectedNodeId);
        dispatch({ type: "CLEAR_SELECTION" });
      }
    } else if (state.selectedEdgeIds.size === 1) {
      const edgeId = [...state.selectedEdgeIds][0];
      const edge = mapGraph?.edges.find((e) => e.id === edgeId);
      const reverseEdge = edge
        ? mapGraph?.edges.find(
            (e) =>
              e.start_node === edge.end_node &&
              e.end_node === edge.start_node,
          )
        : null;
      const msg = reverseEdge
        ? de.editor.edge.removeBothConfirm
        : de.editor.deleteEdgeConfirm;
      if (confirm(msg)) {
        deleteEdgeMutation.mutate(edgeId);
        if (reverseEdge) {
          deleteEdgeMutation.mutate(reverseEdge.id);
        }
        dispatch({ type: "CLEAR_SELECTION" });
      }
    }
  }, [
    state.selectedNodeId,
    state.selectedEdgeIds,
    deleteNodeMutation,
    deleteEdgeMutation,
    mapGraph?.edges,
  ]);

  if (mapLoading || graphLoading) {
    return (
      <div className="min-h-dvh bg-background">
        <Loading label={de.editor.loading} />
      </div>
    );
  }
  if (!gameMap) {
    return (
      <main className="flex min-h-dvh items-center bg-background px-4 text-foreground">
        <div className="mx-auto max-w-(--measure-body)">
          <Alert variant="destructive">
            <AlertDescription>{de.editor.notFound}</AlertDescription>
          </Alert>
          <Button asChild variant="outline" className="mt-6">
            <Link to="/maps">{de.map.allMaps}</Link>
          </Button>
        </div>
      </main>
    );
  }

  return (
    <EditorViewportGate>
    <div className="min-h-dvh bg-background text-foreground">
      <div className="mx-auto max-w-[1600px] px-4 py-4">
        {/* Header */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-4">
            <Button asChild variant="link" size="sm" className="-ml-4">
              <Link to="/maps/$mapId" params={{ mapId }}>
                &larr; {de.editor.back}
              </Link>
            </Button>
            <h1 className="text-2xl font-semibold">
              {de.editor.title(gameMap.name)}
            </h1>
            {/* Which version everything below draws into. "Ansehen" puts any
                version on the canvas, and a street drawn in Graph mode then goes
                into that version and what is built on it — not into base. */}
            {mapGraph && versions && versions.length > 1 ? (
              <span className="text-sm text-muted-foreground">
                {de.editor.onVersion(
                  shownVersion?.base_version
                    ? de.editor.version.base
                    : mapGraph.version_name,
                )}
              </span>
            ) : null}
          </div>
          {state.isDirty && (
            <span className="text-sm font-medium text-destructive">
              {de.editor.unsaved}
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
          hasSelection={
            state.selectedNodeId !== null || state.selectedEdgeIds.size > 0
          }
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
          versionDiffEditingPtLine={versionDiffEditingPtLine !== null}
          bidirectional={state.bidirectional}
          onBidirectionalChange={(value: boolean) =>
            dispatch({ type: "SET_BIDIRECTIONAL", value })
          }
          saving={canvasSaving}
        />

        {/* Mutation error banner */}
        {(createNodeMutation.error ||
          updateNodeMutation.error ||
          createEdgeMutation.error) && (
          <Alert variant="destructive" className="mt-2">
            <AlertDescription>
              {(createNodeMutation.error ||
                updateNodeMutation.error ||
                createEdgeMutation.error)?.message}
            </AlertDescription>
          </Alert>
        )}

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mt-4">
          {/* Canvas */}
          <div className="relative z-10 lg:col-span-3">
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
              newNodes={newNodes}
              newEdges={newEdges}
              deletedNodeIds={deletedNodeIds}
              deletedEdgeIds={deletedEdgeIds}
              edgeSourceTempId={edgeSourceTempId}
              onVirtualNodeClick={handleVirtualNodeClick}
              diff={diff}
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
              onVersionChange={(id) => {
                setSelectedVersionId(id);
                // A new version on the canvas gets its own obvious comparison.
                setCompareVersionId(undefined);
              }}
              versionTab={versionTab}
              onVersionTabChange={setVersionTab}
              compare={{
                shownId: mapGraph?.version_id,
                compareId,
                onCompareChange: setCompareVersionId,
                diff,
                graphs: [compareGraph, mapGraph],
              }}
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
              versionDiffEditingPtLine={versionDiffEditingPtLine}
              setVersionDiffEditingPtLine={setVersionDiffEditingPtLine}
              newNodes={newNodes}
              setNewNodes={setNewNodes}
              newEdges={newEdges}
              setNewEdges={setNewEdges}
              deletedNodeIds={deletedNodeIds}
              setDeletedNodeIds={setDeletedNodeIds}
              deletedEdgeIds={deletedEdgeIds}
              setDeletedEdgeIds={setDeletedEdgeIds}
              cascadeDeletedEdgeIds={cascadeDeletedEdgeIds}
              setCascadeDeletedEdgeIds={setCascadeDeletedEdgeIds}
            />
          </div>
        </div>
      </div>
    </div>
    </EditorViewportGate>
  );
};

export default MapEditor;
