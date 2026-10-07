import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EditorField,
  EditorNote,
  EditorPanel,
  editorControl,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { defaultPtCapacity, defaultPtSpeed } from "@/lib/map/pt-defaults";
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
import { useCreateVersionFromDiff } from "@/lib/queries/map-editor";
import EdgePropertyPanel from "./EdgePropertyPanel";

/**
 * Building an alternate version: the metadata, then the changes, then submit.
 *
 * ### S18: it was the most English screen left in the SPA
 *
 * `Changes (n)`, `PT Line Changes (n)`, five `Undo` buttons, `(cascade)`,
 * `"Creating..."`, `Create Version (n changes)` — and a badge that rendered
 * `change.action` **raw**, so the class's own vocabulary for a pending change was
 * `add`, `modify`, `remove`. S17's detector saw none of it: `Undo` and
 * `"Creating..."` are one word, and none of the rest carried a word from its
 * giveaway list. That list has grown and the detector reads two more shapes now
 * — see `tests/design/german.test.ts`.
 *
 * A data value is not copy. It becomes copy the moment something renders it,
 * which is what `de.editor.version.action` is for.
 *
 * ### Colour
 *
 * The rulebook's pair, and this panel is the clearest case for it: **primary is
 * what this version adds, the accent is what it takes away**. Where the old code
 * had green-for-new, red-for-deleted, amber-for-changed and a second amber for
 * "undo", there are now two.
 */

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
  const [ptDraftCapacity, setPtDraftCapacity] = useState(defaultPtCapacity("bus"));
  const [ptDraftSpeed, setPtDraftSpeed] = useState(defaultPtSpeed("bus"));
  const [ptDraftKind, setPtDraftKind] = useState<"train" | "tram">("train");
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
    if (!edge) return de.editor.edge.numbered(edgeId);
    const sn = mapGraph?.nodes.find((n) => n.id === edge.start_node);
    const en = mapGraph?.nodes.find((n) => n.id === edge.end_node);
    return `${sn?.name || edge.start_node} → ${en?.name || edge.end_node}`;
  };

  const getNodeLabel = (nodeId: number) => {
    const node = mapGraph?.nodes.find((n) => n.id === nodeId);
    return node?.name || de.editor.node.numbered(nodeId);
  };

  const getVirtualEdgeLabel = (ve: VirtualEdge) => {
    const startLabel =
      typeof ve.start_node === "string"
        ? newNodes.find((n) => n.tempId === ve.start_node)
          ? de.editor.version.newNodePending
          : de.editor.version.newNodeMissing(ve.start_node)
        : getNodeLabel(ve.start_node);
    const endLabel =
      typeof ve.end_node === "string"
        ? newNodes.find((n) => n.tempId === ve.end_node)
          ? de.editor.version.newNodePending
          : de.editor.version.newNodeMissing(ve.end_node)
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
      capacity: defaultPtCapacity(type),
      speed_kmh: defaultPtSpeed(type),
    });
    setPtDraftName("");
    setPtDraftInterval(5);
    setPtDraftCapacity(defaultPtCapacity(type));
    setPtDraftSpeed(defaultPtSpeed(type));
    setPtDraftKind("train");
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
    setPtDraftKind(existingChange?.kind ?? line.kind ?? "train");
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
      setPtDraftError(de.editor.ptLine.needsOneEdge);
      return;
    }

    const type = versionDiffEditingPtLine.line_type;
    const incompatible = ptLineEdgeIds.filter((id) => !isEdgeCompatible(id, type));
    if (incompatible.length > 0) {
      setPtDraftError(
        type === "bus"
          ? de.editor.ptLine.missingStreet(incompatible.length)
          : de.editor.ptLine.missingTrain(incompatible.length),
      );
      return;
    }

    const resolvedEdgeIds = resolveEdgeIds(type, ptLineEdgeIds);
    if (resolvedEdgeIds.length === 0) {
      setPtDraftError(de.editor.ptLine.noValidEdges);
      return;
    }

    const change: PTLineChange = {
      id: versionDiffEditingPtLine.existingLineId,
      action: versionDiffEditingPtLine.action,
      line_type: type,
      ...(type === "train" ? { kind: ptDraftKind } : {}),
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

  // ─── Step 1: Version Metadata Form ─────────────────────────────────
  if (versionDiffStep === 1) {
    return (
      <EditorPanel title={de.editor.version.createTitle}>
        <EditorNote>{de.editor.version.createLead}</EditorNote>

        <EditorField label={de.editor.version.sourceVersion}>
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
            className={editorControl}
          >
            <option value="">
              {mapGraph
                ? de.editor.version.current(mapGraph.version_name)
                : de.editor.loading}
            </option>
            {versions?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} {v.base_version ? de.editor.version.baseSuffix : ""}
              </option>
            ))}
          </select>
        </EditorField>

        <EditorField
          label={
            <>
              {de.editor.version.versionName}{" "}
              <span className="text-destructive">*</span>
            </>
          }
        >
          <input
            type="text"
            value={versionMetadata.versionName}
            onChange={(e) => updateField("versionName", e.target.value)}
            placeholder={de.editor.version.namePlaceholder}
            className={editorControl}
          />
        </EditorField>

        <EditorField
          label={
            <>
              {de.editor.version.pollText}{" "}
              <span className="text-destructive">*</span>
            </>
          }
        >
          <p className="mb-1 text-xs text-muted-foreground">
            {de.editor.version.pollQuestion}
          </p>
          <textarea
            value={versionMetadata.pollText}
            onChange={(e) => updateField("pollText", e.target.value)}
            placeholder={de.editor.version.pollPlaceholder}
            rows={2}
            className={editorControl}
          />
        </EditorField>

        <EditorField label={de.editor.version.pollRevert}>
          <input
            type="text"
            value={versionMetadata.revertPollText}
            onChange={(e) => updateField("revertPollText", e.target.value)}
            placeholder={de.editor.version.revertPlaceholder}
            className={editorControl}
          />
        </EditorField>

        <EditorField label={de.editor.version.description}>
          <textarea
            value={versionMetadata.description}
            onChange={(e) => updateField("description", e.target.value)}
            rows={2}
            className={editorControl}
          />
        </EditorField>

        <Button
          size="sm"
          className="w-full"
          onClick={() => dispatch({ type: "SET_VERSION_DIFF_STEP", step: 2 })}
          disabled={!canProceed}
        >
          {de.editor.version.startEditing}
        </Button>
      </EditorPanel>
    );
  }

  // ─── Step 2: Modify Map ─────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Collapsed metadata summary */}
      <div className="rounded-xl border bg-card p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">
              {versionMetadata.versionName}
            </p>
            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
              {versionMetadata.pollText}
            </p>
          </div>
          <Button
            size="xs"
            variant="ghost"
            className="shrink-0"
            onClick={() => dispatch({ type: "SET_VERSION_DIFF_STEP", step: 1 })}
          >
            {de.editor.edit}
          </Button>
        </div>
      </div>

      {/* Instructions when nothing is happening */}
      {!selectedEdge && !versionDiffEditingPtLine && totalChanges === 0 && (
        <EditorPanel>
          <p className="text-sm text-muted-foreground">
            {de.editor.version.diffHint}
          </p>
        </EditorPanel>
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
      <EditorPanel title={de.editor.version.ptLines}>
        {/* PT line draft form */}
        {versionDiffEditingPtLine && (
          <div className="space-y-2 rounded-md border border-destructive p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold">
                {versionDiffEditingPtLine.action === "add"
                  ? versionDiffEditingPtLine.line_type === "bus"
                    ? de.editor.newBusLine
                    : de.editor.newTrainLine
                  : versionDiffEditingPtLine.line_type === "bus"
                    ? de.editor.ptLine.editBus
                    : de.editor.ptLine.editTrain}
              </span>
              <Button size="xs" variant="ghost" onClick={cancelPtDraft}>
                {de.editor.cancel}
              </Button>
            </div>
            <EditorField label={de.editor.ptLine.name}>
              <input
                type="text"
                value={ptDraftName}
                onChange={(e) => setPtDraftName(e.target.value)}
                className={editorControl}
              />
            </EditorField>
            {versionDiffEditingPtLine.line_type === "train" && (
              <EditorField label={de.editor.ptLine.kindLabel}>
                <select
                  value={ptDraftKind}
                  onChange={(e) => {
                    const kind = e.target.value as "train" | "tram";
                    setPtDraftKind(kind);
                    // A new line starts at its kind's seats and speed; a line
                    // being changed keeps the numbers it has.
                    if (versionDiffEditingPtLine.action === "add") {
                      setPtDraftCapacity(defaultPtCapacity(kind));
                      setPtDraftSpeed(defaultPtSpeed(kind));
                    }
                  }}
                  className={editorControl}
                >
                  <option value="train">{de.editor.ptLine.kinds.train}</option>
                  <option value="tram">{de.editor.ptLine.kinds.tram}</option>
                </select>
              </EditorField>
            )}
            <div className="grid grid-cols-3 gap-1">
              <EditorField label={de.editor.ptLine.interval}>
                <input
                  type="number"
                  min={1}
                  value={ptDraftInterval}
                  onChange={(e) => setPtDraftInterval(parseInt(e.target.value) || 1)}
                  className={editorControl}
                />
              </EditorField>
              <EditorField label={de.editor.ptLine.capacity}>
                <input
                  type="number"
                  min={1}
                  value={ptDraftCapacity}
                  onChange={(e) => setPtDraftCapacity(parseInt(e.target.value) || 1)}
                  className={editorControl}
                />
              </EditorField>
              <EditorField label={de.editor.ptLine.speed}>
                <input
                  type="number"
                  min={1}
                  value={ptDraftSpeed}
                  onChange={(e) => setPtDraftSpeed(parseInt(e.target.value) || 1)}
                  className={editorControl}
                />
              </EditorField>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                {de.editor.ptLine.routeOnMap(ptLineEdgeIds.length)}
              </p>
              {ptLineEdgeIds.length > 0 && (
                <div className="mt-1 flex max-h-32 flex-col gap-0.5 overflow-y-auto">
                  {ptLineEdgeIds.map((id, idx) => {
                    const compatible = isEdgeCompatible(
                      id,
                      versionDiffEditingPtLine.line_type,
                    );
                    return (
                      <span
                        key={`${id}-${idx}`}
                        className={cn(
                          "cursor-pointer rounded px-1.5 py-0.5 text-xs hover:line-through",
                          compatible
                            ? "border border-input"
                            : "bg-destructive font-medium text-destructive-foreground",
                        )}
                        onClick={() =>
                          setPtLineEdgeIds(ptLineEdgeIds.filter((_, i) => i !== idx))
                        }
                        title={
                          !compatible
                            ? de.editor.ptLine.incompatibleClickToRemove
                            : de.editor.ptLine.clickToRemove
                        }
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
              <EditorNote tone="attention">{ptDraftError}</EditorNote>
            )}
            <Button size="xs" className="w-full" onClick={savePtDraft}>
              {de.editor.version.savePtLine}
            </Button>
          </div>
        )}

        {/* Existing PT lines list */}
        {!versionDiffEditingPtLine && (
          <>
            {allPtLines.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                {de.editor.version.noPtLines}
              </p>
            ) : (
              <div className="space-y-1">
                {allPtLines.map((line) => {
                  const changeAction = getPtLineChangeAction(line.id, line.type);
                  return (
                    <div
                      key={`${line.type}-${line.id}`}
                      className={cn(
                        "flex items-center justify-between gap-1 rounded p-2",
                        changeAction && "bg-destructive/10",
                      )}
                    >
                      <div className="min-w-0 flex-1 space-x-1">
                        <Badge variant="outline">
                          {de.editor.ptLine.kind(line.type, line.kind)}
                        </Badge>
                        <span className="text-xs font-medium">{line.name}</span>
                        {changeAction && (
                          /* The badge rendered `change.action` raw — so a class
                             looking at the projector read "modify". */
                          <Badge
                            variant={
                              changeAction === "remove" ? "destructive" : "default"
                            }
                          >
                            {de.editor.version.action(changeAction)}
                          </Badge>
                        )}
                      </div>
                      <div className="ml-1 flex shrink-0 gap-1">
                        {changeAction === "remove" ? (
                          <Button
                            size="xs"
                            variant="ghost"
                            onClick={() => {
                              const idx = ptLineChanges.findIndex(
                                (c) => c.id === line.id && c.line_type === line.type,
                              );
                              if (idx >= 0) removePtLineChange(idx);
                            }}
                          >
                            {de.actions.undo}
                          </Button>
                        ) : (
                          <>
                            <Button
                              size="xs"
                              variant="ghost"
                              onClick={() => startModifyPtLine(line)}
                            >
                              {de.editor.modify}
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              className="text-destructive"
                              onClick={() => addRemovePtLine(line)}
                            >
                              {de.editor.remove}
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Add new PT line buttons. Bus and Bahn were blue and red; they are
                one line here and the label says which. */}
            <div className="flex gap-2">
              <Button
                size="xs"
                className="flex-1"
                onClick={() => startAddPtLine("bus")}
              >
                {de.editor.ptLine.addBus}
              </Button>
              <Button
                size="xs"
                className="flex-1"
                onClick={() => startAddPtLine("train")}
              >
                {de.editor.ptLine.addTrain}
              </Button>
            </div>
          </>
        )}
      </EditorPanel>

      {/* ── Changeset Summary ──

          Six lists of "a thing that changed, and a way to take it back", written
          out six times with six different colours: green for a new node, red for
          a deleted one, amber for the undo, red for the other undo. `ChangeRow`
          is the one shape, and it carries the palette's two: **primary for what
          this version adds, the accent for what it removes.** */}
      {totalChanges > 0 && (
        <EditorPanel attention title={de.editor.version.changeset(totalChanges)}>
          {/* Edge property changes */}
          {edgeChanges.length > 0 && (
            <ChangeGroup title={de.editor.version.edgeChanges(edgeChanges.length)}>
              {edgeChanges.map((change) => {
                const edge = mapGraph?.edges.find((e) => e.id === change.edge_id);
                const fields = Object.keys(change).filter((k) => k !== "edge_id");
                return (
                  <ChangeRow
                    key={change.edge_id}
                    onUndo={() => removeEdgeChange(change.edge_id)}
                  >
                    <span className="font-medium">
                      {edge?.name || de.editor.edge.numbered(change.edge_id)}
                    </span>{" "}
                    <span className="text-muted-foreground">
                      {fields.join(", ")}
                    </span>
                  </ChangeRow>
                );
              })}
            </ChangeGroup>
          )}

          {/* PT line changes */}
          {ptLineChanges.length > 0 && (
            <ChangeGroup
              title={de.editor.version.lineChanges(ptLineChanges.length)}
            >
              {ptLineChanges.map((change, idx) => (
                <ChangeRow key={idx} onUndo={() => removePtLineChange(idx)}>
                  <Badge
                    variant={
                      change.action === "remove" ? "destructive" : "default"
                    }
                    className="mr-1"
                  >
                    {de.editor.version.action(change.action)}
                  </Badge>
                  {change.name || de.editor.ptLine.unnamed(change.line_type, change.kind)}
                </ChangeRow>
              ))}
            </ChangeGroup>
          )}

          {/* New nodes */}
          {newNodes.length > 0 && (
            <ChangeGroup title={de.editor.version.newNodes(newNodes.length)}>
              {newNodes.map((node) => (
                <ChangeRow
                  key={node.tempId}
                  undoLabel={de.editor.remove}
                  onUndo={() => removeNewNode(node.tempId)}
                >
                  <span className="text-primary">
                    {de.editor.version.newNodeAt(
                      node.x_position.toFixed(2),
                      node.y_position.toFixed(2),
                    )}
                  </span>
                </ChangeRow>
              ))}
            </ChangeGroup>
          )}

          {/* New edges */}
          {newEdges.length > 0 && (
            <ChangeGroup title={de.editor.version.newEdges(newEdges.length)}>
              {newEdges.map((edge) => (
                <ChangeRow
                  key={edge.tempId}
                  undoLabel={de.editor.remove}
                  onUndo={() => removeNewEdge(edge.tempId)}
                >
                  <span className="text-primary">
                    {getVirtualEdgeLabel(edge)}
                    {edge.bidirectional && " (↔)"}
                  </span>
                </ChangeRow>
              ))}
            </ChangeGroup>
          )}

          {/* Deleted nodes */}
          {deletedNodeIds.size > 0 && (
            <ChangeGroup
              title={de.editor.version.deletedNodes(deletedNodeIds.size)}
            >
              {[...deletedNodeIds].map((nodeId) => (
                <ChangeRow key={nodeId} onUndo={() => undoDeletedNode(nodeId)}>
                  <span className="line-through">{getNodeLabel(nodeId)}</span>
                </ChangeRow>
              ))}
            </ChangeGroup>
          )}

          {/* Deleted edges. An edge that goes because its node goes cannot be
              taken back on its own, which is what the note says now — the old
              one said "(cascade)", which is the mechanism, not the consequence. */}
          {deletedEdgeIds.size > 0 && (
            <ChangeGroup
              title={de.editor.version.deletedEdges(deletedEdgeIds.size)}
            >
              {[...deletedEdgeIds].map((edgeId) => {
                const isCascade = [...cascadeDeletedEdgeIds.values()].some((set) =>
                  set.has(edgeId),
                );
                return (
                  <ChangeRow
                    key={edgeId}
                    onUndo={isCascade ? undefined : () => undoDeletedEdge(edgeId)}
                  >
                    <span className="line-through">{getEdgeLabel(edgeId)}</span>
                    {isCascade && (
                      <span className="ml-1 text-muted-foreground no-underline">
                        ({de.editor.version.cascadeSuffix})
                      </span>
                    )}
                  </ChangeRow>
                );
              })}
            </ChangeGroup>
          )}
        </EditorPanel>
      )}

      {/* Create Version button */}
      <div className="space-y-2">
        <Button
          size="sm"
          className="w-full"
          onClick={handleCreateVersion}
          disabled={
            createMutation.isPending ||
            totalChanges === 0 ||
            !!versionDiffEditingPtLine
          }
        >
          {createMutation.isPending
            ? de.editor.version.creating
            : de.editor.version.createWithCount(totalChanges)}
        </Button>

        {versionDiffEditingPtLine && (
          <EditorNote tone="attention">
            {de.editor.version.finishPtLineFirst}
          </EditorNote>
        )}

        {createMutation.isError && (
          <EditorNote tone="attention">
            {de.editor.version.createFailed}
          </EditorNote>
        )}

        {createMutation.isSuccess && (
          <EditorNote>{de.editor.version.created}</EditorNote>
        )}
      </div>
    </div>
  );
};

/** One kind of change, with its count. */
function ChangeGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1 text-xs text-muted-foreground">{title}</p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

/**
 * One pending change, and the way back out of it.
 *
 * `onUndo` is optional because a cascade-deleted edge has none: it goes when its
 * node goes and comes back the same way. The old code left the button off and
 * said nothing, so the row just looked different for no stated reason.
 */
function ChangeRow({
  children,
  undoLabel,
  onUndo,
}: {
  children: React.ReactNode;
  undoLabel?: string;
  onUndo?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded bg-secondary/60 p-2 text-xs">
      <span className="min-w-0">{children}</span>
      {onUndo ? (
        <Button
          size="xs"
          variant="ghost"
          className="shrink-0 text-destructive"
          onClick={onUndo}
        >
          {undoLabel ?? de.actions.undo}
        </Button>
      ) : null}
    </div>
  );
}

export default VersionDiffPanel;
