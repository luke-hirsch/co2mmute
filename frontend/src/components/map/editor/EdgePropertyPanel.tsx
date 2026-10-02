import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EditorFact,
  EditorField,
  EditorNote,
  EditorPanel,
  editorControl,
  editorControlNarrow,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import type { Edge, Node } from "../../../types/mapTypes";
import {
  useUpdateEdge,
  useDeleteEdge,
  useCreateEdge,
  useCreateStreetEdge,
  useUpdateStreetEdge,
  useDeleteStreetEdge,
  useCreateTrainEdge,
  useDeleteTrainEdge,
} from "@/lib/queries/map-editor";

/**
 * One link's properties — the densest panel in the editor, and the one that held
 * forty off-palette classes.
 *
 * ### What S18 changed, and what it did not
 *
 * Presentation only. Every handler, every mutation and the reverse-edge
 * bookkeeping are byte-for-byte what they were: this panel writes to the map, so
 * it is the part of the sweep where nothing structural was allowed to move.
 *
 * What went:
 *
 * - `bg-indigo-100` / `bg-amber-100` on the direction badge, `bg-gray-100` on
 *   the street, `bg-red-100` on the railway and `bg-green-100` on a path — four
 *   hues for four facts, none of which is good or bad news. They are outline
 *   badges now, and what a link carries is read off the words.
 * - `border-dashed border-amber-400`, `border-dashed border-indigo-400`,
 *   `border-dashed border-gray-400`, `border-dashed border-red-400` — four
 *   dashed buttons meaning "add the thing that is not here yet". One outline
 *   button.
 * - `text-red-600` on the two small `x`es that take a street or a railway off
 *   the link. Those are destructive and they are the accent now, which is the
 *   colour the palette has for that.
 * - **`"Yes"` / `"No"`**, rendered for `biking` and `walking` in the read-only
 *   branch. `de.actions.yes` / `.no` have existed since S17 and the bus-lane row
 *   three lines below already used them; these two were missed because a
 *   one-word literal is invisible to `german.test.ts`.
 * - `"Saving..."`, for the same reason.
 */

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
  /** All edges in the graph, used to detect reverse edges */
  allEdges?: Edge[];
  /** All nodes in the graph, used to show node names for direction */
  allNodes?: Node[];
  /** Called after deleting an edge (e.g. to clear selection) */
  onEdgeDeleted?: () => void;
}

const EdgePropertyPanel = ({
  edge,
  mapId,
  versionId,
  editable = false,
  mode = "edit",
  onChange,
  onModifyDone,
  allEdges,
  allNodes,
  onEdgeDeleted,
}: EdgePropertyPanelProps) => {
  // Direct-edit mode (graph mode with mapId) vs onChange mode (version-diff)
  const directEdit = editable && !!mapId && mode === "edit";
  const isModifyMode = mode === "modify";
  // Modify mode and directEdit both use local state
  const useLocalState = directEdit || isModifyMode;

  const updateEdgeMutation = useUpdateEdge(mapId ?? "");
  const deleteEdgeMutation = useDeleteEdge(mapId ?? "");
  const createEdgeMutation = useCreateEdge(mapId ?? "");
  const createStreetEdgeMutation = useCreateStreetEdge(mapId ?? "");
  const updateStreetEdgeMutation = useUpdateStreetEdge(mapId ?? "");
  const deleteStreetEdgeMutation = useDeleteStreetEdge(mapId ?? "");
  const createTrainEdgeMutation = useCreateTrainEdge(mapId ?? "");
  const deleteTrainEdgeMutation = useDeleteTrainEdge(mapId ?? "");

  // Direction info
  const startNode = allNodes?.find((n) => n.id === edge.start_node);
  const endNode = allNodes?.find((n) => n.id === edge.end_node);
  const reverseEdge = allEdges?.find(
    (e) => e.start_node === edge.end_node && e.end_node === edge.start_node,
  );
  const isBidirectional = !!reverseEdge;
  const [confirmOneWayFor, setConfirmOneWayFor] = useState<number | null>(null);
  const confirmOneWay = confirmOneWayFor === edge.id;
  const setConfirmOneWay = (v: boolean) => setConfirmOneWayFor(v ? edge.id : null);

  const [edgeName, setEdgeName] = useState(edge.name ?? "");
  const [biking, setBiking] = useState(edge.biking ?? true);
  const [walking, setWalking] = useState(edge.walking ?? true);
  const [maxLanes, setMaxLanes] = useState(edge.max_lanes ?? 1);
  const [speedLimit, setSpeedLimit] = useState(edge.street_edge?.speed_limit ?? 50);
  const [lanes, setLanes] = useState(edge.street_edge?.lanes ?? 1);
  const [busLane, setBusLane] = useState(edge.street_edge?.dedicated_bus_lane ?? false);

  useEffect(() => {
    setEdgeName(edge.name ?? "");
    setBiking(edge.biking ?? true);
    setWalking(edge.walking ?? true);
    setMaxLanes(edge.max_lanes ?? 1);
    setSpeedLimit(edge.street_edge?.speed_limit ?? 50);
    setLanes(edge.street_edge?.lanes ?? 1);
    setBusLane(edge.street_edge?.dedicated_bus_lane ?? false);
  }, [edge.id, edge.name, edge.biking, edge.walking, edge.max_lanes, edge.street_edge]);

  const handleSave = () => {
    if (!mapId) return;
    updateEdgeMutation.mutate({
      edgeId: edge.id,
      biking,
      walking,
      max_lanes: maxLanes,
      name: edgeName,
    });
    if (edge.street_edge) {
      updateStreetEdgeMutation.mutate({
        streetEdgeId: edge.street_edge.id,
        speed_limit: speedLimit,
        lanes,
        dedicated_bus_lane: busLane,
      });
    }
    // Sync reverse edge properties
    if (reverseEdge) {
      updateEdgeMutation.mutate({
        edgeId: reverseEdge.id,
        biking,
        walking,
        max_lanes: maxLanes,
        name: edgeName,
      });
      if (reverseEdge.street_edge) {
        updateStreetEdgeMutation.mutate({
          streetEdgeId: reverseEdge.street_edge.id,
          speed_limit: speedLimit,
          lanes,
          dedicated_bus_lane: busLane,
        });
      }
    }
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
    const msg = reverseEdge
      ? de.editor.edge.removeBothConfirm
      : de.editor.deleteEdgeConfirm;
    if (confirm(msg)) {
      deleteEdgeMutation.mutate(edge.id);
      if (reverseEdge) {
        deleteEdgeMutation.mutate(reverseEdge.id);
      }
      onEdgeDeleted?.();
    }
  };

  const handleAddStreetEdge = () => {
    if (!mapId) return;
    const payload = {
      speed_limit: 50,
      lanes: 1,
      dedicated_bus_lane: false,
      map_versions: versionId ? [versionId] : [],
    };
    createStreetEdgeMutation.mutate({ edge: edge.id, ...payload });
    if (reverseEdge && !reverseEdge.street_edge) {
      createStreetEdgeMutation.mutate({ edge: reverseEdge.id, ...payload });
    }
  };

  const handleRemoveStreetEdge = () => {
    if (!mapId || !edge.street_edge) return;
    deleteStreetEdgeMutation.mutate(edge.street_edge.id);
    if (reverseEdge?.street_edge) {
      deleteStreetEdgeMutation.mutate(reverseEdge.street_edge.id);
    }
  };

  const handleAddTrainEdge = () => {
    if (!mapId) return;
    const payload = { map_versions: versionId ? [versionId] : [] };
    createTrainEdgeMutation.mutate({ edge: edge.id, ...payload });
    if (reverseEdge && !reverseEdge.train_edge) {
      createTrainEdgeMutation.mutate({ edge: reverseEdge.id, ...payload });
    }
  };

  const handleRemoveTrainEdge = () => {
    if (!mapId || !edge.train_edge) return;
    deleteTrainEdgeMutation.mutate(edge.train_edge.id);
    if (reverseEdge?.train_edge) {
      deleteTrainEdgeMutation.mutate(reverseEdge.train_edge.id);
    }
  };

  const isPending =
    updateEdgeMutation.isPending ||
    updateStreetEdgeMutation.isPending ||
    deleteEdgeMutation.isPending ||
    createEdgeMutation.isPending ||
    createStreetEdgeMutation.isPending ||
    deleteStreetEdgeMutation.isPending ||
    createTrainEdgeMutation.isPending ||
    deleteTrainEdgeMutation.isPending;

  const anyError =
    updateEdgeMutation.error ||
    updateStreetEdgeMutation.error ||
    deleteEdgeMutation.error ||
    createEdgeMutation.error ||
    createStreetEdgeMutation.error ||
    deleteStreetEdgeMutation.error ||
    createTrainEdgeMutation.error ||
    deleteTrainEdgeMutation.error;

  /** A boolean the reader may only look at. */
  const readOnlyFlag = (value: boolean | undefined) =>
    value ? de.actions.yes : de.actions.no;

  return (
    <EditorPanel
      title={isModifyMode ? de.editor.edge.modifyTitle : de.editor.edge.title}
    >
      {/* Direction info */}
      {allNodes && (
        <div>
          <p className="text-xs text-muted-foreground">
            {de.editor.edge.direction}
          </p>
          <p className="mt-0.5 text-sm font-medium">
            {startNode?.name || de.editor.node.numbered(edge.start_node)} →{" "}
            {endNode?.name || de.editor.node.numbered(edge.end_node)}
          </p>
          <div className="mt-1.5">
            <Badge variant="outline">
              {isBidirectional
                ? `↔ ${de.editor.edge.bidirectional}`
                : `→ ${de.editor.edge.oneWay}`}
            </Badge>
          </div>
          {directEdit && (
            <div className="mt-2">
              {isBidirectional && !confirmOneWay && (
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => setConfirmOneWay(true)}
                  disabled={isPending}
                >
                  {de.editor.edge.makeOneWay}
                </Button>
              )}
              {isBidirectional && confirmOneWay && reverseEdge && (
                <div className="space-y-1.5">
                  <p className="text-xs text-muted-foreground">
                    {de.editor.edge.whichDirection}
                  </p>
                  <div className="flex flex-col items-stretch gap-1">
                    <Button
                      size="xs"
                      className="justify-start"
                      disabled={isPending}
                      onClick={() => {
                        deleteEdgeMutation.mutate(reverseEdge.id, {
                          onSuccess: () => setConfirmOneWay(false),
                        });
                      }}
                    >
                      {de.editor.edge.keepDirection(
                        startNode?.name || de.editor.node.numbered(edge.start_node),
                        endNode?.name || de.editor.node.numbered(edge.end_node),
                      )}
                    </Button>
                    <Button
                      size="xs"
                      className="justify-start"
                      disabled={isPending}
                      onClick={() => {
                        deleteEdgeMutation.mutate(edge.id, {
                          onSuccess: () => {
                            setConfirmOneWay(false);
                            onEdgeDeleted?.();
                          },
                        });
                      }}
                    >
                      {de.editor.edge.keepDirection(
                        endNode?.name || de.editor.node.numbered(edge.end_node),
                        startNode?.name || de.editor.node.numbered(edge.start_node),
                      )}
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => setConfirmOneWay(false)}
                    >
                      {de.editor.cancel}
                    </Button>
                  </div>
                </div>
              )}
              {!isBidirectional && (
                <Button
                  size="xs"
                  variant="outline"
                  disabled={isPending}
                  onClick={() => {
                    createEdgeMutation.mutate(
                      {
                        start_node: edge.end_node,
                        end_node: edge.start_node,
                        biking: edge.biking,
                        walking: edge.walking,
                        max_lanes: edge.max_lanes,
                        map_versions: versionId ? [versionId] : [],
                      },
                      {
                        onSuccess: (newEdge: { id: number }) => {
                          const versions = versionId ? [versionId] : [];
                          if (edge.street_edge) {
                            createStreetEdgeMutation.mutate({
                              edge: newEdge.id,
                              speed_limit: edge.street_edge.speed_limit,
                              lanes: edge.street_edge.lanes,
                              dedicated_bus_lane: edge.street_edge.dedicated_bus_lane,
                              map_versions: versions,
                            });
                          }
                          if (edge.train_edge) {
                            createTrainEdgeMutation.mutate({
                              edge: newEdge.id,
                              map_versions: versions,
                            });
                          }
                        },
                      },
                    );
                  }}
                >
                  {de.editor.edge.makeBidirectional}
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      {directEdit ? (
        <EditorField label={de.editor.edge.name}>
          <input
            type="text"
            value={edgeName}
            onChange={(e) => setEdgeName(e.target.value)}
            placeholder={de.editor.edge.numbered(edge.id)}
            className={editorControl}
          />
        </EditorField>
      ) : (
        <EditorFact label={de.editor.edge.name}>
          <span className="font-medium">
            {edge.name || de.editor.edge.numbered(edge.id)}
          </span>
        </EditorFact>
      )}

      {/* What the corridor carries, and what can be added to it */}
      <EditorFact label={de.editor.edge.type}>
        <div className="flex flex-col items-start gap-1.5">
          {edge.street_edge ? (
            <div className="flex w-full items-center gap-1">
              <Badge variant="outline" className="flex-1">
                {de.editor.edge.streetSummary(
                  edge.street_edge.speed_limit,
                  edge.street_edge.lanes,
                )}
                {edge.street_edge.dedicated_bus_lane &&
                  ` ${de.editor.edge.busLaneSuffix}`}
              </Badge>
              {directEdit && (
                <Button
                  size="icon-xs"
                  variant="ghost"
                  className="text-destructive"
                  aria-label={de.editor.remove}
                  disabled={isPending}
                  onClick={handleRemoveStreetEdge}
                >
                  ×
                </Button>
              )}
            </div>
          ) : (
            directEdit && (
              <Button
                size="xs"
                variant="outline"
                disabled={isPending}
                onClick={handleAddStreetEdge}
              >
                {de.editor.edge.addStreet}
              </Button>
            )
          )}
          {edge.train_edge ? (
            <div className="flex w-full items-center gap-1">
              <Badge variant="outline" className="flex-1">
                {de.editor.edge.train}
              </Badge>
              {directEdit && (
                <Button
                  size="icon-xs"
                  variant="ghost"
                  className="text-destructive"
                  aria-label={de.editor.remove}
                  disabled={isPending}
                  onClick={handleRemoveTrainEdge}
                >
                  ×
                </Button>
              )}
            </div>
          ) : (
            directEdit && (
              <Button
                size="xs"
                variant="outline"
                disabled={isPending}
                onClick={handleAddTrainEdge}
              >
                {de.editor.edge.addTrain}
              </Button>
            )
          )}
          {!edge.street_edge && !edge.train_edge && !directEdit && (
            <Badge variant="outline">{de.editor.edge.path}</Badge>
          )}
        </div>
      </EditorFact>

      {/* Properties */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {de.editor.edge.biking}
          </span>
          {editable || isModifyMode ? (
            <input
              type="checkbox"
              checked={useLocalState ? biking : (edge.biking ?? true)}
              onChange={(e) => {
                if (useLocalState) setBiking(e.target.checked);
                else onChange?.({ biking: e.target.checked });
              }}
              className="size-4 rounded accent-primary"
            />
          ) : (
            <span className="text-xs">{readOnlyFlag(edge.biking)}</span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {de.editor.edge.walking}
          </span>
          {editable || isModifyMode ? (
            <input
              type="checkbox"
              checked={useLocalState ? walking : (edge.walking ?? true)}
              onChange={(e) => {
                if (useLocalState) setWalking(e.target.checked);
                else onChange?.({ walking: e.target.checked });
              }}
              className="size-4 rounded accent-primary"
            />
          ) : (
            <span className="text-xs">{readOnlyFlag(edge.walking)}</span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {de.editor.edge.maxLanes}
          </span>
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
              className={editorControlNarrow}
            />
          ) : (
            <span className="font-mono text-xs">{edge.max_lanes}</span>
          )}
        </div>

        {edge.street_edge && (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {de.editor.edge.speedLimit}
              </span>
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
                  className={editorControlNarrow}
                />
              ) : (
                <span className="font-mono text-xs">
                  {edge.street_edge.speed_limit} km/h
                </span>
              )}
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {de.editor.edge.lanes}
              </span>
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
                  className={editorControlNarrow}
                />
              ) : (
                <span className="font-mono text-xs">{edge.street_edge.lanes}</span>
              )}
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {de.editor.edge.busLane}
              </span>
              {editable || isModifyMode ? (
                <input
                  type="checkbox"
                  checked={useLocalState ? busLane : edge.street_edge.dedicated_bus_lane}
                  onChange={(e) => {
                    if (useLocalState) setBusLane(e.target.checked);
                    else onChange?.({ dedicated_bus_lane: e.target.checked });
                  }}
                  className="size-4 rounded accent-primary"
                />
              ) : (
                <span className="text-xs">
                  {readOnlyFlag(edge.street_edge.dedicated_bus_lane)}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {edge.distance_m != null && (
        <EditorFact label={de.editor.edge.distance}>
          <span className="font-mono">{edge.distance_m.toFixed(0)} m</span>
        </EditorFact>
      )}

      {/* Save / Delete in direct edit mode */}
      {directEdit && (
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            className="flex-1"
            onClick={handleSave}
            disabled={isPending}
          >
            {updateEdgeMutation.isPending ? de.editor.saving : de.editor.save}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={handleDelete}
            disabled={isPending}
          >
            {de.editor.delete}
          </Button>
        </div>
      )}
      {updateEdgeMutation.isSuccess && !updateStreetEdgeMutation.isPending && (
        <EditorNote>{de.editor.saved}</EditorNote>
      )}
      {anyError && (
        <EditorNote tone="attention">{anyError.message}</EditorNote>
      )}

      {/* Modify button in version-diff mode */}
      {isModifyMode && (
        <Button size="sm" className="w-full" onClick={handleModify}>
          {de.editor.modify}
        </Button>
      )}
    </EditorPanel>
  );
};

export default EdgePropertyPanel;
