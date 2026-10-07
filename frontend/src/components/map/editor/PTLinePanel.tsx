import { useState, useEffect } from "react";

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
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type { PTLine } from "../../../types/routeTypes";
import {
  useCreateBusLine,
  useCreateTrainLine,
  useDeletePTLine,
  useUpdateBusLine,
  useUpdateTrainLine,
  useUpdateBusLineEdges,
  useUpdateTrainLineEdges,
} from "@/lib/queries/map-editor";

interface PTLinePanelProps {
  mapId: string;
  mapGraph: ExtendedMapGraph | undefined;
  ptLineCreating: "bus" | "train" | null;
  ptLineEdgeIds: number[];
  setPtLineEdgeIds: (ids: number[]) => void;
  setPtLineCreating: (type: "bus" | "train" | null) => void;
  selectedVersionId: number | undefined;
}

const PTLinePanel = ({
  mapId,
  mapGraph,
  ptLineCreating,
  ptLineEdgeIds,
  setPtLineEdgeIds,
  setPtLineCreating,
  selectedVersionId,
}: PTLinePanelProps) => {
  const createBusMutation = useCreateBusLine(mapId);
  const createTrainMutation = useCreateTrainLine(mapId);
  const deleteMutation = useDeletePTLine(mapId);
  const updateBusMutation = useUpdateBusLine(mapId);
  const updateTrainMutation = useUpdateTrainLine(mapId);
  const updateBusEdgesMutation = useUpdateBusLineEdges(mapId);
  const updateTrainEdgesMutation = useUpdateTrainLineEdges(mapId);

  const [name, setName] = useState("");
  const [interval, setInterval] = useState(5);
  const [capacity, setCapacity] = useState(defaultPtCapacity("bus"));
  const [speed, setSpeed] = useState(defaultPtSpeed("bus"));
  // A train line's kind. A tram rides rails like any train line; its kind
  // sets its seats, its speed and its figures per km in the simulation.
  const [kind, setKind] = useState<TrainKind>("train");

  // Edit mode state
  const [editingLine, setEditingLine] = useState<PTLine | null>(null);
  const [editName, setEditName] = useState("");
  const [editInterval, setEditInterval] = useState(5);
  const [editCapacity, setEditCapacity] = useState(defaultPtCapacity("bus"));
  const [editSpeed, setEditSpeed] = useState(defaultPtSpeed("bus"));
  const [editKind, setEditKind] = useState<TrainKind>("train");

  // One panel serves both modes, so the seat default has to follow the mode
  // the host just picked rather than being fixed when the component mounts —
  // a train that opens at a bus's 85 seats is the bug this closes, one order
  // of magnitude smaller.
  //
  // The kind does the same for a train line: a tram starts at a tram's seats
  // and speed, not a U-Bahn's.
  useEffect(() => {
    if (!ptLineCreating) return;
    const vehicle = ptLineCreating === "bus" ? "bus" : kind;
    setCapacity(defaultPtCapacity(vehicle));
    setSpeed(defaultPtSpeed(vehicle));
  }, [ptLineCreating, kind]);

  // Sync edit edge IDs when editing
  useEffect(() => {
    if (editingLine) {
      // Resolve sub-edge IDs back to edge IDs for display
      // The ptLineEdgeIds are edge IDs (from the map graph), not sub-edge IDs
      setPtLineEdgeIds(editingLine.edges);
    }
  }, [editingLine?.id]);

  const allLines = [
    ...(mapGraph?.bus_lines ?? []),
    ...(mapGraph?.train_lines ?? []),
  ];

  const startEdit = (line: PTLine) => {
    setEditingLine(line);
    setEditName(line.name);
    setEditInterval(line.interval);
    setEditCapacity(line.capacity);
    setEditSpeed(line.speed_kmh);
    setEditKind(line.kind ?? "train");
    // Set edge IDs — these are the underlying edge IDs from the graph
    setPtLineEdgeIds(line.edges);
    // Clear any create mode
    setPtLineCreating(null);
  };

  const cancelEdit = () => {
    setEditingLine(null);
    setPtLineEdgeIds([]);
  };

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSaveEdit = () => {
    if (!editingLine) return;
    setValidationError(null);

    // Check for incompatible edges
    const incompatible = ptLineEdgeIds.filter(
      (id) => !isEdgeCompatible(id, editingLine.type),
    );
    if (incompatible.length > 0) {
      setValidationError(
        editingLine.type === "bus"
          ? de.editor.ptLine.missingStreet(incompatible.length)
          : de.editor.ptLine.missingTrain(incompatible.length),
      );
      return;
    }

    // Resolve edge IDs to StreetEdge/TrainEdge IDs
    const resolvedEdgeIds = resolveEdgeIds(editingLine.type, ptLineEdgeIds);
    if (resolvedEdgeIds.length === 0) {
      setValidationError(de.editor.ptLine.noValidEdges);
      return;
    }

    if (editingLine.type === "bus") {
      updateBusMutation.mutate(
        {
          lineId: editingLine.id,
          name: editName,
          intervall: editInterval,
          bus_capacity: editCapacity,
          bus_speed_kmh: editSpeed,
        },
        {
          onSuccess: () => {
            updateBusEdgesMutation.mutate(
              { lineId: editingLine.id, edges: resolvedEdgeIds },
              { onSuccess: cancelEdit }
            );
          },
        }
      );
    } else {
      updateTrainMutation.mutate(
        {
          lineId: editingLine.id,
          name: editName,
          kind: editKind,
          intervall: editInterval,
          train_capacity: editCapacity,
          train_speed_kmh: editSpeed,
        },
        {
          onSuccess: () => {
            updateTrainEdgesMutation.mutate(
              { lineId: editingLine.id, edges: resolvedEdgeIds },
              { onSuccess: cancelEdit }
            );
          },
        }
      );
    }
  };

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

  const handleSaveCreate = () => {
    if (!ptLineCreating || ptLineEdgeIds.length === 0) return;
    setValidationError(null);

    // Check for incompatible edges
    const incompatible = ptLineEdgeIds.filter(
      (id) => !isEdgeCompatible(id, ptLineCreating),
    );
    if (incompatible.length > 0) {
      setValidationError(
        ptLineCreating === "bus"
          ? de.editor.ptLine.missingStreet(incompatible.length)
          : de.editor.ptLine.missingTrain(incompatible.length),
      );
      return;
    }

    const resolvedEdgeIds = resolveEdgeIds(ptLineCreating, ptLineEdgeIds);
    if (resolvedEdgeIds.length === 0) {
      setValidationError(de.editor.ptLine.noValidEdges);
      return;
    }

    const versionIds = selectedVersionId
      ? [selectedVersionId]
      : mapGraph?.version_id
        ? [mapGraph.version_id]
        : [];

    if (ptLineCreating === "bus") {
      createBusMutation.mutate(
        {
          name: name || de.editor.newBusLine,
          intervall: interval,
          bus_capacity: capacity,
          bus_speed_kmh: speed,
          edges: resolvedEdgeIds,
          map_versions: versionIds,
        },
        {
          onSuccess: () => {
            setPtLineCreating(null);
            setPtLineEdgeIds([]);
            setName("");
          },
        }
      );
    } else {
      createTrainMutation.mutate(
        {
          name: name || de.editor.newTrainLine,
          kind,
          intervall: interval,
          train_capacity: capacity,
          train_speed_kmh: speed,
          edges: resolvedEdgeIds,
          map_versions: versionIds,
        },
        {
          onSuccess: () => {
            setPtLineCreating(null);
            setPtLineEdgeIds([]);
            setName("");
          },
        }
      );
    }
  };

  const isCreatePending =
    createBusMutation.isPending || createTrainMutation.isPending;
  const isEditPending =
    updateBusMutation.isPending ||
    updateTrainMutation.isPending ||
    updateBusEdgesMutation.isPending ||
    updateTrainEdgesMutation.isPending;

  // Check if an edge is compatible with the current PT line type
  const isEdgeCompatible = (
    edgeId: number,
    type: "bus" | "train" | null,
  ): boolean => {
    if (!type) return true;
    const edge = mapGraph?.edges.find((e) => e.id === edgeId);
    if (!edge) return false;
    if (type === "bus") return !!edge.street_edge;
    return !!edge.train_edge;
  };

  const getEdgeLabel = (edgeId: number) => {
    const edge = mapGraph?.edges.find((e) => e.id === edgeId);
    if (!edge) return de.editor.edge.numbered(edgeId);
    const sn = mapGraph?.nodes.find((n) => n.id === edge.start_node);
    const en = mapGraph?.nodes.find((n) => n.id === edge.end_node);
    return `${sn?.name || edge.start_node} → ${en?.name || edge.end_node}`;
  };

  const findReverseEdgeId = (edgeId: number): number | null => {
    const edge = mapGraph?.edges.find((e) => e.id === edgeId);
    if (!edge) return null;
    const reverse = mapGraph?.edges.find(
      (e) => e.start_node === edge.end_node && e.end_node === edge.start_node,
    );
    return reverse?.id ?? null;
  };

  const handleFlipEdge = (idx: number) => {
    const edgeId = ptLineEdgeIds[idx];
    const reverseId = findReverseEdgeId(edgeId);
    if (reverseId === null) return;
    const updated = [...ptLineEdgeIds];
    updated[idx] = reverseId;
    setPtLineEdgeIds(updated);
    setValidationError(null);
  };

  return (
    <div className="space-y-4">
      {/* Existing lines.

          Bus and Bahn used to be a blue badge and a red one. They are one line
          in this palette and the badge already says which — and red on this
          panel is the delete button two columns over. */}
      <EditorPanel title={de.editor.ptLine.countTitle(allLines.length)}>
        {allLines.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {de.editor.ptLine.none}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {allLines.map((line) => {
              const isEditing =
                editingLine?.id === line.id && editingLine?.type === line.type;
              return (
                <li
                  key={`${line.type}-${line.id}`}
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-2 py-2",
                    isEditing && "rounded-md bg-destructive/10 px-2",
                  )}
                >
                  <div className="flex flex-wrap items-baseline gap-2">
                    <Badge variant="outline">
                      {de.editor.ptLine.kind(line.type, line.kind)}
                    </Badge>
                    <span className="text-sm font-medium">{line.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {de.editor.ptLine.summary(line.edges.length, line.interval)}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => startEdit(line)}
                      disabled={
                        !!ptLineCreating ||
                        (!!editingLine && editingLine.id !== line.id)
                      }
                    >
                      {de.editor.edit}
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      className="text-destructive"
                      onClick={() =>
                        deleteMutation.mutate({
                          lineId: line.id,
                          lineType: line.type as "bus" | "train",
                        })
                      }
                      disabled={!!editingLine || !!ptLineCreating}
                    >
                      {de.editor.delete}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </EditorPanel>

      {/* Edit form. `attention` because it is a live mode: the canvas is taking
          clicks into this line's route until it is saved or cancelled. */}
      {editingLine && (
        <EditorPanel
          attention
          title={
            editingLine.type === "bus"
              ? de.editor.ptLine.editBus
              : de.editor.ptLine.editTrain
          }
          action={
            <Button size="xs" variant="ghost" onClick={cancelEdit}>
              {de.editor.cancel}
            </Button>
          }
        >
          <EditorField label={de.editor.ptLine.name}>
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className={editorControl}
            />
          </EditorField>

          {editingLine.type === "train" && (
            <KindField value={editKind} onChange={setEditKind} />
          )}

          <div className="grid grid-cols-3 gap-2">
            <EditorField label={de.editor.ptLine.interval}>
              <input
                type="number"
                min={1}
                value={editInterval}
                onChange={(e) => setEditInterval(parseInt(e.target.value) || 1)}
                className={editorControl}
              />
            </EditorField>
            <EditorField label={de.editor.ptLine.capacity}>
              <input
                type="number"
                min={1}
                value={editCapacity}
                onChange={(e) => setEditCapacity(parseInt(e.target.value) || 1)}
                className={editorControl}
              />
            </EditorField>
            <EditorField label={de.editor.ptLine.speed}>
              <input
                type="number"
                min={1}
                value={editSpeed}
                onChange={(e) => setEditSpeed(parseInt(e.target.value) || 1)}
                className={editorControl}
              />
            </EditorField>
          </div>

          <div>
            <p className="mb-1 text-xs text-muted-foreground">
              {de.editor.ptLine.routeCount(ptLineEdgeIds.length)}
            </p>
            <RouteEdgeList
              edgeIds={ptLineEdgeIds}
              lineType={editingLine.type as "bus" | "train"}
              removable="ends"
              getEdgeLabel={getEdgeLabel}
              isEdgeCompatible={isEdgeCompatible}
              findReverseEdgeId={findReverseEdgeId}
              onRemove={(idx) =>
                setPtLineEdgeIds(ptLineEdgeIds.filter((_, i) => i !== idx))
              }
              onFlip={handleFlipEdge}
            />
            <EditorNote>{de.editor.ptLine.extendHint}</EditorNote>
          </div>

          {validationError && (
            <EditorNote tone="attention">{validationError}</EditorNote>
          )}
          {(updateBusMutation.isError ||
            updateTrainMutation.isError ||
            updateBusEdgesMutation.isError ||
            updateTrainEdgesMutation.isError) && (
            <EditorNote tone="attention">
              {(updateBusMutation.error ||
                updateTrainMutation.error ||
                updateBusEdgesMutation.error ||
                updateTrainEdgesMutation.error)?.message ??
                de.editor.saveFailed}
            </EditorNote>
          )}

          <Button
            size="sm"
            className="w-full"
            onClick={handleSaveEdit}
            disabled={isEditPending || ptLineEdgeIds.length === 0}
          >
            {isEditPending ? de.editor.saving : de.editor.saveChanges}
          </Button>
        </EditorPanel>
      )}

      {/* Create form */}
      {ptLineCreating && !editingLine && (
        <EditorPanel
          attention
          title={
            ptLineCreating === "bus"
              ? de.editor.newBusLine
              : de.editor.newTrainLine
          }
        >
          <EditorField label={de.editor.ptLine.name}>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={de.editor.ptLine.namePlaceholder(ptLineCreating)}
              className={editorControl}
            />
          </EditorField>

          {ptLineCreating === "train" && <KindField value={kind} onChange={setKind} />}

          <div className="grid grid-cols-3 gap-2">
            <EditorField label={de.editor.ptLine.interval}>
              <input
                type="number"
                min={1}
                value={interval}
                onChange={(e) => setInterval(parseInt(e.target.value) || 1)}
                className={editorControl}
              />
            </EditorField>
            <EditorField label={de.editor.ptLine.capacity}>
              <input
                type="number"
                min={1}
                value={capacity}
                onChange={(e) => setCapacity(parseInt(e.target.value) || 1)}
                className={editorControl}
              />
            </EditorField>
            <EditorField label={de.editor.ptLine.speed}>
              <input
                type="number"
                min={1}
                value={speed}
                onChange={(e) => setSpeed(parseInt(e.target.value) || 1)}
                className={editorControl}
              />
            </EditorField>
          </div>

          <div>
            <p className="mb-1 text-xs text-muted-foreground">
              {de.editor.ptLine.routeSelected(ptLineEdgeIds.length)}
            </p>
            <RouteEdgeList
              edgeIds={ptLineEdgeIds}
              lineType={ptLineCreating}
              removable="any"
              getEdgeLabel={getEdgeLabel}
              isEdgeCompatible={isEdgeCompatible}
              findReverseEdgeId={findReverseEdgeId}
              onRemove={(idx) =>
                setPtLineEdgeIds(ptLineEdgeIds.filter((_, i) => i !== idx))
              }
              onFlip={handleFlipEdge}
            />
          </div>

          {validationError && (
            <EditorNote tone="attention">{validationError}</EditorNote>
          )}
          {(createBusMutation.isError || createTrainMutation.isError) && (
            <EditorNote tone="attention">
              {(createBusMutation.error || createTrainMutation.error)?.message ??
                de.editor.ptLine.createFailed}
            </EditorNote>
          )}

          <Button
            size="sm"
            className="w-full"
            onClick={handleSaveCreate}
            disabled={isCreatePending || ptLineEdgeIds.length === 0}
          >
            {isCreatePending ? de.editor.saving : de.editor.saveLine}
          </Button>
        </EditorPanel>
      )}
    </div>
  );
};

type TrainKind = "train" | "tram";

/** S- or U-Bahn, or tram: what runs a train line. */
function KindField({
  value,
  onChange,
}: {
  value: TrainKind;
  onChange: (kind: TrainKind) => void;
}) {
  return (
    <EditorField label={de.editor.ptLine.kindLabel}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as TrainKind)}
        className={editorControl}
      >
        <option value="train">{de.editor.ptLine.kinds.train}</option>
        <option value="tram">{de.editor.ptLine.kinds.tram}</option>
      </select>
    </EditorField>
  );
}

/**
 * The line's route as a list of links.
 *
 * It was written out twice, once in each form, with three differences that were
 * all accidents: the create list let you drop any link and the edit list only
 * the two ends (deliberate — a hole in the middle breaks the chain), but the
 * create list also had no `hover:line-through` on an incompatible chip and used
 * a different title for it. Once is once.
 *
 * The three states are the palette's: **a link the line cannot use is the
 * accent**, because it is the one thing here that has to be read; a link you may
 * drop is outlined, because it is a control; a link in the middle of the chain is
 * a filled neutral, because it is only context.
 */
function RouteEdgeList({
  edgeIds,
  lineType,
  removable,
  getEdgeLabel,
  isEdgeCompatible,
  findReverseEdgeId,
  onRemove,
  onFlip,
}: {
  edgeIds: number[];
  lineType: "bus" | "train";
  removable: "ends" | "any";
  getEdgeLabel: (edgeId: number) => string;
  isEdgeCompatible: (edgeId: number, type: "bus" | "train" | null) => boolean;
  findReverseEdgeId: (edgeId: number) => number | null;
  onRemove: (index: number) => void;
  onFlip: (index: number) => void;
}) {
  if (edgeIds.length === 0) {
    return <EditorNote tone="attention">{de.editor.ptLine.pickEdges}</EditorNote>;
  }

  return (
    <div className="flex flex-col gap-1">
      {edgeIds.map((id, idx) => {
        const isEnd = idx === 0 || idx === edgeIds.length - 1;
        const canRemove = removable === "any" || isEnd;
        const hasReverse = findReverseEdgeId(id) !== null;
        const compatible = isEdgeCompatible(id, lineType);

        return (
          <div key={`${id}-${idx}`} className="flex items-center gap-1">
            <span
              className={cn(
                "flex-1 rounded px-1.5 py-0.5 text-xs",
                !compatible
                  ? "bg-destructive font-medium text-destructive-foreground"
                  : canRemove
                    ? "border border-input"
                    : "bg-secondary text-secondary-foreground",
                canRemove && "cursor-pointer hover:line-through",
              )}
              onClick={() => {
                if (canRemove) onRemove(idx);
              }}
              title={
                !compatible
                  ? lineType === "bus"
                    ? de.editor.ptLine.noStreetHere
                    : de.editor.ptLine.noTrainHere
                  : canRemove
                    ? de.editor.ptLine.clickToRemove
                    : undefined
              }
            >
              {idx + 1}: {getEdgeLabel(id)}
              {!compatible && " !!"}
            </span>
            {hasReverse && (
              <Button
                size="icon-xs"
                variant="ghost"
                onClick={() => onFlip(idx)}
                title={de.editor.ptLine.flipDirection}
              >
                ↔
              </Button>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default PTLinePanel;
