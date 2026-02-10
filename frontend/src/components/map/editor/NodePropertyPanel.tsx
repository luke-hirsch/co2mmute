import type { Node } from "../../../types/mapTypes";

interface NodePropertyPanelProps {
  node: Node;
}

const NodePropertyPanel = ({ node }: NodePropertyPanelProps) => {
  return (
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">Node</h3>
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext">Name</p>
        <p className="font-semibold text-main dark:text-darktext">
          {node.name || `Node ${node.id}`}
        </p>
      </div>
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext">Position</p>
        <p className="text-sm text-main dark:text-darktext">
          ({node.x_position}, {node.y_position})
        </p>
      </div>
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext">Types</p>
        <div className="flex flex-wrap gap-1 mt-1">
          {node.node_type.map((t) => (
            <span
              key={t.id}
              className="inline-block bg-main dark:bg-darktext text-white dark:text-black text-xs px-2 py-0.5 rounded"
            >
              {t.short} — {t.name}
            </span>
          ))}
          {node.node_type.length === 0 && (
            <span className="text-xs text-muted dark:text-darkmutedtext">None</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default NodePropertyPanel;
