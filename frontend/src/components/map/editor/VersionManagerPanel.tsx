import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EditorField,
  EditorNote,
  EditorPanel,
  editorControl,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import {
  useGenerateCombinations,
  useMapVersions,
  useUpdateMapVersion,
} from "@/lib/queries/map-graph";
import { API_BASE_URL } from "../../../config";
import type { MapVersion } from "../../../types/mapTypes";

/**
 * The versions of a map, and the ballot between them.
 *
 * Presentation only, as everywhere in S18 — the `FormData` this panel PATCHes is
 * what wires `compatible_versions` up, and `compatible_versions` **is the vote**:
 * `vote_options()` walks that M2M from the active version. So the checkboxes and
 * the save are untouched; what changed is that they are no longer indigo.
 *
 * Four English strings were here too: `"Saving..."`, `"Generating..."`,
 * `Generate combinations (n selected)` and `Created n combination version(s)`,
 * plus an `alt="change preview"` on the image. Two were invisible to
 * `german.test.ts` for being one word and the rest carried none of its giveaway
 * words — which is why a panel a researcher uses every time they draw a version
 * was still half English after S17.
 */

interface VersionManagerPanelProps {
  mapId: string;
}

interface EditState {
  name: string;
  description: string;
  poll_text: string;
  revert_poll_text: string;
  compatible_versions: number[];
  newImage: File | null;
}

function VersionEditor({
  version,
  allVersions,
  mapId,
  onDone,
}: {
  version: MapVersion;
  allVersions: MapVersion[];
  mapId: string;
  onDone: () => void;
}) {
  const [values, setValues] = useState<EditState>({
    name: version.name,
    description: version.description ?? "",
    poll_text: version.poll_text,
    revert_poll_text: version.revert_poll_text,
    compatible_versions: version.compatible_versions ?? [],
    newImage: null,
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const updateMutation = useUpdateMapVersion(mapId, version.id);

  const handleSave = () => {
    const fd = new FormData();
    fd.append("name", values.name);
    fd.append("description", values.description);
    fd.append("poll_text", values.poll_text);
    fd.append("revert_poll_text", values.revert_poll_text);
    values.compatible_versions.forEach((id) =>
      fd.append("compatible_versions", String(id))
    );
    if (values.newImage) {
      fd.append("change_img", values.newImage);
    }
    updateMutation.mutate(fd, { onSuccess: onDone });
  };

  const toggleCompatible = (id: number) => {
    setValues((prev) => ({
      ...prev,
      compatible_versions: prev.compatible_versions.includes(id)
        ? prev.compatible_versions.filter((v) => v !== id)
        : [...prev.compatible_versions, id],
    }));
  };

  const otherVersions = allVersions.filter((v) => v.id !== version.id);
  const imgUrl = values.newImage
    ? URL.createObjectURL(values.newImage)
    : version.change_img_url
      ? version.change_img_url.startsWith("http")
        ? version.change_img_url
        : `${API_BASE_URL}${version.change_img_url}`
      : null;

  return (
    <div className="space-y-3 pt-2">
      <EditorField label={de.editor.version.name}>
        <input
          className={editorControl}
          value={values.name}
          onChange={(e) => setValues({ ...values, name: e.target.value })}
        />
      </EditorField>

      <EditorField label={de.editor.version.description}>
        <textarea
          rows={2}
          className={editorControl}
          value={values.description}
          onChange={(e) => setValues({ ...values, description: e.target.value })}
        />
      </EditorField>

      <EditorField label={de.editor.version.pollForward}>
        <input
          className={editorControl}
          value={values.poll_text}
          onChange={(e) => setValues({ ...values, poll_text: e.target.value })}
        />
      </EditorField>

      <EditorField label={de.editor.version.pollRevert}>
        <input
          className={editorControl}
          value={values.revert_poll_text}
          onChange={(e) =>
            setValues({ ...values, revert_poll_text: e.target.value })
          }
        />
      </EditorField>

      {otherVersions.length > 0 && (
        <EditorField label={de.editor.version.compatible}>
          <div className="max-h-36 space-y-1 overflow-y-auto rounded-md border px-2 py-1.5">
            {otherVersions.map((v) => (
              <label
                key={v.id}
                className="flex cursor-pointer items-center gap-2 text-sm"
              >
                <input
                  type="checkbox"
                  checked={values.compatible_versions.includes(v.id)}
                  onChange={() => toggleCompatible(v.id)}
                  className="size-4 rounded accent-primary"
                />
                <span className="truncate">{v.name}</span>
                {v.base_version && (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {de.editor.version.baseSuffix}
                  </span>
                )}
              </label>
            ))}
          </div>
        </EditorField>
      )}

      <EditorField label={de.editor.version.changeImage}>
        {imgUrl && (
          <img
            src={imgUrl}
            alt={de.editor.version.changeImageAlt}
            className="mb-1.5 max-h-32 w-full rounded-md border object-contain"
          />
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) =>
            setValues({ ...values, newImage: e.target.files?.[0] ?? null })
          }
        />
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={() => fileRef.current?.click()}
          >
            {imgUrl
              ? de.editor.version.replaceImage
              : de.editor.version.uploadImage}
          </Button>
          {values.newImage && (
            <span className="truncate text-xs text-muted-foreground">
              {values.newImage.name}
            </span>
          )}
        </div>
      </EditorField>

      <div className="flex gap-2 pt-1">
        <Button
          type="button"
          size="sm"
          className="flex-1"
          onClick={handleSave}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? de.editor.saving : de.editor.save}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="flex-1"
          onClick={onDone}
        >
          {de.editor.cancel}
        </Button>
      </div>

      {updateMutation.isError && (
        <EditorNote tone="attention">
          {de.editor.saveFailed} {updateMutation.error?.message}
        </EditorNote>
      )}
    </div>
  );
}

const VersionManagerPanel = ({ mapId }: VersionManagerPanelProps) => {
  const { data: versions, isLoading } = useMapVersions(mapId);
  const generateMutation = useGenerateCombinations(mapId);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleGenerate = () => {
    const version_ids = Array.from(selectedIds);
    if (version_ids.length < 2) return;
    generateMutation.mutate(
      { version_ids },
      { onSuccess: () => setSelectedIds(new Set()) }
    );
  };

  if (isLoading) {
    return (
      <EditorPanel>
        <p className="text-sm text-muted-foreground">
          {de.editor.version.loading}
        </p>
      </EditorPanel>
    );
  }

  const versionList = versions ?? [];
  const nonBase = versionList.filter((v) => !v.base_version);

  return (
    <EditorPanel title={de.editor.version.manage}>
      {versionList.length === 0 && (
        <p className="text-sm text-muted-foreground">{de.editor.version.none}</p>
      )}

      <div className="space-y-2">
        {versionList.map((v) => (
          <div key={v.id} className="overflow-hidden rounded-md border">
            <div className="flex items-center gap-2 px-3 py-2">
              {!v.base_version && (
                <input
                  type="checkbox"
                  title={de.editor.selectForCombination}
                  checked={selectedIds.has(v.id)}
                  onChange={() => toggleSelected(v.id)}
                  className="size-4 shrink-0 rounded accent-primary"
                />
              )}
              <span className="flex-1 truncate text-sm font-medium">
                {v.name}
              </span>
              {v.base_version && (
                <Badge variant="outline">{de.editor.version.base}</Badge>
              )}
              <Button
                type="button"
                size="xs"
                variant="ghost"
                onClick={() => setExpandedId(expandedId === v.id ? null : v.id)}
              >
                {expandedId === v.id ? de.actions.close : de.editor.edit}
              </Button>
            </div>

            {expandedId === v.id && (
              <div className="border-t px-3 pb-3">
                <VersionEditor
                  version={v}
                  allVersions={versionList}
                  mapId={mapId}
                  onDone={() => setExpandedId(null)}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {nonBase.length >= 2 && (
        <div className="space-y-2 border-t pt-3">
          <EditorNote>{de.editor.version.generateHint}</EditorNote>
          <Button
            type="button"
            size="sm"
            className="w-full"
            onClick={handleGenerate}
            disabled={selectedIds.size < 2 || generateMutation.isPending}
          >
            {generateMutation.isPending
              ? de.editor.version.generating
              : de.editor.version.generateWithCount(selectedIds.size)}
          </Button>
          {generateMutation.isSuccess && (
            <EditorNote>
              {de.editor.version.generated(generateMutation.data.created)}
            </EditorNote>
          )}
          {generateMutation.isError && (
            <EditorNote tone="attention">
              {de.editor.version.generateFailed}{" "}
              {generateMutation.error?.message}
            </EditorNote>
          )}
        </div>
      )}
    </EditorPanel>
  );
};

export default VersionManagerPanel;
