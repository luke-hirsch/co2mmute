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

interface EdgePropertyPanelProps {
  edge: Edge;
  mapId?: string;
  versionId?: number;
  editable?: boolean;
  onChange?: (changes: Partial<{
    biking: boolean;
    walking: boolean;
    max_lanes: number;
    speed_limit: number;
    lanes: number;
    dedicated_bus_lane: boolean;
  }>) => void;
}

const EdgePropertyPanel = ({
  edge,
  mapId,
  versionId,
  editable = false,
  onChange,
}: EdgePropertyPanelProps) => {
  // Direct-edit mode (graph mode with mapId) vs onChange mode (version-diff)
  const directEdit = editable && !!mapId;

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
      <h3 className="text-lg font-semibold text-main dark:text-darktext">Edge</h3>
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
          {editable ? (
            <input
              type="checkbox"
              checked={directEdit ? biking : (edge.biking ?? true)}
              onChange={(e) => {
                if (directEdit) setBiking(e.target.checked);
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
          {editable ? (
            <input
              type="checkbox"
              checked={directEdit ? walking : (edge.walking ?? true)}
              onChange={(e) => {
                if (directEdit) setWalking(e.target.checked);
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
          {editable ? (
            <input
              type="number"
              min={1}
              max={6}
              value={directEdit ? maxLanes : (edge.max_lanes ?? 2)}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (directEdit) setMaxLanes(v);
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
              {editable ? (
                <input
                  type="number"
                  min={5}
                  max={200}
                  step={5}
                  value={directEdit ? speedLimit : edge.street_edge.speed_limit}
                  onChange={(e) => {
                    const v = parseInt(e.target.value);
                    if (directEdit) setSpeedLimit(v);
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
              {editable ? (
                <input
                  type="number"
                  min={1}
                  max={6}
                  value={directEdit ? lanes : edge.street_edge.lanes}
                  onChange={(e) => {
                    const v = parseInt(e.target.value);
                    if (directEdit) setLanes(v);
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
              {editable ? (
                <input
                  type="checkbox"
                  checked={directEdit ? busLane : edge.street_edge.dedicated_bus_lane}
                  onChange={(e) => {
                    if (directEdit) setBusLane(e.target.checked);
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
    </div>
  );
};

export default EdgePropertyPanel;
