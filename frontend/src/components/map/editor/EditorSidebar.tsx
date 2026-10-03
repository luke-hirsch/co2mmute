import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EditorPanel } from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import type { Dispatch } from "react";
import type { GameMap, MapVersion } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type {
  EditorState,
  EditorAction,
  EdgeChange,
  PTLineChange,
  VersionMetadata,
  PTLineDraftInDiff,
  VirtualNode,
  VirtualEdge,
} from "../../../types/editorTypes";
import MapSettingsPanel from "./MapSettingsPanel";
import ImageTransformPanel from "./ImageTransformPanel";
import EdgePropertyPanel from "./EdgePropertyPanel";
import NodePropertyPanel from "./NodePropertyPanel";
import PTLinePanel from "./PTLinePanel";
import VersionDiffPanel from "./VersionDiffPanel";
import VersionManagerPanel from "./VersionManagerPanel";

interface EditorSidebarProps {
  mapId: string;
  gameMap: GameMap;
  mapGraph: ExtendedMapGraph | undefined;
  state: EditorState;
  versions: MapVersion[] | undefined;
  selectedVersionId: number | undefined;
  onVersionChange: (versionId: number | undefined) => void;
  ptLineCreating: "bus" | "train" | null;
  ptLineEdgeIds: number[];
  setPtLineEdgeIds: (ids: number[]) => void;
  setPtLineCreating: (type: "bus" | "train" | null) => void;
  edgeChanges: EdgeChange[];
  setEdgeChanges: (changes: EdgeChange[]) => void;
  ptLineChanges: PTLineChange[];
  setPtLineChanges: (changes: PTLineChange[]) => void;
  dispatch: Dispatch<EditorAction>;
  versionMetadata: VersionMetadata;
  setVersionMetadata: (meta: VersionMetadata) => void;
  versionDiffEditingPtLine: PTLineDraftInDiff | null;
  setVersionDiffEditingPtLine: (draft: PTLineDraftInDiff | null) => void;
  newNodes: VirtualNode[];
  setNewNodes: (nodes: VirtualNode[]) => void;
  newEdges: VirtualEdge[];
  setNewEdges: (edges: VirtualEdge[]) => void;
  deletedNodeIds: Set<number>;
  setDeletedNodeIds: (ids: Set<number>) => void;
  deletedEdgeIds: Set<number>;
  setDeletedEdgeIds: (ids: Set<number>) => void;
  cascadeDeletedEdgeIds: Map<number, Set<number>>;
  setCascadeDeletedEdgeIds: (m: Map<number, Set<number>>) => void;
}

const EditorSidebar = ({
  mapId,
  gameMap,
  mapGraph,
  state,
  versions,
  selectedVersionId,
  onVersionChange,
  ptLineCreating,
  ptLineEdgeIds,
  setPtLineEdgeIds,
  setPtLineCreating,
  edgeChanges,
  setEdgeChanges,
  ptLineChanges,
  setPtLineChanges,
  dispatch,
  versionMetadata,
  setVersionMetadata,
  versionDiffEditingPtLine,
  setVersionDiffEditingPtLine,
  newNodes,
  setNewNodes,
  newEdges,
  setNewEdges,
  deletedNodeIds,
  setDeletedNodeIds,
  deletedEdgeIds,
  setDeletedEdgeIds,
  cascadeDeletedEdgeIds,
  setCascadeDeletedEdgeIds,
}: EditorSidebarProps) => {
  const [versionTab, setVersionTab] = useState<"create" | "manage">("create");

  const selectedNode = state.selectedNodeId
    ? mapGraph?.nodes.find((n) => n.id === state.selectedNodeId)
    : null;

  const selectedEdge =
    state.selectedEdgeIds.size === 1
      ? mapGraph?.edges.find((e) => state.selectedEdgeIds.has(e.id))
      : null;

  return (
    <div className="sticky top-4 z-20 space-y-4">
      {/* Settings mode */}
      {state.mode === "settings" && (
        <MapSettingsPanel key={gameMap.updated} mapId={mapId} gameMap={gameMap} />
      )}

      {/* Image mode */}
      {state.mode === "image" && (
        <ImageTransformPanel mapId={mapId} gameMap={gameMap} mapGraph={mapGraph} />
      )}

      {/* Graph mode */}
      {state.mode === "graph" && selectedNode && (
        <NodePropertyPanel node={selectedNode} mapId={mapId} />
      )}
      {state.mode === "graph" && selectedEdge && (
        <EdgePropertyPanel
          edge={selectedEdge}
          mapId={mapId}
          versionId={mapGraph?.version_id}
          editable
          allEdges={mapGraph?.edges}
          allNodes={mapGraph?.nodes}
          onEdgeDeleted={() => dispatch({ type: "CLEAR_SELECTION" })}
        />
      )}
      {state.mode === "graph" && !selectedNode && !selectedEdge && (
        <EditorPanel>
          <p className="text-sm text-muted-foreground">{de.editor.pickHint}</p>
        </EditorPanel>
      )}

      {/* PT Lines mode */}
      {state.mode === "pt-lines" && (
        <PTLinePanel
          mapId={mapId}
          mapGraph={mapGraph}
          ptLineCreating={ptLineCreating}
          ptLineEdgeIds={ptLineEdgeIds}
          setPtLineEdgeIds={setPtLineEdgeIds}
          setPtLineCreating={setPtLineCreating}
          selectedVersionId={selectedVersionId}
        />
      )}

      {/* Version Diff mode */}
      {state.mode === "version-diff" && (
        <>
          {/* Sub-tab bar.

              It reached for `bg-darkaccent` and `dark:hover:bg-darkbg`, and
              **neither is a token** — the tokens are `brandaccent` and
              `darkbody`. Tailwind emits nothing for a colour it cannot resolve,
              so in dark mode the selected tab had no background at all and the
              two tabs were indistinguishable. Two `Button`s now, filled versus
              ghost like every other on/off pair in the app; there is no class
              string left to misspell. */}
          <div className="grid grid-cols-2 gap-1 rounded-xl border bg-card p-1">
            <Button
              size="sm"
              variant={versionTab === "create" ? "default" : "ghost"}
              onClick={() => setVersionTab("create")}
            >
              {de.editor.create}
            </Button>
            <Button
              size="sm"
              variant={versionTab === "manage" ? "default" : "ghost"}
              onClick={() => setVersionTab("manage")}
            >
              {de.editor.manage}
            </Button>
          </div>

          {versionTab === "create" && (
            <VersionDiffPanel
              mapId={mapId}
              mapGraph={mapGraph}
              versions={versions}
              selectedVersionId={selectedVersionId}
              onVersionChange={onVersionChange}
              edgeChanges={edgeChanges}
              setEdgeChanges={setEdgeChanges}
              ptLineChanges={ptLineChanges}
              setPtLineChanges={setPtLineChanges}
              selectedEdge={selectedEdge ?? undefined}
              dispatch={dispatch}
              versionDiffStep={state.versionDiffStep}
              versionMetadata={versionMetadata}
              setVersionMetadata={setVersionMetadata}
              versionDiffEditingPtLine={versionDiffEditingPtLine}
              setVersionDiffEditingPtLine={setVersionDiffEditingPtLine}
              ptLineEdgeIds={ptLineEdgeIds}
              setPtLineEdgeIds={setPtLineEdgeIds}
              newNodes={newNodes}
              setNewNodes={setNewNodes}
              newEdges={newEdges}
              setNewEdges={setNewEdges}
              deletedNodeIds={deletedNodeIds}
              setDeletedNodeIds={setDeletedNodeIds}
              deletedEdgeIds={deletedEdgeIds}
              setDeletedEdgeIds={setDeletedEdgeIds}
              cascadeDeletedEdgeIds={cascadeDeletedEdgeIds}
              setCascadeDeletedEdgeIds={setCascadeDeletedEdgeIds}
            />
          )}

          {versionTab === "manage" && (
            <VersionManagerPanel
              mapId={mapId}
              selectedVersionId={selectedVersionId}
              onVersionChange={onVersionChange}
            />
          )}
        </>
      )}
    </div>
  );
};

export default EditorSidebar;
