import { useState, type Dispatch } from "react";
import type { MapVersion, Edge } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type {
  EdgeChange,
  PTLineChange,
  EditorAction,
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
}: VersionDiffPanelProps) => {
  const createMutation = useCreateVersionFromDiff(mapId);

  const [versionName, setVersionName] = useState("");
  const [description, setDescription] = useState("");
  const [pollText, setPollText] = useState("");
  const [revertPollText, setRevertPollText] = useState("");

  const sourceVersionId = selectedVersionId ?? mapGraph?.version_id;

  const handleEdgeChange = (changes: Partial<EdgeChange>) => {
    if (!selectedEdge) return;
    const existing = edgeChanges.find((c) => c.edge_id === selectedEdge.id);
    if (existing) {
      setEdgeChanges(
        edgeChanges.map((c) =>
          c.edge_id === selectedEdge.id ? { ...c, ...changes } : c
        )
      );
    } else {
      setEdgeChanges([
        ...edgeChanges,
        { edge_id: selectedEdge.id, ...changes },
      ]);
    }
    dispatch({ type: "MARK_DIRTY" });
  };

  const removeEdgeChange = (edgeId: number) => {
    setEdgeChanges(edgeChanges.filter((c) => c.edge_id !== edgeId));
    dispatch({ type: "DESELECT_EDGE", edgeId });
  };

  const handleSave = () => {
    if (!sourceVersionId || !versionName.trim()) return;

    createMutation.mutate(
      {
        source_version_id: sourceVersionId,
        version_name: versionName.trim(),
        description: description || undefined,
        poll_text: pollText || undefined,
        revert_poll_text: revertPollText || undefined,
        edge_changes: edgeChanges,
        pt_line_changes: ptLineChanges,
      },
      {
        onSuccess: () => {
          setVersionName("");
          setDescription("");
          setPollText("");
          setRevertPollText("");
          setEdgeChanges([]);
          setPtLineChanges([]);
          dispatch({ type: "MARK_CLEAN" });
          dispatch({ type: "CLEAR_SELECTION" });
        },
      }
    );
  };

  const totalChanges = edgeChanges.length + ptLineChanges.length;

  return (
    <div className="space-y-4">
      {/* Source version selector */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
        <h3 className="text-lg font-semibold text-main dark:text-darktext">
          Create Version from Diff
        </h3>

        <div>
          <label className="text-xs text-muted dark:text-darkmutedtext">
            Source Version
          </label>
          <select
            value={selectedVersionId ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              onVersionChange(val ? Number(val) : undefined);
              // Clear changes when switching source
              setEdgeChanges([]);
              setPtLineChanges([]);
              dispatch({ type: "CLEAR_SELECTION" });
              dispatch({ type: "MARK_CLEAN" });
            }}
            className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
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

        <p className="text-xs text-muted dark:text-darkmutedtext">
          Click edges on the map to select them for modification.
        </p>
      </div>

      {/* Selected edge editing */}
      {selectedEdge && (
        <EdgePropertyPanel
          edge={selectedEdge}
          editable
          onChange={handleEdgeChange}
        />
      )}

      {/* Changeset summary */}
      {totalChanges > 0 && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-amber-300 dark:border-amber-700 space-y-3">
          <h3 className="text-lg font-semibold text-main dark:text-darktext">
            Changes ({totalChanges})
          </h3>

          {edgeChanges.length > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                Edge Changes
              </p>
              <div className="space-y-1">
                {edgeChanges.map((change) => {
                  const edge = mapGraph?.edges.find(
                    (e) => e.id === change.edge_id
                  );
                  const fields = Object.keys(change).filter(
                    (k) => k !== "edge_id"
                  );
                  return (
                    <div
                      key={change.edge_id}
                      className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                    >
                      <div>
                        <span className="text-sm font-medium text-main dark:text-darktext">
                          {edge?.name || `Edge ${change.edge_id}`}
                        </span>
                        <span className="text-xs text-muted dark:text-darkmutedtext ml-2">
                          {fields.join(", ")}
                        </span>
                      </div>
                      <button
                        onClick={() => removeEdgeChange(change.edge_id)}
                        className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                      >
                        Remove
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {ptLineChanges.length > 0 && (
            <div>
              <p className="text-xs text-muted dark:text-darkmutedtext mb-1">
                PT Line Changes
              </p>
              <div className="space-y-1">
                {ptLineChanges.map((change, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-body dark:bg-darkbody rounded p-2"
                  >
                    <div>
                      <span
                        className={`inline-block text-xs px-1.5 py-0.5 rounded mr-2 ${
                          change.action === "add"
                            ? "bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100"
                            : change.action === "remove"
                              ? "bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100"
                              : "bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100"
                        }`}
                      >
                        {change.action}
                      </span>
                      <span className="text-sm text-main dark:text-darktext">
                        {change.name || `${change.line_type} line`}
                      </span>
                    </div>
                    <button
                      onClick={() =>
                        setPtLineChanges(
                          ptLineChanges.filter((_, i) => i !== idx)
                        )
                      }
                      className="text-xs text-red-600 hover:text-red-800 dark:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* New version form */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
        <h3 className="text-lg font-semibold text-main dark:text-darktext">
          New Version Details
        </h3>

        <div>
          <label className="text-xs text-muted dark:text-darkmutedtext">
            Version Name *
          </label>
          <input
            type="text"
            value={versionName}
            onChange={(e) => setVersionName(e.target.value)}
            placeholder="e.g. Add bus lanes on Main St"
            className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
          />
        </div>

        <div>
          <label className="text-xs text-muted dark:text-darkmutedtext">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
          />
        </div>

        <div>
          <label className="text-xs text-muted dark:text-darkmutedtext">
            Poll Text
          </label>
          <input
            type="text"
            value={pollText}
            onChange={(e) => setPollText(e.target.value)}
            placeholder="e.g. Should we add bus lanes?"
            className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
          />
        </div>

        <div>
          <label className="text-xs text-muted dark:text-darkmutedtext">
            Revert Poll Text
          </label>
          <input
            type="text"
            value={revertPollText}
            onChange={(e) => setRevertPollText(e.target.value)}
            placeholder="e.g. Remove bus lanes?"
            className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
          />
        </div>

        <button
          onClick={handleSave}
          disabled={
            createMutation.isPending ||
            !versionName.trim() ||
            totalChanges === 0
          }
          className="w-full px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {createMutation.isPending
            ? "Creating..."
            : `Create Version (${totalChanges} change${totalChanges !== 1 ? "s" : ""})`}
        </button>

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
