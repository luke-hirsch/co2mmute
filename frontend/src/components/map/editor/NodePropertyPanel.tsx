import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  EditorFact,
  EditorField,
  EditorNote,
  EditorPanel,
  editorControl,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import { useNodeTypes } from "@/lib/queries/map-graph";
import { useDeleteNode, useUpdateNode } from "@/lib/queries/map-editor";
import type { Node, NodeType } from "../../../types/mapTypes";

interface NodePropertyPanelProps {
  node: Node;
  mapId: string;
}

const NodePropertyPanel = ({ node, mapId }: NodePropertyPanelProps) => {
  const { data: allNodeTypes } = useNodeTypes();
  const updateMutation = useUpdateNode(mapId);
  const deleteMutation = useDeleteNode(mapId);

  const [name, setName] = useState(node.name || "");
  const [selectedTypeIds, setSelectedTypeIds] = useState<Set<number>>(
    new Set(node.node_type.map((t) => t.id))
  );

  // Sync when selected node changes
  useEffect(() => {
    setName(node.name || "");
    setSelectedTypeIds(new Set(node.node_type.map((t) => t.id)));
  }, [node.id, node.name, node.node_type]);

  const handleSave = () => {
    updateMutation.mutate({
      nodeId: node.id,
      name: name || undefined,
      node_type: [...selectedTypeIds],
    });
  };

  const handleDelete = () => {
    if (confirm(de.editor.node.removeConfirm)) {
      deleteMutation.mutate(node.id);
    }
  };

  const toggleType = (typeId: number) => {
    setSelectedTypeIds((prev) => {
      const next = new Set(prev);
      if (next.has(typeId)) {
        next.delete(typeId);
      } else {
        next.add(typeId);
      }
      return next;
    });
  };

  const hasChanges =
    name !== (node.name || "") ||
    selectedTypeIds.size !== node.node_type.length ||
    node.node_type.some((t) => !selectedTypeIds.has(t.id));

  return (
    <EditorPanel title={de.editor.node.title}>
      <EditorField label={de.editor.node.name}>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={de.editor.node.numbered(node.id)}
          className={editorControl}
        />
      </EditorField>

      <EditorFact label={de.editor.node.position}>
        <span className="font-mono">
          ({node.x_position.toFixed(2)}, {node.y_position.toFixed(2)})
        </span>
      </EditorFact>

      <EditorFact label={de.editor.node.types}>
        <div className="flex flex-wrap gap-1.5">
          {/* A type is on or off, so the button that sets it is filled or
              outlined — the same filled-vs-hollow the map marks use, and the
              reason `bg-indigo-600` had nothing to be. */}
          {(allNodeTypes ?? []).map((t: NodeType) => (
            <Button
              key={t.id}
              size="xs"
              variant={selectedTypeIds.has(t.id) ? "default" : "outline"}
              onClick={() => toggleType(t.id)}
            >
              {t.short} — {t.name}
            </Button>
          ))}
          {(!allNodeTypes || allNodeTypes.length === 0) && (
            <EditorNote>{de.editor.node.noTypes}</EditorNote>
          )}
        </div>
      </EditorFact>

      <div className="flex gap-2 pt-1">
        <Button
          size="sm"
          className="flex-1"
          onClick={handleSave}
          disabled={updateMutation.isPending || !hasChanges}
        >
          {updateMutation.isPending ? de.editor.saving : de.editor.save}
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
        >
          {de.editor.delete}
        </Button>
      </div>

      {updateMutation.isSuccess && <EditorNote>{de.editor.saved}</EditorNote>}
      {updateMutation.isError && (
        <EditorNote tone="attention">{updateMutation.error?.message}</EditorNote>
      )}
      {deleteMutation.isError && (
        <EditorNote tone="attention">{deleteMutation.error?.message}</EditorNote>
      )}
    </EditorPanel>
  );
};

export default NodePropertyPanel;
