import { useState } from "react";
import type { GameMap } from "../../../types/mapTypes";
import { useUpdateMapSettings } from "../../../hooks/mapEditorHooks";

interface MapSettingsPanelProps {
  mapId: string;
  gameMap: GameMap;
}

interface SettingsValues {
  name: string;
  x_dim: number;
  y_dim: number;
  scale: number;
  max_player: number;
  walk_speed_kmh: number;
  bike_speed_kmh: number;
  default_car_speed_kmh: number;
}

const MapSettingsPanel = ({ mapId, gameMap }: MapSettingsPanelProps) => {
  const updateMutation = useUpdateMapSettings(mapId);

  const [values, setValues] = useState<SettingsValues>({
    name: gameMap.name,
    x_dim: gameMap.x_dim,
    y_dim: gameMap.y_dim,
    scale: gameMap.scale,
    max_player: gameMap.max_player,
    walk_speed_kmh: gameMap.walk_speed_kmh,
    bike_speed_kmh: gameMap.bike_speed_kmh,
    default_car_speed_kmh: gameMap.default_car_speed_kmh,
  });

  const handleSave = () => {
    updateMutation.mutate(values);
  };

  const numberFields: {
    field: keyof Omit<SettingsValues, "name">;
    label: string;
    min: number;
    max: number;
    step: number;
  }[] = [
    { field: "x_dim", label: "Width (grid units)", min: 1, max: 100, step: 1 },
    { field: "y_dim", label: "Height (grid units)", min: 1, max: 100, step: 1 },
    { field: "scale", label: "Scale (m per unit)", min: 1, max: 10000, step: 1 },
    { field: "max_player", label: "Max Players", min: 1, max: 20, step: 1 },
    { field: "walk_speed_kmh", label: "Walk Speed (km/h)", min: 1, max: 15, step: 1 },
    { field: "bike_speed_kmh", label: "Bike Speed (km/h)", min: 5, max: 50, step: 1 },
    { field: "default_car_speed_kmh", label: "Default Car Speed (km/h)", min: 10, max: 200, step: 5 },
  ];

  return (
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">
        Map Settings
      </h3>

      <div>
        <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
          Name
        </label>
        <input
          type="text"
          value={values.name}
          onChange={(e) => setValues((prev) => ({ ...prev, name: e.target.value }))}
          className="w-full px-2 py-1.5 text-sm rounded-md border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
        />
      </div>

      {numberFields.map(({ field, label, min, max, step }) => (
        <div key={field}>
          <label className="flex justify-between text-xs text-muted dark:text-darkmutedtext mb-1">
            <span>{label}</span>
            <span>{values[field]}</span>
          </label>
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={values[field]}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [field]: Number(e.target.value) }))
            }
            className="w-full px-2 py-1.5 text-sm rounded-md border border-subtle dark:border-darksubtle bg-body dark:bg-darkbody text-main dark:text-darktext"
          />
        </div>
      ))}

      <div className="pt-2">
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="w-full px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {updateMutation.isPending ? "Saving..." : "Save Settings"}
        </button>
      </div>
      {updateMutation.isSuccess && (
        <p className="text-xs text-green-600 dark:text-green-400">Saved</p>
      )}
    </div>
  );
};

export default MapSettingsPanel;
