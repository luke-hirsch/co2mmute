import { useState, useEffect, useCallback } from "react";

import { Button } from "@/components/ui/button";
import {
  EditorField,
  EditorNote,
  EditorPanel,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
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
      <EditorPanel title={de.editor.image.title}>
        <p className="text-sm text-muted-foreground">{de.editor.image.none}</p>
      </EditorPanel>
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
    <EditorPanel title={de.editor.image.title}>
      <EditorNote>{de.editor.image.hint}</EditorNote>

      {sliders.map(({ field, label, min, max, step }) => (
        <EditorField
          key={field}
          label={label}
          value={values[field].toFixed(field === "image_scale" ? 2 : 1)}
        >
          {/* The track is `accent-primary` rather than a grey of its own: a
              range input paints its own filled half, and `bg-gray-300` fought
              the theme instead of following it. */}
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={values[field]}
            onChange={(e) => handleChange(field, parseFloat(e.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-primary"
          />
        </EditorField>
      ))}

      <div className="flex gap-2 pt-1">
        <Button
          size="sm"
          className="flex-1"
          onClick={handleSave}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? de.editor.saving : de.editor.save}
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
        >
          {de.editor.image.remove}
        </Button>
      </div>
      {updateMutation.isSuccess && <EditorNote>{de.editor.saved}</EditorNote>}
    </EditorPanel>
  );
};

export default ImageTransformPanel;
