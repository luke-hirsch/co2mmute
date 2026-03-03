import type { Dispatch } from "react";
import type { GameMap, MapVersion } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type {
  EditorState,
  EditorAction,
  EdgeChange,
  PTLineChange,
  VersionMetadata,
} from "../../../types/editorTypes";
import ImageTransformPanel from "./ImageTransformPanel";
import EdgePropertyPanel from "./EdgePropertyPanel";
import NodePropertyPanel from "./NodePropertyPanel";
import PTLinePanel from "./PTLinePanel";
import VersionDiffPanel from "./VersionDiffPanel";

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
}: EditorSidebarProps) => {
  const selectedNode = state.selectedNodeId
    ? mapGraph?.nodes.find((n) => n.id === state.selectedNodeId)
    : null;

  const selectedEdge =
    state.selectedEdgeIds.size === 1
      ? mapGraph?.edges.find((e) => state.selectedEdgeIds.has(e.id))
      : null;

  return (
    <div className="sticky top-4 z-20 space-y-4">
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
        />
      )}
      {state.mode === "graph" && !selectedNode && !selectedEdge && (
        <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
          <p className="text-sm text-muted dark:text-darkmutedtext">
            Click a node or edge to view and edit its properties.
          </p>
        </div>
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
        />
      )}
    </div>
  );
};

export default EditorSidebar;
