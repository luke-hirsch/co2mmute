import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  EditorField,
  EditorNote,
  EditorPanel,
  editorControl,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import type { GameMap } from "../../../types/mapTypes";
import { useUpdateMapSettings } from "@/lib/queries/map-editor";

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
    { field: "x_dim", label: de.editor.settings.xDim, min: 1, max: 100, step: 1 },
    { field: "y_dim", label: de.editor.settings.yDim, min: 1, max: 100, step: 1 },
    { field: "scale", label: de.editor.settings.scale, min: 1, max: 10000, step: 1 },
    {
      field: "max_player",
      label: de.editor.settings.maxPlayer,
      min: 1,
      max: 20,
      step: 1,
    },
    {
      field: "walk_speed_kmh",
      label: de.editor.settings.walkSpeed,
      min: 1,
      max: 15,
      step: 1,
    },
    {
      field: "bike_speed_kmh",
      label: de.editor.settings.bikeSpeed,
      min: 5,
      max: 50,
      step: 1,
    },
    {
      field: "default_car_speed_kmh",
      label: de.editor.settings.carSpeed,
      min: 10,
      max: 200,
      step: 5,
    },
  ];

  return (
    <EditorPanel title={de.editor.settings.title}>
      <EditorField label={de.editor.settings.name}>
        <input
          type="text"
          value={values.name}
          onChange={(e) => setValues((prev) => ({ ...prev, name: e.target.value }))}
          className={editorControl}
        />
      </EditorField>

      {numberFields.map(({ field, label, min, max, step }) => (
        <EditorField key={field} label={label} value={values[field]}>
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={values[field]}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [field]: Number(e.target.value) }))
            }
            className={editorControl}
          />
        </EditorField>
      ))}

      <Button
        size="sm"
        className="w-full"
        onClick={handleSave}
        disabled={updateMutation.isPending}
      >
        {/* Was `"Saving..."`, live, in a German-only SPA. A one-word literal is
            skipped by `german.test.ts` on purpose, so five of these survived
            S17 across the editor's panels. */}
        {updateMutation.isPending ? de.editor.saving : de.editor.saveSettings}
      </Button>
      {updateMutation.isSuccess && <EditorNote>{de.editor.saved}</EditorNote>}
      {updateMutation.isError && (
        <EditorNote tone="attention">
          {updateMutation.error?.message ?? de.editor.saveFailed}
        </EditorNote>
      )}
    </EditorPanel>
  );
};

export default MapSettingsPanel;
