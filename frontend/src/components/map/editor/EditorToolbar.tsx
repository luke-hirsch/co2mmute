import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import type { EditorMode, GraphTool } from "../../../types/editorTypes";
import type { GameMap } from "../../../types/mapTypes";
import { useUploadBackgroundImage } from "@/lib/queries/map-editor";

/**
 * The bar above the canvas: which mode, which tool, and what to do next.
 *
 * ### What S18 changed
 *
 * It had five colours doing four jobs. The selected mode tab was
 * `bg-indigo-600`; the selected *tool* was `bg-emerald-600`, except the delete
 * tool, which was `bg-red-600`; "+ Buslinie" was `bg-blue-600` and "+ Bahnlinie"
 * `bg-red-600`, which made a train look like a deletion; every hint was
 * `text-amber-600`; and "Bild geladen." was `text-green-600`.
 *
 * Now: **selection is filled versus outlined**, which is the language the rest
 * of the app uses for on-versus-off and costs no colour, and a hint is the accent
 * only when the editor is *waiting on a click* — which is what those hints
 * actually are. `Auswählen` and the version step counter are not waiting on
 * anything, so they stay muted.
 *
 * Bus and Bahn get the same button. They are one line in this palette ("Bus &
 * Bahn"), the labels already say which, and colouring the train red was the one
 * that mattered: red is the delete tool's colour, on the same bar.
 */

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
  versionDiffEditingPtLine?: boolean;
  bidirectional: boolean;
  onBidirectionalChange: (value: boolean) => void;
  /** A node or an edge drawn on the canvas is still on its way (F10). */
  saving?: boolean;
}

const modes: { key: EditorMode; label: string }[] = [
  { key: "settings", label: de.editor.tabs.settings },
  { key: "image", label: de.editor.tabs.image },
  { key: "graph", label: de.editor.tabs.graph },
  { key: "pt-lines", label: de.editor.tabs.ptLines },
  { key: "version-diff", label: de.editor.tabs.versions },
];

const graphTools: { key: GraphTool; label: string }[] = [
  { key: "select", label: de.editor.tools.select },
  { key: "add-node", label: `+ ${de.editor.tools.addNode}` },
  { key: "add-edge", label: `+ ${de.editor.tools.addEdge}` },
  { key: "delete", label: de.editor.tools.delete },
];

/**
 * A line of small print on the bar.
 *
 * `waiting` means the editor cannot do anything until you click on the canvas,
 * which is the one thing on this bar that has to be read. Everything else is
 * context.
 */
function Hint({
  waiting = false,
  children,
}: {
  waiting?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "text-xs",
        waiting ? "font-medium text-destructive" : "text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}

/** A tool button: filled while it is the active tool, outlined otherwise. */
function Tool({
  active,
  destructive = false,
  onClick,
  children,
}: {
  active: boolean;
  destructive?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      size="xs"
      variant={active ? (destructive ? "destructive" : "default") : "outline"}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

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
  versionDiffEditingPtLine,
  bidirectional,
  onBidirectionalChange,
  saving = false,
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

  /** The one-way / both-ways toggle, on the two tools that draw an edge. */
  const directionToggle = (
    <Button
      size="xs"
      variant={bidirectional ? "default" : "outline"}
      onClick={() => onBidirectionalChange(!bidirectional)}
      title={
        bidirectional
          ? de.editor.tools.bidirectionalHint
          : de.editor.tools.oneWayHint
      }
    >
      {bidirectional
        ? `↔ ${de.editor.tools.bidirectional}`
        : `→ ${de.editor.tools.oneWay}`}
    </Button>
  );

  return (
    <div className="relative z-30 flex flex-wrap items-center gap-2 rounded-xl border bg-card p-3">
      {/* Mode tabs */}
      {/* wrap: the five German tab labels are 465px wide, which is more than a
          phone has. The editor is a desktop tool, but a row that runs off the
          screen is a bug wherever it happens. */}
      <div className="flex flex-wrap gap-1">
        {modes.map((m) => (
          <Button
            key={m.key}
            size="sm"
            variant={mode === m.key ? "default" : "ghost"}
            onClick={() => onModeChange(m.key)}
          >
            {m.label}
          </Button>
        ))}
      </div>

      <div className="mx-2 h-6 w-px bg-border" />

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
          <Button
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending
              ? de.editor.image.uploading
              : de.editor.image.upload}
          </Button>
          {gameMap.background_image_url && (
            <Hint>{de.editor.imageLoaded}</Hint>
          )}
        </>
      )}

      {/* Graph mode actions */}
      {mode === "graph" && (
        <>
          <div className="flex gap-1">
            {graphTools
              .filter((t) => t.key !== "delete")
              .map((t) => (
                <Tool
                  key={t.key}
                  active={graphTool === t.key}
                  onClick={() => onGraphToolChange(t.key)}
                >
                  {t.label}
                </Tool>
              ))}
          </div>
          {hasSelection && (
            <Button size="xs" variant="destructive" onClick={onDeleteSelected}>
              {de.editor.delete}
            </Button>
          )}
          {saving ? (
            <Hint>{de.editor.saving}</Hint>
          ) : (
            <>
              {graphTool === "add-node" && (
                <Hint waiting>{de.editor.tools.addNodeHint}</Hint>
              )}
              {graphTool === "add-edge" && (
                <Hint waiting>{de.editor.tools.addEdgeHint}</Hint>
              )}
            </>
          )}
          {graphTool === "add-edge" && directionToggle}
        </>
      )}

      {/* PT Lines mode actions */}
      {mode === "pt-lines" && !ptLineCreating && (
        <>
          <Button size="sm" onClick={() => onStartPtLine("bus")}>
            {de.editor.ptLine.addBus}
          </Button>
          <Button size="sm" onClick={() => onStartPtLine("train")}>
            {de.editor.ptLine.addTrain}
          </Button>
        </>
      )}

      {mode === "pt-lines" && ptLineCreating && (
        <>
          <Hint waiting>{de.editor.ptLine.creatingHint}</Hint>
          <Button size="sm" variant="outline" onClick={onCancelPtLine}>
            {de.editor.cancel}
          </Button>
        </>
      )}

      {/* Version mode step indicator */}
      {mode === "version-diff" && versionDiffStep === 1 && (
        <Hint>{de.editor.versionStep1}</Hint>
      )}

      {/* Version-diff Step 2: show graph editing tools */}
      {mode === "version-diff" && versionDiffStep === 2 && (
        <>
          <div className="flex gap-1">
            {graphTools.map((t) => (
              <Tool
                key={t.key}
                active={graphTool === t.key}
                destructive={t.key === "delete"}
                onClick={() => onGraphToolChange(t.key)}
              >
                {t.label}
              </Tool>
            ))}
          </div>
          {versionDiffEditingPtLine && (
            <Hint waiting>{de.editor.tools.editingPtLine}</Hint>
          )}
          {!versionDiffEditingPtLine && graphTool === "select" && (
            <Hint>{de.editor.tools.selectHint}</Hint>
          )}
          {!versionDiffEditingPtLine && graphTool === "add-node" && (
            <Hint waiting>{de.editor.tools.proposeNodeHint}</Hint>
          )}
          {!versionDiffEditingPtLine && graphTool === "add-edge" && (
            <>
              <Hint waiting>{de.editor.tools.proposeEdgeHint}</Hint>
              {directionToggle}
            </>
          )}
          {!versionDiffEditingPtLine && graphTool === "delete" && (
            <Hint waiting>{de.editor.tools.deleteHint}</Hint>
          )}
        </>
      )}
    </div>
  );
};

export default EditorToolbar;
