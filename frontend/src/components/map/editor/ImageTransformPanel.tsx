import { de } from "@/lib/de";
import { useState, useEffect, useCallback } from "react";
import type { GameMap } from "../../../types/mapTypes";
import type { ExtendedMapGraph } from "../../../types/routeTypes";
import type { ImageTransformValues } from "../../../types/editorTypes";
import {
  useUpdateImageTransform,
  useDeleteBackgroundImage,
} from "@/lib/queries/map-editor";

interface ImageTransformPanelProps {
  mapId: string;
  gameMap: GameMap;
  mapGraph: ExtendedMapGraph | undefined;
}

const ImageTransformPanel = ({ mapId, gameMap, mapGraph }: ImageTransformPanelProps) => {
  const updateMutation = useUpdateImageTransform(mapId);
  const deleteMutation = useDeleteBackgroundImage(mapId);

  const [values, setValues] = useState<ImageTransformValues>({
    image_offset_x: gameMap.image_offset_x ?? 0,
    image_offset_y: gameMap.image_offset_y ?? 0,
    image_scale: gameMap.image_scale ?? 1,
    image_crop_top: gameMap.image_crop_top ?? 0,
    image_crop_right: gameMap.image_crop_right ?? 0,
    image_crop_bottom: gameMap.image_crop_bottom ?? 0,
    image_crop_left: gameMap.image_crop_left ?? 0,
  });

  // Sync when gameMap updates (e.g. after save)
  useEffect(() => {
    setValues({
      image_offset_x: gameMap.image_offset_x ?? 0,
      image_offset_y: gameMap.image_offset_y ?? 0,
      image_scale: gameMap.image_scale ?? 1,
      image_crop_top: gameMap.image_crop_top ?? 0,
      image_crop_right: gameMap.image_crop_right ?? 0,
      image_crop_bottom: gameMap.image_crop_bottom ?? 0,
      image_crop_left: gameMap.image_crop_left ?? 0,
    });
  }, [gameMap]);

  const handleChange = useCallback(
    (field: keyof ImageTransformValues, value: number) => {
      setValues((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  const handleSave = () => {
    updateMutation.mutate(values);
  };

  const hasImage = !!gameMap.background_image_url || !!mapGraph?.background_image_url;

  if (!hasImage) {
    return (
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
        <h3 className="text-lg font-semibold text-main dark:text-darktext mb-2">
          {de.editor.image.title}
        </h3>
        <p className="text-sm text-mutedtext dark:text-darkmutedtext">
          {de.editor.image.none}
        </p>
      </div>
    );
  }

  const sliders: {
    field: keyof ImageTransformValues;
    label: string;
    min: number;
    max: number;
    step: number;
  }[] = [
    { field: "image_offset_x", label: de.editor.image.offsetX, min: -20, max: 20, step: 0.1 },
    { field: "image_offset_y", label: de.editor.image.offsetY, min: -20, max: 20, step: 0.1 },
    { field: "image_scale", label: de.editor.image.scale, min: 0.1, max: 5, step: 0.01 },
    { field: "image_crop_top", label: de.editor.image.cropTop, min: 0, max: 50, step: 0.5 },
    { field: "image_crop_right", label: de.editor.image.cropRight, min: 0, max: 50, step: 0.5 },
    { field: "image_crop_bottom", label: de.editor.image.cropBottom, min: 0, max: 50, step: 0.5 },
    { field: "image_crop_left", label: de.editor.image.cropLeft, min: 0, max: 50, step: 0.5 },
  ];

  return (
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">
        {de.editor.image.title}
      </h3>
      <p className="text-xs text-mutedtext dark:text-darkmutedtext">
        {de.editor.image.hint}
      </p>

      {sliders.map(({ field, label, min, max, step }) => (
        <div key={field}>
          <label className="flex justify-between text-xs text-mutedtext dark:text-darkmutedtext mb-1">
            <span>{label}</span>
            <span>{values[field].toFixed(field === "image_scale" ? 2 : 1)}</span>
          </label>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={values[field]}
            onChange={(e) => handleChange(field, parseFloat(e.target.value))}
            className="w-full h-1.5 bg-gray-300 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      ))}

      <div className="flex gap-2 pt-2">
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="flex-1 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {updateMutation.isPending ? de.editor.saving : de.editor.save}
        </button>
        <button
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
          className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
        >
          {de.editor.image.remove}
        </button>
      </div>
      {updateMutation.isSuccess && (
        <p className="text-xs text-mutedtext dark:text-darkmutedtext">{de.editor.saved}</p>
      )}
    </div>
  );
};

export default ImageTransformPanel;
