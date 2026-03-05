import { useState, useEffect } from "react";
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
} from "../../../hooks/mapEditorHooks";

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
  const [capacity, setCapacity] = useState(60);
  const [speed, setSpeed] = useState(30);

  // Edit mode state
  const [editingLine, setEditingLine] = useState<PTLine | null>(null);
  const [editName, setEditName] = useState("");
  const [editInterval, setEditInterval] = useState(5);
  const [editCapacity, setEditCapacity] = useState(60);
  const [editSpeed, setEditSpeed] = useState(30);

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
    // Set edge IDs — these are the underlying edge IDs from the graph
    setPtLineEdgeIds(line.edges);
    // Clear any create mode
    setPtLineCreating(null);
  };

  const cancelEdit = () => {
    setEditingLine(null);
    setPtLineEdgeIds([]);
  };

  const handleSaveEdit = () => {
    if (!editingLine) return;

    // Resolve edge IDs to StreetEdge/TrainEdge IDs
    const resolvedEdgeIds = resolveEdgeIds(editingLine.type, ptLineEdgeIds);
    if (resolvedEdgeIds.length === 0) return;

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

    const resolvedEdgeIds = resolveEdgeIds(ptLineCreating, ptLineEdgeIds);
    if (resolvedEdgeIds.length === 0) return;

    const versionIds = selectedVersionId
      ? [selectedVersionId]
      : mapGraph?.version_id
        ? [mapGraph.version_id]
        : [];

    if (ptLineCreating === "bus") {
      createBusMutation.mutate(
        {
          name: name || "New Bus Line",
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
          name: name || "New Train Line",
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

  const getEdgeLabel = (edgeId: number) => {
    const edge = mapGraph?.edges.find((e) => e.id === edgeId);
    if (!edge) return `Edge ${edgeId}`;
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
  };

  return (
    <div className="space-y-4">
      {/* Existing lines */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
        <h3 className="text-lg font-semibold text-main dark:text-darktext mb-3">
          PT Lines ({allLines.length})
        </h3>
        {allLines.length === 0 ? (
          <p className="text-sm text-muted dark:text-darkmutedtext">
            No public transport lines yet.
          </p>
        ) : (
          <div className="space-y-2">
            {allLines.map((line) => (
              <div
                key={`${line.type}-${line.id}`}
                className={`flex items-center justify-between rounded p-2 ${
                  editingLine?.id === line.id && editingLine?.type === line.type
                    ? "bg-amber-50 dark:bg-amber-950 border border-amber-300 dark:border-amber-700"
                    : "bg-body dark:bg-darkbody"
                }`}
              >
                <div>
                  <span
                    className={`inline-block text-xs px-1.5 py-0.5 rounded mr-2 ${
                      line.type === "bus"
                        ? "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100"
                        : "bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100"
                    }`}
                  >
                    {line.type}
                  </span>
                  <span className="text-sm font-medium text-main dark:text-darktext">
                    {line.name}
                  </span>
                  <span className="text-xs text-muted dark:text-darkmutedtext ml-2">
                    {line.edges.length} edges, {line.interval}min
                  </span>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => startEdit(line)}
                    disabled={!!ptLineCreating || (!!editingLine && editingLine.id !== line.id)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 disabled:opacity-30"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() =>
                      deleteMutation.mutate({
                        lineId: line.id,
                        lineType: line.type as "bus" | "train",
                      })
                    }
                    disabled={!!editingLine || !!ptLineCreating}
                    className="text-xs text-red-600 hover:text-red-800 dark:text-red-400 disabled:opacity-30"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit form */}
      {editingLine && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-amber-300 dark:border-amber-700 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-main dark:text-darktext">
              Edit {editingLine.type === "bus" ? "Bus" : "Train"} Line
            </h3>
            <button
              onClick={cancelEdit}
              className="text-xs text-muted dark:text-darkmutedtext hover:text-main dark:hover:text-darktext"
            >
              Cancel
            </button>
          </div>

          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">Name</label>
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">
                Interval
              </label>
              <input
                type="number"
                min={1}
                value={editInterval}
                onChange={(e) => setEditInterval(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
              />
            </div>
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">Capacity</label>
              <input
                type="number"
                min={1}
                value={editCapacity}
                onChange={(e) => setEditCapacity(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
              />
            </div>
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">Speed</label>
              <input
                type="number"
                min={1}
                value={editSpeed}
                onChange={(e) => setEditSpeed(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
              />
            </div>
          </div>

          {/* Editable edge list */}
          <div>
            <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
              Route ({ptLineEdgeIds.length} edges)
            </p>
            {ptLineEdgeIds.length === 0 ? (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Click edges on the map to build the route
              </p>
            ) : (
              <div className="flex flex-col gap-1">
                {ptLineEdgeIds.map((id, idx) => {
                  const isEnd = idx === 0 || idx === ptLineEdgeIds.length - 1;
                  const hasReverse = findReverseEdgeId(id) !== null;
                  return (
                    <div
                      key={`${id}-${idx}`}
                      className="flex items-center gap-1"
                    >
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded flex-1 ${
                          isEnd
                            ? "bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100 cursor-pointer hover:line-through"
                            : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300"
                        }`}
                        onClick={() => {
                          if (isEnd) {
                            setPtLineEdgeIds(
                              ptLineEdgeIds.filter((_, i) => i !== idx)
                            );
                          }
                        }}
                        title={isEnd ? "Click to remove" : ""}
                      >
                        {idx + 1}: {getEdgeLabel(id)}
                      </span>
                      {hasReverse && (
                        <button
                          onClick={() => handleFlipEdge(idx)}
                          className="text-xs px-1 py-0.5 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 rounded"
                          title="Flip direction"
                        >
                          ↔
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <p className="text-xs text-muted dark:text-darkmutedtext mt-1">
              Click edges on map to extend. Click end edges to remove.
            </p>
          </div>

          <button
            onClick={handleSaveEdit}
            disabled={isEditPending || ptLineEdgeIds.length === 0}
            className="w-full px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {isEditPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      )}

      {/* Create form */}
      {ptLineCreating && !editingLine && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-amber-300 dark:border-amber-700 space-y-3">
          <h3 className="text-lg font-semibold text-main dark:text-darktext">
            New {ptLineCreating === "bus" ? "Bus" : "Train"} Line
          </h3>

          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={ptLineCreating === "bus" ? "e.g. M1" : "e.g. S1"}
              className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">
                Interval
              </label>
              <input
                type="number"
                min={1}
                value={interval}
                onChange={(e) => setInterval(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
              />
            </div>
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">Capacity</label>
              <input
                type="number"
                min={1}
                value={capacity}
                onChange={(e) => setCapacity(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
              />
            </div>
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">Speed</label>
              <input
                type="number"
                min={1}
                value={speed}
                onChange={(e) => setSpeed(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
              />
            </div>
          </div>

          {/* Selected edges */}
          <div>
            <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
              Route ({ptLineEdgeIds.length} edges selected)
            </p>
            {ptLineEdgeIds.length === 0 ? (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Click edges on the map to build the route
              </p>
            ) : (
              <div className="flex flex-col gap-1">
                {ptLineEdgeIds.map((id, idx) => {
                  const hasReverse = findReverseEdgeId(id) !== null;
                  return (
                    <div
                      key={`${id}-${idx}`}
                      className="flex items-center gap-1"
                    >
                      <span
                        className="text-xs bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100 px-1.5 py-0.5 rounded cursor-pointer hover:line-through flex-1"
                        onClick={() =>
                          setPtLineEdgeIds(
                            ptLineEdgeIds.filter((_, i) => i !== idx)
                          )
                        }
                      >
                        {idx + 1}: {getEdgeLabel(id)}
                      </span>
                      {hasReverse && (
                        <button
                          onClick={() => handleFlipEdge(idx)}
                          className="text-xs px-1 py-0.5 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 rounded"
                          title="Flip direction"
                        >
                          ↔
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <button
            onClick={handleSaveCreate}
            disabled={isCreatePending || ptLineEdgeIds.length === 0}
            className="w-full px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {isCreatePending ? "Saving..." : "Save Line"}
          </button>
        </div>
      )}
    </div>
  );
};

export default PTLinePanel;
