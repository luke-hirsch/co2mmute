import { useState } from "react";
import type { Dispatch } from "react";
import type { MapVersion, Edge } from "../../../types/mapTypes";
import type { ExtendedMapGraph, PTLine } from "../../../types/routeTypes";
import type {
  EdgeChange,
  PTLineChange,
  EditorAction,
  VersionMetadata,
  PTLineDraftInDiff,
  VirtualNode,
  VirtualEdge,
} from "../../../types/editorTypes";
import { useCreateVersionFromDiff } from "../../../hooks/mapEditorHooks";
import EdgePropertyPanel from "./EdgePropertyPanel";

interface VersionDiffPanelProps {
  mapId: string;
  mapGraph: ExtendedMapGraph | undefined;
  versions: MapVersion[] | undefined;
  selectedVersionId: number | undefined;
  onVersionChange: (versionId: number | undefined) => void;
  edgeChanges: EdgeChange[];
  setEdgeChanges: (changes: EdgeChange[]) => void;
  ptLineChanges: PTLineChange[];
  setPtLineChanges: (changes: PTLineChange[]) => void;
  selectedEdge: Edge | undefined;
  dispatch: Dispatch<EditorAction>;
  versionDiffStep: 1 | 2;
  versionMetadata: VersionMetadata;
  setVersionMetadata: (meta: VersionMetadata) => void;
  versionDiffEditingPtLine: PTLineDraftInDiff | null;
  setVersionDiffEditingPtLine: (draft: PTLineDraftInDiff | null) => void;
  ptLineEdgeIds: number[];
  setPtLineEdgeIds: (ids: number[]) => void;
  newNodes: VirtualNode[];
  setNewNodes: (nodes: VirtualNode[]) => void;
  newEdges: VirtualEdge[];
  setNewEdges: (edges: VirtualEdge[]) => void;
  deletedNodeIds: Set<number>;
  setDeletedNodeIds: (ids: Set<number>) => void;
  deletedEdgeIds: Set<number>;
  setDeletedEdgeIds: (ids: Set<number>) => void;
  cascadeDeletedEdgeIds: Map<number, Set<number>>;
  setCascadeDeletedEdgeIds: (m: Map<number, Set<number>>) => void;
}

const VersionDiffPanel = ({
  mapId,
  mapGraph,
  versions,
  selectedVersionId,
  onVersionChange,
  edgeChanges,
  setEdgeChanges,
  ptLineChanges,
  setPtLineChanges,
  selectedEdge,
  dispatch,
  versionDiffStep,
  versionMetadata,
  setVersionMetadata,
  versionDiffEditingPtLine,
  setVersionDiffEditingPtLine,
  ptLineEdgeIds,
  setPtLineEdgeIds,
  newNodes,
  setNewNodes,
  newEdges,
  setNewEdges,
  deletedNodeIds,
  setDeletedNodeIds,
  deletedEdgeIds,
  setDeletedEdgeIds,
  cascadeDeletedEdgeIds,
  setCascadeDeletedEdgeIds,
}: VersionDiffPanelProps) => {
  const createMutation = useCreateVersionFromDiff(mapId);

  // Local form state for PT line draft
  const [ptDraftName, setPtDraftName] = useState("");
  const [ptDraftInterval, setPtDraftInterval] = useState(5);
  const [ptDraftCapacity, setPtDraftCapacity] = useState(60);
  const [ptDraftSpeed, setPtDraftSpeed] = useState(30);
  const [ptDraftError, setPtDraftError] = useState<string | null>(null);

  const sourceVersionId = selectedVersionId ?? mapGraph?.version_id;

  const allPtLines: PTLine[] = [
    ...(mapGraph?.bus_lines ?? []),
    ...(mapGraph?.train_lines ?? []),
  ];

  // ─── Helpers ────────────────────────────────────────────────────────
  const resolveEdgeIds = (type: "bus" | "train", edgeIds: number[]) => {
    const resolved: number[] = [];
    for (const edgeId of edgeIds) {
      const edge = mapGraph?.edges.find((e) => e.id === edgeId);
      if (!edge) continue;
      if (type === "bus" && edge.street_edge) {
        resolved.push(edge.street_edge.id);
      } else if (type === "train" && edge.train_edge) {
        resolved.push(edge.train_edge.id);
      }
    }
    return resolved;
  };

  const isEdgeCompatible = (edgeId: number, type: "bus" | "train") => {
    const edge = mapGraph?.edges.find((e) => e.id === edgeId);
    if (!edge) return false;
    return type === "bus" ? !!edge.street_edge : !!edge.train_edge;
  };

  const getEdgeLabel = (edgeId: number) => {
    const edge = mapGraph?.edges.find((e) => e.id === edgeId);
    if (!edge) return `Edge ${edgeId}`;
    const sn = mapGraph?.nodes.find((n) => n.id === edge.start_node);
    const en = mapGraph?.nodes.find((n) => n.id === edge.end_node);
    return `${sn?.name || edge.start_node} → ${en?.name || edge.end_node}`;
  };

  const getNodeLabel = (nodeId: number) => {
    const node = mapGraph?.nodes.find((n) => n.id === nodeId);
    return node?.name || `Node ${nodeId}`;
  };

  const getVirtualEdgeLabel = (ve: VirtualEdge) => {
    const startLabel =
      typeof ve.start_node === "string"
        ? `New (${newNodes.find((n) => n.tempId === ve.start_node) ? "pending" : ve.start_node})`
        : getNodeLabel(ve.start_node);
    const endLabel =
      typeof ve.end_node === "string"
        ? `New (${newNodes.find((n) => n.tempId === ve.end_node) ? "pending" : ve.end_node})`
        : getNodeLabel(ve.end_node);
    return `${startLabel} → ${endLabel}`;
  };

  // ─── Edge changes ───────────────────────────────────────────────────
  const handleEdgeChange = (changes: Partial<EdgeChange>) => {
    if (!selectedEdge) return;
    const existing = edgeChanges.find((c) => c.edge_id === selectedEdge.id);
    if (existing) {
      setEdgeChanges(
        edgeChanges.map((c) =>
          c.edge_id === selectedEdge.id ? { ...c, ...changes } : c,
        ),
      );
    } else {
      setEdgeChanges([...edgeChanges, { edge_id: selectedEdge.id, ...changes }]);
    }
    dispatch({ type: "MARK_DIRTY" });
  };

  const removeEdgeChange = (edgeId: number) => {
    setEdgeChanges(edgeChanges.filter((c) => c.edge_id !== edgeId));
    dispatch({ type: "DESELECT_EDGE", edgeId });
  };

  // ─── PT Line Draft ──────────────────────────────────────────────────
  const startAddPtLine = (type: "bus" | "train") => {
    const tempId = `new-${Date.now()}`;
    setVersionDiffEditingPtLine({
      tempId,
      action: "add",
      line_type: type,
      name: "",
      interval: 5,
      capacity: type === "bus" ? 60 : 200,
      speed_kmh: type === "bus" ? 30 : 60,
    });
    setPtDraftName("");
    setPtDraftInterval(5);
    setPtDraftCapacity(type === "bus" ? 60 : 200);
    setPtDraftSpeed(type === "bus" ? 30 : 60);
    setPtLineEdgeIds([]);
    setPtDraftError(null);
  };

  const startModifyPtLine = (line: PTLine) => {
    const existingChange = ptLineChanges.find(
      (c) => c.id === line.id && c.line_type === line.type,
    );
    setVersionDiffEditingPtLine({
      tempId: `modify-${line.id}`,
      action: "modify",
      line_type: line.type as "bus" | "train",
      existingLineId: line.id,
      name: existingChange?.name ?? line.name,
      interval: existingChange?.interval ?? line.interval,
      capacity: existingChange?.capacity ?? line.capacity,
      speed_kmh: existingChange?.speed_kmh ?? line.speed_kmh,
    });
    setPtDraftName(existingChange?.name ?? line.name);
    setPtDraftInterval(existingChange?.interval ?? line.interval);
    setPtDraftCapacity(existingChange?.capacity ?? line.capacity);
    setPtDraftSpeed(existingChange?.speed_kmh ?? line.speed_kmh);
    // Restore previously saved edges or use original line edges
    const savedEdgeIds = existingChange?.edge_ids;
    if (savedEdgeIds) {
      // Convert StreetEdge/TrainEdge IDs back to edge IDs for display
      const edgeIdsForDisplay = savedEdgeIds.flatMap((subId) => {
        const edge = mapGraph?.edges.find(
          (e) =>
            (line.type === "bus" ? e.street_edge?.id : e.train_edge?.id) ===
            subId,
        );
        return edge ? [edge.id] : [];
      });
      setPtLineEdgeIds(edgeIdsForDisplay.length > 0 ? edgeIdsForDisplay : line.edges);
    } else {
      setPtLineEdgeIds(line.edges);
    }
    setPtDraftError(null);
  };

  const cancelPtDraft = () => {
    setVersionDiffEditingPtLine(null);
    setPtLineEdgeIds([]);
    setPtDraftError(null);
  };

  const savePtDraft = () => {
    if (!versionDiffEditingPtLine) return;
    setPtDraftError(null);

    if (ptLineEdgeIds.length === 0) {
      setPtDraftError("Route must have at least one edge.");
      return;
    }

    const type = versionDiffEditingPtLine.line_type;
    const incompatible = ptLineEdgeIds.filter((id) => !isEdgeCompatible(id, type));
    if (incompatible.length > 0) {
      const typeLabel = type === "bus" ? "street edge" : "train edge";
      setPtDraftError(
        `${incompatible.length} edge(s) missing a ${typeLabel}. Remove or fix them.`,
      );
      return;
    }

    const resolvedEdgeIds = resolveEdgeIds(type, ptLineEdgeIds);
    if (resolvedEdgeIds.length === 0) {
      setPtDraftError("No valid edges in the route.");
      return;
    }

    const change: PTLineChange = {
      id: versionDiffEditingPtLine.existingLineId,
      action: versionDiffEditingPtLine.action,
      line_type: type,
      name: ptDraftName || undefined,
      interval: ptDraftInterval,
      capacity: ptDraftCapacity,
      speed_kmh: ptDraftSpeed,
      edge_ids: resolvedEdgeIds,
    };

    if (versionDiffEditingPtLine.action === "modify") {
      // Replace existing modify entry for this line, or add
      const exists = ptLineChanges.some(
        (c) =>
          c.id === versionDiffEditingPtLine.existingLineId &&
          c.action !== "remove",
      );
      if (exists) {
        setPtLineChanges(
          ptLineChanges.map((c) =>
            c.id === versionDiffEditingPtLine.existingLineId && c.action !== "remove"
              ? change
              : c,
          ),
        );
      } else {
        setPtLineChanges([...ptLineChanges, change]);
      }
    } else {
      setPtLineChanges([...ptLineChanges, change]);
    }

    cancelPtDraft();
    dispatch({ type: "MARK_DIRTY" });
  };

  const removePtLineChange = (idx: number) => {
    setPtLineChanges(ptLineChanges.filter((_, i) => i !== idx));
  };

  const addRemovePtLine = (line: PTLine) => {
    // Check if already has a change for this line
    const existingIdx = ptLineChanges.findIndex(
      (c) => c.id === line.id && c.line_type === line.type,
    );
    if (existingIdx >= 0) {
      // Already has a change — replace with remove
      setPtLineChanges(
        ptLineChanges.map((c, i) =>
          i === existingIdx
            ? { id: line.id, action: "remove", line_type: line.type as "bus" | "train" }
            : c,
        ),
      );
    } else {
      setPtLineChanges([
        ...ptLineChanges,
        { id: line.id, action: "remove", line_type: line.type as "bus" | "train" },
      ]);
    }
    dispatch({ type: "MARK_DIRTY" });
  };

  const getPtLineChangeAction = (
    lineId: number,
    lineType: string,
  ): "add" | "modify" | "remove" | null => {
    const change = ptLineChanges.find(
      (c) => c.id === lineId && c.line_type === lineType,
    );
    return change?.action ?? null;
  };

  // ─── Structural change helpers ──────────────────────────────────────
  const removeNewNode = (tempId: string) => {
    setNewNodes(newNodes.filter((n) => n.tempId !== tempId));
    setNewEdges(
      newEdges.filter((e) => e.start_node !== tempId && e.end_node !== tempId),
    );
  };

  const removeNewEdge = (tempId: string) => {
    setNewEdges(newEdges.filter((e) => e.tempId !== tempId));
  };

  const undoDeletedNode = (nodeId: number) => {
    const next = new Set(deletedNodeIds);
    next.delete(nodeId);
    setDeletedNodeIds(next);
    // Also undo cascade-deleted edges
    const cascaded = cascadeDeletedEdgeIds.get(nodeId);
    if (cascaded) {
      const nextEdgeIds = new Set(deletedEdgeIds);
      cascaded.forEach((id) => nextEdgeIds.delete(id));
      setDeletedEdgeIds(nextEdgeIds);
      const nextCascade = new Map(cascadeDeletedEdgeIds);
      nextCascade.delete(nodeId);
      setCascadeDeletedEdgeIds(nextCascade);
    }
  };

  const undoDeletedEdge = (edgeId: number) => {
    const next = new Set(deletedEdgeIds);
    next.delete(edgeId);
    setDeletedEdgeIds(next);
  };

  // ─── Submit ─────────────────────────────────────────────────────────
  const handleCreateVersion = () => {
    if (
      !sourceVersionId ||
      !versionMetadata.versionName.trim() ||
      !versionMetadata.pollText.trim()
    )
      return;

    createMutation.mutate(
      {
        source_version_id: sourceVersionId,
        version_name: versionMetadata.versionName.trim(),
        description: versionMetadata.description || undefined,
        poll_text: versionMetadata.pollText,
        revert_poll_text: versionMetadata.revertPollText || undefined,
        edge_changes: edgeChanges,
        pt_line_changes: ptLineChanges,
        new_nodes: newNodes.map((n) => ({
          temp_id: n.tempId,
          x_position: n.x_position,
          y_position: n.y_position,
        })),
        new_edges: newEdges.map((e) => ({
          temp_start_node: e.start_node,
          temp_end_node: e.end_node,
          bidirectional: e.bidirectional,
          biking: e.biking,
          walking: e.walking,
          max_lanes: e.max_lanes,
          speed_limit: e.speed_limit,
          lanes: e.lanes,
        })),
        deleted_node_ids: [...deletedNodeIds],
        deleted_edge_ids: [...deletedEdgeIds],
      },
      {
        onSuccess: () => {
          setVersionMetadata({
            versionName: "",
            pollText: "",
            revertPollText: "",
            description: "",
          });
          setEdgeChanges([]);
          setPtLineChanges([]);
          setNewNodes([]);
          setNewEdges([]);
          setDeletedNodeIds(new Set());
          setDeletedEdgeIds(new Set());
          setCascadeDeletedEdgeIds(new Map());
          dispatch({ type: "MARK_CLEAN" });
          dispatch({ type: "CLEAR_SELECTION" });
          dispatch({ type: "SET_VERSION_DIFF_STEP", step: 1 });
        },
      },
    );
  };

  const canProceed =
    versionMetadata.versionName.trim().length > 0 &&
    versionMetadata.pollText.trim().length > 0;

  const totalChanges =
    edgeChanges.length +
    ptLineChanges.length +
    newNodes.length +
    newEdges.length +
    deletedNodeIds.size +
    deletedEdgeIds.size;

  const updateField = (field: keyof VersionMetadata, value: string) => {
    setVersionMetadata({ ...versionMetadata, [field]: value });
  };

  const inputClass =
    "w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext";

  // ─── Step 1: Version Metadata Form ─────────────────────────────────
  if (versionDiffStep === 1) {
    return (
      <div className="space-y-4">
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
          <h3 className="text-lg font-semibold text-main dark:text-darktext">
            Create Alternate Version
          </h3>
          <p className="text-xs text-muted dark:text-darkmutedtext">
            Define the version that players can vote for. Fill in the details
            below, then proceed to modify edges.
          </p>

          {/* Source version selector */}
          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">
              Source Version
            </label>
            <select
              value={selectedVersionId ?? ""}
              onChange={(e) => {
                const val = e.target.value;
                onVersionChange(val ? Number(val) : undefined);
                setEdgeChanges([]);
                setPtLineChanges([]);
                dispatch({ type: "CLEAR_SELECTION" });
                dispatch({ type: "MARK_CLEAN" });
              }}
              className={inputClass}
            >
              <option value="">
                {mapGraph ? `Current (${mapGraph.version_name})` : "Loading..."}
              </option>
              {versions?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} {v.base_version ? "(base)" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Version Name */}
          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">
              Version Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={versionMetadata.versionName}
              onChange={(e) => updateField("versionName", e.target.value)}
              placeholder="e.g. Add bus lanes on Main St"
              className={inputClass}
            />
          </div>

          {/* Poll Text */}
          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">
              Poll Text <span className="text-red-500">*</span>
            </label>
            <p className="text-xs text-muted dark:text-darkmutedtext mt-0.5 mb-1">
              What should players vote on?
            </p>
            <textarea
              value={versionMetadata.pollText}
              onChange={(e) => updateField("pollText", e.target.value)}
              placeholder="e.g. Should we add dedicated bus lanes on the main roads?"
              rows={2}
              className={inputClass}
            />
          </div>

          {/* Revert Poll Text */}
          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">
              Revert Poll Text
            </label>
            <input
              type="text"
              value={versionMetadata.revertPollText}
              onChange={(e) => updateField("revertPollText", e.target.value)}
              placeholder="e.g. Remove bus lanes again?"
              className={inputClass}
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">
              Description
            </label>
            <textarea
              value={versionMetadata.description}
              onChange={(e) => updateField("description", e.target.value)}
              rows={2}
              className={inputClass}
            />
          </div>

          <button
            onClick={() => dispatch({ type: "SET_VERSION_DIFF_STEP", step: 2 })}
            disabled={!canProceed}
            className="w-full px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            Start Editing
          </button>
        </div>
      </div>
    );
  }

  // ─── Step 2: Modify Map ─────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Collapsed metadata summary */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-3 border border-subtle dark:border-darksubtle">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-main dark:text-darktext truncate">
              {versionMetadata.versionName}
            </p>
            <p className="text-xs text-muted dark:text-darkmutedtext mt-0.5 line-clamp-2">
              {versionMetadata.pollText}
            </p>
          </div>
          <button
            onClick={() => dispatch({ type: "SET_VERSION_DIFF_STEP", step: 1 })}
            className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline ml-2 shrink-0"
          >
            Edit
          </button>
        </div>
      </div>

      {/* Instructions when nothing is happening */}
      {!selectedEdge && !versionDiffEditingPtLine && totalChanges === 0 && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
          <p className="text-sm text-muted dark:text-darkmutedtext">
            Use the toolbar tools to modify the map. Click edges to change their
            properties, add/delete nodes and edges, or add/modify PT lines below.
          </p>
        </div>
      )}

      {/* Selected edge editing (when select tool is active) */}
      {selectedEdge && !versionDiffEditingPtLine && (
        <EdgePropertyPanel
          edge={selectedEdge}
          mode="modify"
          onChange={handleEdgeChange}
          onModifyDone={() => dispatch({ type: "CLEAR_SELECTION" })}
        />
      )}

      {/* ── PT Lines Section ── */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
        <h3 className="text-sm font-semibold text-main dark:text-darktext">
          PT Lines
        </h3>

        {/* PT line draft form */}
        {versionDiffEditingPtLine && (
          <div className="border border-amber-300 dark:border-amber-700 rounded-md p-3 space-y-2 bg-body dark:bg-darkbody">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-main dark:text-darktext">
                {versionDiffEditingPtLine.action === "add" ? "Add" : "Modify"}{" "}
                {versionDiffEditingPtLine.line_type === "bus" ? "Bus" : "Train"} Line
              </span>
              <button
                onClick={cancelPtDraft}
                className="text-xs text-muted dark:text-darkmutedtext hover:text-main dark:hover:text-darktext"
              >
                Cancel
              </button>
            </div>
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">Name</label>
              <input
                type="text"
                value={ptDraftName}
                onChange={(e) => setPtDraftName(e.target.value)}
                className="w-full mt-0.5 px-2 py-1 text-xs rounded border border-subtle dark:border-darksubtle bg-subtle dark:bg-darksubtle text-main dark:text-darktext"
              />
            </div>
            <div className="grid grid-cols-3 gap-1">
              <div>
                <label className="text-xs text-muted dark:text-darkmutedtext">Interval</label>
                <input
                  type="number"
                  min={1}
                  value={ptDraftInterval}
                  onChange={(e) => setPtDraftInterval(parseInt(e.target.value) || 1)}
                  className="w-full mt-0.5 px-1 py-1 text-xs rounded border border-subtle dark:border-darksubtle bg-subtle dark:bg-darksubtle text-main dark:text-darktext"
                />
              </div>
              <div>
                <label className="text-xs text-muted dark:text-darkmutedtext">Capacity</label>
                <input
                  type="number"
                  min={1}
                  value={ptDraftCapacity}
                  onChange={(e) => setPtDraftCapacity(parseInt(e.target.value) || 1)}
                  className="w-full mt-0.5 px-1 py-1 text-xs rounded border border-subtle dark:border-darksubtle bg-subtle dark:bg-darksubtle text-main dark:text-darktext"
                />
              </div>
              <div>
                <label className="text-xs text-muted dark:text-darkmutedtext">Speed</label>
                <input
                  type="number"
                  min={1}
                  value={ptDraftSpeed}
                  onChange={(e) => setPtDraftSpeed(parseInt(e.target.value) || 1)}
                  className="w-full mt-0.5 px-1 py-1 text-xs rounded border border-subtle dark:border-darksubtle bg-subtle dark:bg-darksubtle text-main dark:text-darktext"
                />
              </div>
            </div>
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext">
                Route ({ptLineEdgeIds.length} edges) — click edges on map
              </p>
              {ptLineEdgeIds.length > 0 && (
                <div className="flex flex-col gap-0.5 mt-1 max-h-32 overflow-y-auto">
                  {ptLineEdgeIds.map((id, idx) => {
                    const compatible = isEdgeCompatible(
                      id,
                      versionDiffEditingPtLine.line_type,
                    );
                    return (
                      <span
                        key={`${id}-${idx}`}
                        className={`text-xs px-1.5 py-0.5 rounded cursor-pointer hover:line-through ${
                          !compatible
                            ? "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
                            : "bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100"
                        }`}
                        onClick={() =>
                          setPtLineEdgeIds(ptLineEdgeIds.filter((_, i) => i !== idx))
                        }
                        title={!compatible ? "Incompatible edge — click to remove" : "Click to remove"}
                      >
                        {idx + 1}: {getEdgeLabel(id)}
                        {!compatible && " !!"}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
            {ptDraftError && (
              <p className="text-xs text-red-600 dark:text-red-400">{ptDraftError}</p>
            )}
            <button
              onClick={savePtDraft}
              className="w-full px-2 py-1 text-xs bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Save PT Line Change
            </button>
          </div>
        )}

        {/* Existing PT lines list */}
        {!versionDiffEditingPtLine && (
          <>
            {allPtLines.length === 0 ? (
              <p className="text-xs text-muted dark:text-darkmutedtext">
                No PT lines in this version.
              </p>
            ) : (
              <div className="space-y-1">
                {allPtLines.map((line) => {
                  const changeAction = getPtLineChangeAction(line.id, line.type);
                  return (
                    <div
                      key={`${line.type}-${line.id}`}
                      className={`flex items-center justify-between rounded p-2 ${
                        changeAction
                          ? "bg-amber-50 dark:bg-amber-950 border border-amber-300 dark:border-amber-700"
                          : "bg-body dark:bg-darkbody"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <span
                          className={`inline-block text-xs px-1.5 py-0.5 rounded mr-1 ${
                            line.type === "bus"
                              ? "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100"
                              : "bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100"
                          }`}
                        >
                          {line.type}
                        </span>
                        <span className="text-xs font-medium text-main dark:text-darktext">
                          {line.name}
                        </span>
                        {changeAction && (
                          <span
                            className={`inline-block text-xs px-1 py-0.5 rounded ml-1 ${
                              changeAction === "remove"
                                ? "bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100"
                                : "bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100"
                            }`}
                          >
                            {changeAction}
                          </span>
                        )}
                      </div>
                      <div className="flex gap-1 shrink-0 ml-1">
                        {changeAction === "remove" ? (
                          <button
                            onClick={() => {
                              const idx = ptLineChanges.findIndex(
                                (c) => c.id === line.id && c.line_type === line.type,
                              );
                              if (idx >= 0) removePtLineChange(idx);
                            }}
                            className="text-xs text-amber-600 dark:text-amber-400 hover:underline"
                          >
                            Undo
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={() => startModifyPtLine(line)}
                              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                            >
                              Modify
                            </button>
                            <button
                              onClick={() => addRemovePtLine(line)}
                              className="text-xs text-red-600 dark:text-red-400 hover:underline"
                            >
                              Remove
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Add new PT line buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => startAddPtLine("bus")}
                className="flex-1 px-2 py-1 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                + Bus Line
              </button>
              <button
                onClick={() => startAddPtLine("train")}
                className="flex-1 px-2 py-1 text-xs bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                + Train Line
              </button>
            </div>
          </>
        )}
      </div>

      {/* ── Changeset Summary ── */}
      {totalChanges > 0 && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-amber-300 dark:border-amber-700 space-y-3">
          <h3 className="text-sm font-semibold text-main dark:text-darktext">
            Changes ({totalChanges})
          </h3>

          {/* Edge property changes */}
          {edgeChanges.length > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                Edge Modifications ({edgeChanges.length})
              </p>
              <div className="space-y-1">
                {edgeChanges.map((change) => {
                  const edge = mapGraph?.edges.find((e) => e.id === change.edge_id);
                  const fields = Object.keys(change).filter((k) => k !== "edge_id");
                  return (
                    <div
                      key={change.edge_id}
                      className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                    >
                      <div>
                        <span className="text-xs font-medium text-main dark:text-darktext">
                          {edge?.name || `Edge ${change.edge_id}`}
                        </span>
                        <span className="text-xs text-muted dark:text-darkmutedtext ml-1">
                          {fields.join(", ")}
                        </span>
                      </div>
                      <button
                        onClick={() => removeEdgeChange(change.edge_id)}
                        className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                      >
                        Undo
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* PT line changes */}
          {ptLineChanges.length > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                PT Line Changes ({ptLineChanges.length})
              </p>
              <div className="space-y-1">
                {ptLineChanges.map((change, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                  >
                    <div>
                      <span
                        className={`inline-block text-xs px-1.5 py-0.5 rounded mr-1 ${
                          change.action === "add"
                            ? "bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100"
                            : change.action === "remove"
                              ? "bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100"
                              : "bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100"
                        }`}
                      >
                        {change.action}
                      </span>
                      <span className="text-xs text-main dark:text-darktext">
                        {change.name || `${change.line_type} line`}
                      </span>
                    </div>
                    <button
                      onClick={() => removePtLineChange(idx)}
                      className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                    >
                      Undo
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* New nodes */}
          {newNodes.length > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                New Nodes ({newNodes.length})
              </p>
              <div className="space-y-1">
                {newNodes.map((node) => (
                  <div
                    key={node.tempId}
                    className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                  >
                    <span className="text-xs text-green-700 dark:text-green-400">
                      New node at ({node.x_position.toFixed(2)}, {node.y_position.toFixed(2)})
                    </span>
                    <button
                      onClick={() => removeNewNode(node.tempId)}
                      className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* New edges */}
          {newEdges.length > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                New Edges ({newEdges.length})
              </p>
              <div className="space-y-1">
                {newEdges.map((edge) => (
                  <div
                    key={edge.tempId}
                    className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                  >
                    <span className="text-xs text-green-700 dark:text-green-400">
                      {getVirtualEdgeLabel(edge)}
                      {edge.bidirectional && " (↔)"}
                    </span>
                    <button
                      onClick={() => removeNewEdge(edge.tempId)}
                      className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Deleted nodes */}
          {deletedNodeIds.size > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                Deleted Nodes ({deletedNodeIds.size})
              </p>
              <div className="space-y-1">
                {[...deletedNodeIds].map((nodeId) => (
                  <div
                    key={nodeId}
                    className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                  >
                    <span className="text-xs text-red-700 dark:text-red-400 line-through">
                      {getNodeLabel(nodeId)}
                    </span>
                    <button
                      onClick={() => undoDeletedNode(nodeId)}
                      className="text-xs text-amber-600 hover:text-amber-800 dark:text-amber-400"
                    >
                      Undo
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Deleted edges (non-cascade only in display) */}
          {deletedEdgeIds.size > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                Deleted Edges ({deletedEdgeIds.size})
              </p>
              <div className="space-y-1">
                {[...deletedEdgeIds].map((edgeId) => {
                  const isCascade = [...cascadeDeletedEdgeIds.values()].some(
                    (s) => s.has(edgeId),
                  );
                  return (
                    <div
                      key={edgeId}
                      className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                    >
                      <span className="text-xs text-red-700 dark:text-red-400 line-through">
                        {getEdgeLabel(edgeId)}
                        {isCascade && (
                          <span className="text-xs text-muted dark:text-darkmutedtext ml-1 no-underline">
                            (cascade)
                          </span>
                        )}
                      </span>
                      {!isCascade && (
                        <button
                          onClick={() => undoDeletedEdge(edgeId)}
                          className="text-xs text-amber-600 hover:text-amber-800 dark:text-amber-400"
                        >
                          Undo
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Version button */}
      <div className="space-y-2">
        <button
          onClick={handleCreateVersion}
          disabled={createMutation.isPending || totalChanges === 0 || !!versionDiffEditingPtLine}
          className="w-full px-3 py-1.5 text-sm bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:opacity-50"
        >
          {createMutation.isPending
            ? "Creating..."
            : `Create Version (${totalChanges} change${totalChanges !== 1 ? "s" : ""})`}
        </button>

        {versionDiffEditingPtLine && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Save or cancel the PT line edit first.
          </p>
        )}

        {createMutation.isError && (
          <p className="text-xs text-red-600 dark:text-red-400">
            Failed to create version. Please try again.
          </p>
        )}

        {createMutation.isSuccess && (
          <p className="text-xs text-green-600 dark:text-green-400">
            Version created successfully!
          </p>
        )}
      </div>
    </div>
  );
};

export default VersionDiffPanel;
