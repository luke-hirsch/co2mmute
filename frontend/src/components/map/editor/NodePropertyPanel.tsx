import { de } from "@/lib/de";
import { useState, useEffect } from "react";
import type { Node, NodeType } from "../../../types/mapTypes";
import { useNodeTypes } from "@/lib/queries/map-graph";
import { useUpdateNode, useDeleteNode } from "@/lib/queries/map-editor";

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
    if (confirm("Delete this node and all connected edges?")) {
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
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">{de.editor.node.title}</h3>

      <div>
        <label className="text-xs text-mutedtext dark:text-darkmutedtext">{de.editor.node.name}</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={`Node ${node.id}`}
          className="w-full mt-1 px-2 py-1 text-sm rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
        />
      </div>

      <div>
        <p className="text-xs text-mutedtext dark:text-darkmutedtext">{de.editor.node.position}</p>
        <p className="text-sm text-main dark:text-darktext">
          ({node.x_position.toFixed(2)}, {node.y_position.toFixed(2)})
        </p>
      </div>

      <div>
        <p className="text-xs text-mutedtext dark:text-darkmutedtext mb-1">{de.editor.node.types}</p>
        <div className="flex flex-wrap gap-1">
          {(allNodeTypes ?? []).map((t: NodeType) => (
            <button
              key={t.id}
              onClick={() => toggleType(t.id)}
              className={`text-xs px-2 py-0.5 rounded transition-colors ${
                selectedTypeIds.has(t.id)
                  ? "bg-indigo-600 text-white"
                  : "bg-body dark:bg-darkbody text-mutedtext dark:text-darkmutedtext border border-subtle dark:border-darksubtle"
              }`}
            >
              {t.short} — {t.name}
            </button>
          ))}
          {(!allNodeTypes || allNodeTypes.length === 0) && (
            <span className="text-xs text-mutedtext dark:text-darkmutedtext">
              {de.editor.node.noTypes}
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-2 pt-2">
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending || !hasChanges}
          className="flex-1 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {updateMutation.isPending ? "Saving..." : de.editor.save}
        </button>
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
        >
          {de.editor.delete}
        </button>
      </div>
      {updateMutation.isSuccess && (
        <p className="text-xs text-green-600 dark:text-green-400">{de.editor.saved}</p>
      )}
      {updateMutation.isError && (
        <p className="text-xs text-red-600 dark:text-red-400">{updateMutation.error?.message}</p>
      )}
      {deleteMutation.isError && (
        <p className="text-xs text-red-600 dark:text-red-400">{deleteMutation.error?.message}</p>
      )}
    </div>
  );
};

export default NodePropertyPanel;
