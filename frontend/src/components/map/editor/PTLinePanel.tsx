import { useState } from "react";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import { useCreateBusLine, useCreateTrainLine, useDeletePTLine } from "../../../hooks/mapEditorHooks";

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

  const [name, setName] = useState("");
  const [interval, setInterval] = useState(5);
  const [capacity, setCapacity] = useState(60);
  const [speed, setSpeed] = useState(30);

  const allLines = [
    ...(mapGraph?.bus_lines ?? []),
    ...(mapGraph?.train_lines ?? []),
  ];

  const handleSave = () => {
    if (!ptLineCreating || ptLineEdgeIds.length === 0) return;

    // Resolve Edge IDs to StreetEdge/TrainEdge IDs
    const resolvedEdgeIds: number[] = [];
    for (const edgeId of ptLineEdgeIds) {
      const edge = mapGraph?.edges.find((e) => e.id === edgeId);
      if (!edge) continue;
      if (ptLineCreating === "bus" && edge.street_edge) {
        resolvedEdgeIds.push(edge.street_edge.id);
      } else if (ptLineCreating === "train" && edge.train_edge) {
        resolvedEdgeIds.push(edge.train_edge.id);
      }
    }

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

  const isPending = createBusMutation.isPending || createTrainMutation.isPending;

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
                className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
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
                <button
                  onClick={() =>
                    deleteMutation.mutate({
                      lineId: line.id,
                      lineType: line.type as "bus" | "train",
                    })
                  }
                  className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create form */}
      {ptLineCreating && (
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

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-muted dark:text-darkmutedtext">
                Interval (min)
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
          </div>

          <div>
            <label className="text-xs text-muted dark:text-darkmutedtext">
              Speed (km/h)
            </label>
            <input
              type="number"
              min={1}
              value={speed}
              onChange={(e) => setSpeed(parseInt(e.target.value) || 1)}
              className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
            />
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
              <div className="flex flex-wrap gap-1">
                {ptLineEdgeIds.map((id, idx) => (
                  <span
                    key={id}
                    className="text-xs bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100 px-1.5 py-0.5 rounded cursor-pointer hover:line-through"
                    onClick={() =>
                      setPtLineEdgeIds(ptLineEdgeIds.filter((_, i) => i !== idx))
                    }
                  >
                    {idx + 1}: Edge {id}
                  </span>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={handleSave}
            disabled={isPending || ptLineEdgeIds.length === 0}
            className="w-full px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {isPending ? "Saving..." : "Save Line"}
          </button>
        </div>
      )}
    </div>
  );
};

export default PTLinePanel;
