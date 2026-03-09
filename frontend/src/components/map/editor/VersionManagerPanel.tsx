import { useRef, useState } from "react";
import {
  useGenerateCombinations,
  useMapVersions,
  useUpdateMapVersion,
} from "../../../hooks/mapHooks";
import { API_BASE_URL } from "../../../config";
import type { MapVersion } from "../../../types/mapTypes";

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
    // Send compatible_versions as repeated form fields
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
      <div>
        <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
          Name
        </label>
        <input
          className="w-full rounded border border-subtle dark:border-darksubtle bg-white dark:bg-darkbg px-2 py-1 text-sm text-main dark:text-darktext"
          value={values.name}
          onChange={(e) => setValues({ ...values, name: e.target.value })}
        />
      </div>
      <div>
        <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
          Description
        </label>
        <textarea
          rows={2}
          className="w-full rounded border border-subtle dark:border-darksubtle bg-white dark:bg-darkbg px-2 py-1 text-sm text-main dark:text-darktext"
          value={values.description}
          onChange={(e) => setValues({ ...values, description: e.target.value })}
        />
      </div>
      <div>
        <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
          Poll text (forward)
        </label>
        <input
          className="w-full rounded border border-subtle dark:border-darksubtle bg-white dark:bg-darkbg px-2 py-1 text-sm text-main dark:text-darktext"
          value={values.poll_text}
          onChange={(e) => setValues({ ...values, poll_text: e.target.value })}
        />
      </div>
      <div>
        <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
          Poll text (revert)
        </label>
        <input
          className="w-full rounded border border-subtle dark:border-darksubtle bg-white dark:bg-darkbg px-2 py-1 text-sm text-main dark:text-darktext"
          value={values.revert_poll_text}
          onChange={(e) =>
            setValues({ ...values, revert_poll_text: e.target.value })
          }
        />
      </div>

      {otherVersions.length > 0 && (
        <div>
          <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
            Compatible versions
          </label>
          <div className="space-y-1 max-h-36 overflow-y-auto">
            {otherVersions.map((v) => (
              <label key={v.id} className="flex items-center gap-2 text-sm text-main dark:text-darktext cursor-pointer">
                <input
                  type="checkbox"
                  checked={values.compatible_versions.includes(v.id)}
                  onChange={() => toggleCompatible(v.id)}
                />
                {v.name}
                {v.base_version && (
                  <span className="text-xs text-muted dark:text-darkmutedtext">(base)</span>
                )}
              </label>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="block text-xs text-muted dark:text-darkmutedtext mb-1">
          Change image
        </label>
        {imgUrl && (
          <img
            src={imgUrl}
            alt="change preview"
            className="w-full max-h-32 object-contain rounded mb-1 border border-subtle dark:border-darksubtle"
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
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="text-xs px-2 py-1 rounded border border-subtle dark:border-darksubtle text-main dark:text-darktext hover:bg-subtle dark:hover:bg-darksubtle"
        >
          {imgUrl ? "Replace image" : "Upload image"}
        </button>
        {values.newImage && (
          <span className="ml-2 text-xs text-muted dark:text-darkmutedtext">
            {values.newImage.name}
          </span>
        )}
      </div>

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="flex-1 rounded bg-accent dark:bg-darkaccent text-white text-sm py-1 hover:opacity-80 disabled:opacity-50"
        >
          {updateMutation.isPending ? "Saving..." : "Save"}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="flex-1 rounded border border-subtle dark:border-darksubtle text-sm py-1 text-main dark:text-darktext hover:bg-subtle dark:hover:bg-darksubtle"
        >
          Cancel
        </button>
      </div>
      {updateMutation.isError && (
        <p className="text-xs text-red-500">
          Save failed. {updateMutation.error?.message}
        </p>
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
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle">
        <p className="text-sm text-muted dark:text-darkmutedtext">Loading versions...</p>
      </div>
    );
  }

  const versionList = versions ?? [];
  const nonBase = versionList.filter((v) => !v.base_version);

  return (
    <div className="bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle dark:border-darksubtle space-y-3">
      <h3 className="text-lg font-semibold text-main dark:text-darktext">
        Manage Versions
      </h3>

      {versionList.length === 0 && (
        <p className="text-sm text-muted dark:text-darkmutedtext">No versions yet.</p>
      )}

      <div className="space-y-2">
        {versionList.map((v) => (
          <div
            key={v.id}
            className="rounded border border-subtle dark:border-darksubtle bg-white dark:bg-darkbg"
          >
            <div className="flex items-center gap-2 px-3 py-2">
              {!v.base_version && (
                <input
                  type="checkbox"
                  title="Select for combination generation"
                  checked={selectedIds.has(v.id)}
                  onChange={() => toggleSelected(v.id)}
                  className="shrink-0"
                />
              )}
              <span className="flex-1 text-sm font-medium text-main dark:text-darktext truncate">
                {v.name}
              </span>
              {v.base_version && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-accent/10 dark:bg-darkaccent/10 text-accent dark:text-darkaccent">
                  base
                </span>
              )}
              <button
                type="button"
                onClick={() =>
                  setExpandedId(expandedId === v.id ? null : v.id)
                }
                className="text-xs text-accent dark:text-darkaccent hover:underline"
              >
                {expandedId === v.id ? "Close" : "Edit"}
              </button>
            </div>

            {expandedId === v.id && (
              <div className="px-3 pb-3 border-t border-subtle dark:border-darksubtle">
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
        <div className="pt-2 border-t border-subtle dark:border-darksubtle space-y-2">
          <p className="text-xs text-muted dark:text-darkmutedtext">
            Select 2+ non-base versions above to generate all combination versions.
          </p>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={selectedIds.size < 2 || generateMutation.isPending}
            className="w-full rounded bg-accent dark:bg-darkaccent text-white text-sm py-1.5 hover:opacity-80 disabled:opacity-40"
          >
            {generateMutation.isPending
              ? "Generating..."
              : `Generate combinations (${selectedIds.size} selected)`}
          </button>
          {generateMutation.isSuccess && (
            <p className="text-xs text-green-600 dark:text-green-400">
              Created {generateMutation.data.created} combination version(s).
            </p>
          )}
          {generateMutation.isError && (
            <p className="text-xs text-red-500">
              Failed. {generateMutation.error?.message}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default VersionManagerPanel;
