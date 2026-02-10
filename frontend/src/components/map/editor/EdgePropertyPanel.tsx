import type { Edge } from "../../../types/mapTypes";

interface EdgePropertyPanelProps {
  edge: Edge;
  editable?: boolean;
  onChange?: (changes: Partial<{
    biking: boolean;
    walking: boolean;
    max_lanes: number;
    speed_limit: number;
    lanes: number;
    dedicated_bus_lane: boolean;
  }>) => void;
}

const EdgePropertyPanel = ({ edge, editable = false, onChange }: EdgePropertyPanelProps) => {
  return (
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">Edge</h3>
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext">Name</p>
        <p className="font-semibold text-main dark:text-darktext">
          {edge.name || `Edge ${edge.id}`}
        </p>
      </div>

      {/* Edge type badges */}
      <div>
        <p className="text-xs text-muted dark:text-darkmutedtext mb-1">Type</p>
        <div className="flex flex-col gap-1">
          {edge.street_edge && (
            <span className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100 px-2 py-1 rounded">
              Street ({edge.street_edge.speed_limit} km/h, {edge.street_edge.lanes} lane
              {edge.street_edge.lanes !== 1 ? "s" : ""})
              {edge.street_edge.dedicated_bus_lane && " + Bus Lane"}
            </span>
          )}
          {edge.train_edge && (
            <span className="text-xs bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 px-2 py-1 rounded">
              Train
            </span>
          )}
          {!edge.street_edge && !edge.train_edge && (
            <span className="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 px-2 py-1 rounded">
              Path
            </span>
          )}
        </div>
      </div>

      {/* Properties */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted dark:text-darkmutedtext">Biking</span>
          {editable ? (
            <input
              type="checkbox"
              checked={edge.biking ?? true}
              onChange={(e) => onChange?.({ biking: e.target.checked })}
              className="rounded"
            />
          ) : (
            <span className="text-xs text-main dark:text-darktext">
              {edge.biking ? "Yes" : "No"}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted dark:text-darkmutedtext">Walking</span>
          {editable ? (
            <input
              type="checkbox"
              checked={edge.walking ?? true}
              onChange={(e) => onChange?.({ walking: e.target.checked })}
              className="rounded"
            />
          ) : (
            <span className="text-xs text-main dark:text-darktext">
              {edge.walking ? "Yes" : "No"}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted dark:text-darkmutedtext">Max Lanes</span>
          {editable ? (
            <input
              type="number"
              min={1}
              max={6}
              value={edge.max_lanes ?? 2}
              onChange={(e) => onChange?.({ max_lanes: parseInt(e.target.value) })}
              className="w-16 text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
            />
          ) : (
            <span className="text-xs text-main dark:text-darktext">{edge.max_lanes}</span>
          )}
        </div>

        {edge.street_edge && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">Speed Limit</span>
              {editable ? (
                <input
                  type="number"
                  min={5}
                  max={200}
                  step={5}
                  value={edge.street_edge.speed_limit}
                  onChange={(e) => onChange?.({ speed_limit: parseInt(e.target.value) })}
                  className="w-16 text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
                />
              ) : (
                <span className="text-xs text-main dark:text-darktext">
                  {edge.street_edge.speed_limit} km/h
                </span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">Lanes</span>
              {editable ? (
                <input
                  type="number"
                  min={1}
                  max={6}
                  value={edge.street_edge.lanes}
                  onChange={(e) => onChange?.({ lanes: parseInt(e.target.value) })}
                  className="w-16 text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
                />
              ) : (
                <span className="text-xs text-main dark:text-darktext">
                  {edge.street_edge.lanes}
                </span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">Bus Lane</span>
              {editable ? (
                <input
                  type="checkbox"
                  checked={edge.street_edge.dedicated_bus_lane}
                  onChange={(e) => onChange?.({ dedicated_bus_lane: e.target.checked })}
                  className="rounded"
                />
              ) : (
                <span className="text-xs text-main dark:text-darktext">
                  {edge.street_edge.dedicated_bus_lane ? "Yes" : "No"}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {edge.distance_m != null && (
        <div>
          <p className="text-xs text-muted dark:text-darkmutedtext">Distance</p>
          <p className="text-sm text-main dark:text-darktext">
            {edge.distance_m.toFixed(0)} m
          </p>
        </div>
      )}
    </div>
  );
};

export default EdgePropertyPanel;
