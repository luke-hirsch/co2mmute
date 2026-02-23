import type { Dispatch } from "react";
import type { MapVersion, Edge } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type {
  EdgeChange,
  PTLineChange,
  EditorAction,
  VersionMetadata,
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
}: VersionDiffPanelProps) => {
  const createMutation = useCreateVersionFromDiff(mapId);

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

  const handleCreateVersion = () => {
    if (!sourceVersionId || !versionMetadata.versionName.trim() || !versionMetadata.pollText.trim()) return;

    createMutation.mutate(
      {
        source_version_id: sourceVersionId,
        version_name: versionMetadata.versionName.trim(),
        description: versionMetadata.description || undefined,
        poll_text: versionMetadata.pollText,
        revert_poll_text: versionMetadata.revertPollText || undefined,
        edge_changes: edgeChanges,
        pt_line_changes: ptLineChanges,
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
          dispatch({ type: "MARK_CLEAN" });
          dispatch({ type: "CLEAR_SELECTION" });
          dispatch({ type: "SET_VERSION_DIFF_STEP", step: 1 });
        },
      }
    );
  };

  const canProceed =
    versionMetadata.versionName.trim().length > 0 &&
    versionMetadata.pollText.trim().length > 0;

  const totalChanges = edgeChanges.length + ptLineChanges.length;

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
            Define the version that players can vote for. Fill in the details below, then proceed to modify edges.
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

  // ─── Step 2: Modify Edges ──────────────────────────────────────────
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

      {/* Instructions */}
      {!selectedEdge && totalChanges === 0 && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
          <p className="text-sm text-muted dark:text-darkmutedtext">
            Click edges on the map to select and modify their properties.
          </p>
        </div>
      )}

      {/* Selected edge editing */}
      {selectedEdge && (
        <EdgePropertyPanel
          edge={selectedEdge}
          mode="modify"
          onChange={handleEdgeChange}
          onModifyDone={() => dispatch({ type: "CLEAR_SELECTION" })}
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

      {/* Create Version button */}
      <div className="space-y-2">
        <button
          onClick={handleCreateVersion}
          disabled={createMutation.isPending || totalChanges === 0}
          className="w-full px-3 py-1.5 text-sm bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:opacity-50"
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
