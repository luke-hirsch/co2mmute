import { useRef } from "react";
import type { EditorMode, GraphTool } from "../../../types/editorTypes";
import type { GameMap } from "../../../types/mapTypes";
import { useUploadBackgroundImage } from "../../../hooks/mapEditorHooks";

interface EditorToolbarProps {
  mode: EditorMode;
  onModeChange: (mode: EditorMode) => void;
  mapId: string;
  gameMap: GameMap;
  graphTool: GraphTool;
  onGraphToolChange: (tool: GraphTool) => void;
  hasSelection: boolean;
  onDeleteSelected: () => void;
  ptLineCreating: "bus" | "train" | null;
  onStartPtLine: (type: "bus" | "train") => void;
  onCancelPtLine: () => void;
  versionDiffStep?: 1 | 2;
}

const modes: { key: EditorMode; label: string }[] = [
  { key: "settings", label: "Settings" },
  { key: "image", label: "Background Image" },
  { key: "graph", label: "Graph" },
  { key: "pt-lines", label: "PT Lines" },
  { key: "version-diff", label: "Versions" },
];

const graphTools: { key: GraphTool; label: string }[] = [
  { key: "select", label: "Select" },
  { key: "add-node", label: "+ Node" },
  { key: "add-edge", label: "+ Edge" },
];

const EditorToolbar = ({
  mode,
  onModeChange,
  mapId,
  gameMap,
  graphTool,
  onGraphToolChange,
  hasSelection,
  onDeleteSelected,
  ptLineCreating,
  onStartPtLine,
  onCancelPtLine,
  versionDiffStep,
}: EditorToolbarProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadBackgroundImage(mapId);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="relative z-30 flex flex-wrap items-center gap-2 bg-subtle dark:bg-darksubtle rounded-lg p-3 border border-subtle dark:border-darksubtle">
      {/* Mode tabs */}
      <div className="flex gap-1">
        {modes.map((m) => (
          <button
            key={m.key}
            onClick={() => onModeChange(m.key)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              mode === m.key
                ? "bg-indigo-600 text-white"
                : "text-muted dark:text-darkmutedtext hover:bg-body dark:hover:bg-darkbody"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="w-px h-6 bg-subtle dark:bg-darksubtle mx-2" />

      {/* Image mode actions */}
      {mode === "image" && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {uploadMutation.isPending ? "Uploading..." : "Upload Image"}
          </button>
          {gameMap.background_image_url && (
            <span className="text-xs text-green-600 dark:text-green-400">
              Image loaded
            </span>
          )}
        </>
      )}

      {/* Graph mode actions */}
      {mode === "graph" && (
        <>
          <div className="flex gap-1">
            {graphTools.map((t) => (
              <button
                key={t.key}
                onClick={() => onGraphToolChange(t.key)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  graphTool === t.key
                    ? "bg-emerald-600 text-white"
                    : "text-muted dark:text-darkmutedtext hover:bg-body dark:hover:bg-darkbody border border-subtle dark:border-darksubtle"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {hasSelection && (
            <button
              onClick={onDeleteSelected}
              className="px-2.5 py-1 text-xs bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              Delete
            </button>
          )}
          {graphTool === "add-node" && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              Click on canvas to place a node
            </span>
          )}
          {graphTool === "add-edge" && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              Click two nodes to connect them
            </span>
          )}
        </>
      )}

      {/* PT Lines mode actions */}
      {mode === "pt-lines" && !ptLineCreating && (
        <>
          <button
            onClick={() => onStartPtLine("bus")}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            + Bus Line
          </button>
          <button
            onClick={() => onStartPtLine("train")}
            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            + Train Line
          </button>
        </>
      )}

      {mode === "pt-lines" && ptLineCreating && (
        <>
          <span className="text-sm text-amber-600 dark:text-amber-400">
            Creating {ptLineCreating} line — click edges to build route
          </span>
          <button
            onClick={onCancelPtLine}
            className="px-3 py-1.5 text-sm bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            Cancel
          </button>
        </>
      )}

      {/* Version mode step indicator */}
      {mode === "version-diff" && versionDiffStep === 1 && (
        <span className="text-sm text-muted dark:text-darkmutedtext">
          Step 1: Define version details
        </span>
      )}
      {mode === "version-diff" && versionDiffStep === 2 && (
        <span className="text-sm text-amber-600 dark:text-amber-400">
          Step 2: Select edges to modify
        </span>
      )}
    </div>
  );
};

export default EditorToolbar;
