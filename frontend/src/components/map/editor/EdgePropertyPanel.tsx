import { useState, useEffect } from "react";
import type { Edge } from "../../../types/mapTypes";
import {
  useUpdateEdge,
  useDeleteEdge,
  useCreateStreetEdge,
  useDeleteStreetEdge,
  useCreateTrainEdge,
  useDeleteTrainEdge,
} from "../../../hooks/mapEditorHooks";

interface EdgeChangeFields {
  biking: boolean;
  walking: boolean;
  max_lanes: number;
  speed_limit: number;
  lanes: number;
  dedicated_bus_lane: boolean;
}

interface EdgePropertyPanelProps {
  edge: Edge;
  mapId?: string;
  versionId?: number;
  editable?: boolean;
  /** "edit" = default (graph mode), "modify" = version-diff mode with explicit commit */
  mode?: "edit" | "modify";
  onChange?: (changes: Partial<EdgeChangeFields>) => void;
  /** Called after "Modify" is clicked and changes are committed (used to deselect) */
  onModifyDone?: () => void;
}

const EdgePropertyPanel = ({
  edge,
  mapId,
  versionId,
  editable = false,
  mode = "edit",
  onChange,
  onModifyDone,
}: EdgePropertyPanelProps) => {
  // Direct-edit mode (graph mode with mapId) vs onChange mode (version-diff)
  const directEdit = editable && !!mapId && mode === "edit";
  const isModifyMode = mode === "modify";
  // Modify mode and directEdit both use local state
  const useLocalState = directEdit || isModifyMode;

  const updateEdgeMutation = useUpdateEdge(mapId ?? "");
  const deleteEdgeMutation = useDeleteEdge(mapId ?? "");
  const createStreetEdgeMutation = useCreateStreetEdge(mapId ?? "");
  const deleteStreetEdgeMutation = useDeleteStreetEdge(mapId ?? "");
  const createTrainEdgeMutation = useCreateTrainEdge(mapId ?? "");
  const deleteTrainEdgeMutation = useDeleteTrainEdge(mapId ?? "");

  const [biking, setBiking] = useState(edge.biking ?? true);
  const [walking, setWalking] = useState(edge.walking ?? true);
  const [maxLanes, setMaxLanes] = useState(edge.max_lanes ?? 1);
  const [speedLimit, setSpeedLimit] = useState(edge.street_edge?.speed_limit ?? 50);
  const [lanes, setLanes] = useState(edge.street_edge?.lanes ?? 1);
  const [busLane, setBusLane] = useState(edge.street_edge?.dedicated_bus_lane ?? false);

  useEffect(() => {
    setBiking(edge.biking ?? true);
    setWalking(edge.walking ?? true);
    setMaxLanes(edge.max_lanes ?? 1);
    setSpeedLimit(edge.street_edge?.speed_limit ?? 50);
    setLanes(edge.street_edge?.lanes ?? 1);
    setBusLane(edge.street_edge?.dedicated_bus_lane ?? false);
  }, [edge.id, edge.biking, edge.walking, edge.max_lanes, edge.street_edge]);

  const handleSave = () => {
    if (!mapId) return;
    updateEdgeMutation.mutate({
      edgeId: edge.id,
      biking,
      walking,
      max_lanes: maxLanes,
    });
    // Street edge properties are updated separately via StreetEdge PATCH
    // For now we handle this by delete + recreate if street edge exists and changed
    // TODO: add useUpdateStreetEdge if needed
  };

  const handleModify = () => {
    // Build diff of changed values
    const changes: Partial<EdgeChangeFields> = {};
    if (biking !== (edge.biking ?? true)) changes.biking = biking;
    if (walking !== (edge.walking ?? true)) changes.walking = walking;
    if (maxLanes !== (edge.max_lanes ?? 1)) changes.max_lanes = maxLanes;
    if (edge.street_edge) {
      if (speedLimit !== edge.street_edge.speed_limit) changes.speed_limit = speedLimit;
      if (lanes !== edge.street_edge.lanes) changes.lanes = lanes;
      if (busLane !== edge.street_edge.dedicated_bus_lane) changes.dedicated_bus_lane = busLane;
    }
    if (Object.keys(changes).length > 0) {
      onChange?.(changes);
    }
    onModifyDone?.();
  };

  const handleDelete = () => {
    if (!mapId) return;
    if (confirm("Delete this edge?")) {
      deleteEdgeMutation.mutate(edge.id);
    }
  };

  const handleAddStreetEdge = () => {
    if (!mapId) return;
    createStreetEdgeMutation.mutate({
      edge: edge.id,
      speed_limit: 50,
      lanes: 1,
      dedicated_bus_lane: false,
      map_versions: versionId ? [versionId] : [],
    });
  };

  const handleRemoveStreetEdge = () => {
    if (!mapId || !edge.street_edge) return;
    deleteStreetEdgeMutation.mutate(edge.street_edge.id);
  };

  const handleAddTrainEdge = () => {
    if (!mapId) return;
    createTrainEdgeMutation.mutate({
      edge: edge.id,
      map_versions: versionId ? [versionId] : [],
    });
  };

  const handleRemoveTrainEdge = () => {
    if (!mapId || !edge.train_edge) return;
    deleteTrainEdgeMutation.mutate(edge.train_edge.id);
  };

  const isPending =
    updateEdgeMutation.isPending ||
    deleteEdgeMutation.isPending ||
    createStreetEdgeMutation.isPending ||
    deleteStreetEdgeMutation.isPending ||
    createTrainEdgeMutation.isPending ||
    deleteTrainEdgeMutation.isPending;

  return (
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">
        {isModifyMode ? "Modify Edge" : "Edge"}
      </h3>
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext">Name</p>
        <p className="font-semibold text-main dark:text-darktext">
          {edge.name || `Edge ${edge.id}`}
        </p>
      </div>

      {/* Edge type badges + toggle buttons */}
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext mb-1">Type</p>
        <div className="flex flex-col gap-1">
          {edge.street_edge ? (
            <div className="flex items-center gap-1">
              <span className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100 px-2 py-1 rounded flex-1">
                Street ({edge.street_edge.speed_limit} km/h, {edge.street_edge.lanes} lane
                {edge.street_edge.lanes !== 1 ? "s" : ""})
                {edge.street_edge.dedicated_bus_lane && " + Bus Lane"}
              </span>
              {directEdit && (
                <button
                  onClick={handleRemoveStreetEdge}
                  className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                >
                  x
                </button>
              )}
            </div>
          ) : (
            directEdit && (
              <button
                onClick={handleAddStreetEdge}
                className="text-xs px-2 py-1 rounded border border-dashed border-gray-400 text-muted dark:text-darkmutedtext hover:border-gray-600"
              >
                + Make Street
              </button>
            )
          )}
          {edge.train_edge ? (
            <div className="flex items-center gap-1">
              <span className="text-xs bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 px-2 py-1 rounded flex-1">
                Train
              </span>
              {directEdit && (
                <button
                  onClick={handleRemoveTrainEdge}
                  className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                >
                  x
                </button>
              )}
            </div>
          ) : (
            directEdit && (
              <button
                onClick={handleAddTrainEdge}
                className="text-xs px-2 py-1 rounded border border-dashed border-red-400 text-muted dark:text-darkmutedtext hover:border-red-600"
              >
                + Make Train
              </button>
            )
          )}
          {!edge.street_edge && !edge.train_edge && !directEdit && (
            <span className="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 px-2 py-1 rounded">
              Path
            </span>
          )}
        </div>
      </div>

      {/* Properties */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted dark:text-darkmutedtext">Biking</span>
          {editable || isModifyMode ? (
            <input
              type="checkbox"
              checked={useLocalState ? biking : (edge.biking ?? true)}
              onChange={(e) => {
                if (useLocalState) setBiking(e.target.checked);
                else onChange?.({ biking: e.target.checked });
              }}
              className="rounded"
            />
          ) : (
            <span className="text-xs text-main dark:text-darktext">
              {edge.biking ? "Yes" : "No"}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted dark:text-darkmutedtext">Walking</span>
          {editable || isModifyMode ? (
            <input
              type="checkbox"
              checked={useLocalState ? walking : (edge.walking ?? true)}
              onChange={(e) => {
                if (useLocalState) setWalking(e.target.checked);
                else onChange?.({ walking: e.target.checked });
              }}
              className="rounded"
            />
          ) : (
            <span className="text-xs text-main dark:text-darktext">
              {edge.walking ? "Yes" : "No"}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted dark:text-darkmutedtext">Max Lanes</span>
          {editable || isModifyMode ? (
            <input
              type="number"
              min={1}
              max={6}
              value={useLocalState ? maxLanes : (edge.max_lanes ?? 2)}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (useLocalState) setMaxLanes(v);
                else onChange?.({ max_lanes: v });
              }}
              className="w-16 text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
            />
          ) : (
            <span className="text-xs text-main dark:text-darktext">{edge.max_lanes}</span>
          )}
        </div>

        {edge.street_edge && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">Speed Limit</span>
              {editable || isModifyMode ? (
                <input
                  type="number"
                  min={5}
                  max={200}
                  step={5}
                  value={useLocalState ? speedLimit : edge.street_edge.speed_limit}
                  onChange={(e) => {
                    const v = parseInt(e.target.value);
                    if (useLocalState) setSpeedLimit(v);
                    else onChange?.({ speed_limit: v });
                  }}
                  className="w-16 text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
                />
              ) : (
                <span className="text-xs text-main dark:text-darktext">
                  {edge.street_edge.speed_limit} km/h
                </span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">Lanes</span>
              {editable || isModifyMode ? (
                <input
                  type="number"
                  min={1}
                  max={6}
                  value={useLocalState ? lanes : edge.street_edge.lanes}
                  onChange={(e) => {
                    const v = parseInt(e.target.value);
                    if (useLocalState) setLanes(v);
                    else onChange?.({ lanes: v });
                  }}
                  className="w-16 text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
                />
              ) : (
                <span className="text-xs text-main dark:text-darktext">
                  {edge.street_edge.lanes}
                </span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">Bus Lane</span>
              {editable || isModifyMode ? (
                <input
                  type="checkbox"
                  checked={useLocalState ? busLane : edge.street_edge.dedicated_bus_lane}
                  onChange={(e) => {
                    if (useLocalState) setBusLane(e.target.checked);
                    else onChange?.({ dedicated_bus_lane: e.target.checked });
                  }}
                  className="rounded"
                />
              ) : (
                <span className="text-xs text-main dark:text-darktext">
                  {edge.street_edge.dedicated_bus_lane ? "Yes" : "No"}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {edge.distance_m != null && (
        <div>
          <p className="text-xs text-muted dark:text-darkmutedtext">Distance</p>
          <p className="text-sm text-main dark:text-darktext">
            {edge.distance_m.toFixed(0)} m
          </p>
        </div>
      )}

      {/* Save / Delete in direct edit mode */}
      {directEdit && (
        <div className="flex gap-2 pt-2">
          <button
            onClick={handleSave}
            disabled={isPending}
            className="flex-1 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {updateEdgeMutation.isPending ? "Saving..." : "Save"}
          </button>
          <button
            onClick={handleDelete}
            disabled={isPending}
            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      )}
      {updateEdgeMutation.isSuccess && (
        <p className="text-xs text-green-600 dark:text-green-400">Saved</p>
      )}
      {(updateEdgeMutation.isError ||
        deleteEdgeMutation.isError ||
        createStreetEdgeMutation.isError ||
        deleteStreetEdgeMutation.isError ||
        createTrainEdgeMutation.isError ||
        deleteTrainEdgeMutation.isError) && (
        <p className="text-xs text-red-600 dark:text-red-400">
          {(updateEdgeMutation.error ||
            deleteEdgeMutation.error ||
            createStreetEdgeMutation.error ||
            deleteStreetEdgeMutation.error ||
            createTrainEdgeMutation.error ||
            deleteTrainEdgeMutation.error)?.message}
        </p>
      )}

      {/* Modify button in version-diff mode */}
      {isModifyMode && (
        <div className="pt-2">
          <button
            onClick={handleModify}
            className="w-full px-3 py-1.5 text-sm bg-amber-600 text-white rounded-md hover:bg-amber-700"
          >
            Modify
          </button>
        </div>
      )}
    </div>
  );
};

export default EdgePropertyPanel;
