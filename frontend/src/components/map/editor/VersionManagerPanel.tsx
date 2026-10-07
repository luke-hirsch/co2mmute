import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeleteVersionDialog } from "@/components/map/editor/delete-version-dialog";
import {
  EditorField,
  EditorNote,
  EditorPanel,
  editorControl,
} from "@/components/map/editor/editor-panel";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { PT_LINE_PAINT } from "@/lib/map/palette";
import {
  linkEntries,
  type DiffableGraph,
  type LinkAspect,
  type Network,
  type Sense,
  type VersionDiff,
} from "@/lib/map/version-diff";
import {
  useGenerateCombinations,
  useMapVersions,
  useUpdateMapVersion,
} from "@/lib/queries/map-graph";
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
 *
 * ### What a version does (the version comparison)
 *
 * "Verwalten" used to change nothing on the canvas: you could tick versions and
 * build combinations, and the only way to learn what `Busspuren` actually does
 * was the database. Now each version can be put on the canvas ("Ansehen") and is
 * drawn against the version it was made from — or any other, by the select —
 * with the change list in words beside it (`lib/map/version-diff.ts`). The
 * ballot draws the same comparison, so the change picture (`change_img`) is no
 * longer offered here: nothing in the game shows it any more.
 */

/** Which version the canvas shows, what it is compared with, and the result. */
export type VersionComparison = {
  shownId: number | undefined;
  compareId: number | null;
  onCompareChange: (versionId: number | null) => void;
  diff: VersionDiff | null;
  /** The two graphs compared, for the names of the places in the list. */
  graphs: (DiffableGraph | undefined)[];
};

interface VersionManagerPanelProps {
  mapId: string;
  /** The version the editor is showing, so a delete can step off it first. */
  selectedVersionId?: number;
  onVersionChange?: (versionId: number | undefined) => void;
  compare: VersionComparison;
}

interface EditState {
  name: string;
  description: string;
  poll_text: string;
  revert_poll_text: string;
  compatible_versions: number[];
}

function VersionEditor({
  version,
  allVersions,
  mapId,
  onDone,
  onDeleting,
}: {
  version: MapVersion;
  allVersions: MapVersion[];
  mapId: string;
  onDone: () => void;
  onDeleting: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const [values, setValues] = useState<EditState>({
    name: version.name,
    description: version.description ?? "",
    poll_text: version.poll_text,
    revert_poll_text: version.revert_poll_text,
    compatible_versions: version.compatible_versions ?? [],
  });
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

      {/* F14. Not for the base version: every game starts on it, and the
          server refuses it anyway. */}
      {!version.base_version && (
        <>
          <Button
            type="button"
            size="sm"
            variant="destructive"
            className="w-full"
            onClick={() => setAsking(true)}
          >
            {de.editor.version.deleteVersion}
          </Button>
          <DeleteVersionDialog
            mapId={mapId}
            version={version}
            open={asking}
            onOpenChange={setAsking}
            onDeleting={onDeleting}
            onDeleted={onDone}
          />
        </>
      )}
    </div>
  );
}

const VersionManagerPanel = ({
  mapId,
  selectedVersionId,
  onVersionChange,
  compare,
}: VersionManagerPanelProps) => {
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
        {versionList.map((v) => {
          const shown = v.id === compare.shownId;
          return (
          <div
            key={v.id}
            className={cn(
              "overflow-hidden rounded-md border",
              shown && "border-primary",
            )}
          >
            {/* Name on a line of its own: a combination is called
                "Buslinie + Busspuren + Umgehungsstraßen", and beside two
                buttons in a quarter-width sidebar it was "Buslinie + …"
                three times over. */}
            <div className="px-3 py-2">
              <div className="flex items-start gap-2">
                {!v.base_version && (
                  <input
                    type="checkbox"
                    title={de.editor.selectForCombination}
                    checked={selectedIds.has(v.id)}
                    onChange={() => toggleSelected(v.id)}
                    className="mt-0.5 size-4 shrink-0 rounded accent-primary"
                  />
                )}
                <span className="flex-1 text-sm font-medium hyphens-auto">
                  {v.name}
                </span>
                {v.base_version && (
                  <Badge variant="outline">{de.editor.version.base}</Badge>
                )}
              </div>
              <div className="mt-1 flex items-center justify-end gap-1">
                {shown ? (
                  <Badge>{de.editor.version.shown}</Badge>
                ) : (
                  <Button
                    type="button"
                    size="xs"
                    variant="ghost"
                    // Base by the base endpoint, as the editor opens it, so
                    // the two share one cached graph.
                    onClick={() =>
                      onVersionChange?.(v.base_version ? undefined : v.id)
                    }
                  >
                    {de.editor.version.show}
                  </Button>
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
            </div>

            {expandedId === v.id && (
              <div className="border-t px-3 pb-3">
                <VersionEditor
                  version={v}
                  allVersions={versionList}
                  mapId={mapId}
                  onDone={() => setExpandedId(null)}
                  onDeleting={() => {
                    // The editor would ask for this version's graph again
                    // after the delete and get a 404; it goes back to base.
                    if (selectedVersionId === v.id) onVersionChange?.(undefined);
                    setSelectedIds((prev) => {
                      const next = new Set(prev);
                      next.delete(v.id);
                      return next;
                    });
                  }}
                />
              </div>
            )}
          </div>
          );
        })}
      </div>

      <Comparison versions={versionList} compare={compare} />

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

/**
 * The version on the canvas against another one: the select, and what changes
 * in words, grouped by the network it changes — the same two colours the
 * canvas draws them in.
 */
function Comparison({
  versions,
  compare,
}: {
  versions: MapVersion[];
  compare: VersionComparison;
}) {
  const shown = versions.find((v) => v.id === compare.shownId);
  if (!shown) return null;

  const names = new Map<number, string>();
  for (const graph of compare.graphs) {
    for (const node of graph?.nodes ?? []) {
      names.set(node.id, node.name || de.map.diff.unnamed(node.id));
    }
  }
  const name = (id: number) => names.get(id) ?? de.map.diff.unnamed(id);

  const { diff } = compare;

  return (
    <section className="space-y-3 border-t pt-3">
      <h3 className="text-sm font-medium">
        {de.editor.version.diffTitle(shown.name)}
      </h3>
      <EditorField label={de.editor.version.compareWith}>
        <select
          className={editorControl}
          aria-label={de.editor.version.compareWith}
          value={compare.compareId ?? ""}
          onChange={(e) =>
            compare.onCompareChange(e.target.value ? Number(e.target.value) : null)
          }
        >
          <option value="">{de.editor.version.compareNothing}</option>
          {versions
            .filter((v) => v.id !== shown.id)
            .map((v) => (
              <option key={v.id} value={v.id}>
                {v.base_version ? `${v.name} ${de.editor.version.baseSuffix}` : v.name}
              </option>
            ))}
        </select>
      </EditorField>

      {compare.compareId === null ? (
        <EditorNote>{de.editor.version.compareHint}</EditorNote>
      ) : !diff ? (
        <p className="text-sm text-muted-foreground">{de.editor.loading}</p>
      ) : diff.empty ? (
        <EditorNote>{de.map.diff.nothing}</EditorNote>
      ) : (
        <ChangeList diff={diff} name={name} />
      )}
    </section>
  );
}

const PAINT: Record<Network, string> = {
  street: "var(--color-primary)",
  pt: PT_LINE_PAINT,
};

/** A short stroke in the canvas's own paint: full for what comes, hollow for what goes. */
function Swatch({ network, sense }: { network: Network; sense: Sense }) {
  return (
    <svg
      width="20"
      height="10"
      viewBox="0 0 20 10"
      aria-hidden="true"
      className="mt-1 shrink-0"
    >
      <line
        x1="3"
        y1="5"
        x2="17"
        y2="5"
        stroke={PAINT[network]}
        strokeWidth="6"
        strokeLinecap="round"
      />
      {sense === "removed" ? (
        <line
          x1="3"
          y1="5"
          x2="17"
          y2="5"
          stroke="var(--color-card)"
          strokeWidth="2.7"
          strokeLinecap="round"
        />
      ) : null}
    </svg>
  );
}

function aspectText(aspect: LinkAspect, sense: Sense): string {
  const added = sense !== "removed";
  switch (aspect.kind) {
    case "street":
      return de.map.diff.street(added, aspect.lanes, aspect.speedLimit);
    case "rail":
      return de.map.diff.rail(added);
    case "path":
      return de.map.diff.path(added, aspect.biking, aspect.walking);
    case "busLane":
      return de.map.diff.busLane(added);
    case "tramTrack":
      return de.map.diff.tramTrack(aspect.from, aspect.to);
    case "bikeLane":
      return de.map.diff.bikeLane(added);
    case "biking":
      return de.map.diff.biking(added);
    case "walking":
      return de.map.diff.walking(added);
    case "lanes":
      return de.map.diff.lanes(aspect.from, aspect.to);
    case "speed":
      return de.map.diff.speed(aspect.from, aspect.to);
  }
}

type Item = { key: string; network: Network; sense: Sense; title: string; detail: string };

function ChangeList({
  diff,
  name,
}: {
  diff: VersionDiff;
  name: (id: number) => string;
}) {
  const items: Item[] = [
    ...linkEntries(diff.links).map((entry, i) => ({
      key: `link-${i}`,
      network: entry.network,
      sense: entry.sense,
      title: entry.bothWays
        ? de.map.diff.both(name(entry.start), name(entry.end))
        : de.map.diff.oneWay(name(entry.start), name(entry.end)),
      detail: [
        ...(entry.bothWays ? [de.map.diff.bothWays] : []),
        ...entry.aspects.map((aspect) => aspectText(aspect, entry.sense)),
      ].join(", "),
    })),
    ...diff.lines.map((line) => {
      const first = line.stops[0] ?? line.segments[0]?.start;
      const last =
        line.stops[line.stops.length - 1] ??
        line.segments[line.segments.length - 1]?.end;
      const gained = line.segments.filter((s) => s.sense === "added").length;
      return {
        key: `line-${line.type}-${line.id}`,
        network: "pt" as const,
        sense: line.sense,
        title: de.map.diff.line(line.type, line.name, line.kind),
        detail:
          line.sense === "added"
            ? de.map.diff.lineAdded(name(first), name(last))
            : line.sense === "removed"
              ? de.map.diff.lineRemoved
              : de.map.diff.lineChanged(gained, line.segments.length - gained),
      };
    }),
  ];
  const nodes = diff.nodes.map((node) => ({
    key: `node-${node.id}`,
    network: "street" as const,
    sense: node.sense,
    title: node.name || de.map.diff.unnamed(node.id),
    detail: node.sense === "added" ? de.map.diff.nodeAdded : de.map.diff.nodeRemoved,
  }));

  const groups: { label: string; items: Item[] }[] = [
    { label: de.map.diff.streets, items: items.filter((i) => i.network === "street") },
    { label: de.map.diff.pt, items: items.filter((i) => i.network === "pt") },
    { label: de.map.diff.places, items: nodes },
  ].filter((group) => group.items.length > 0);

  return (
    <div className="max-h-[50vh] space-y-4 overflow-y-auto pr-1">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="text-xs text-muted-foreground">
            {group.label} ({group.items.length})
          </p>
          <ul className="mt-1.5 space-y-2">
            {group.items.map((item) => (
              <li key={item.key} className="flex gap-2 text-sm">
                <Swatch network={item.network} sense={item.sense} />
                <div className="min-w-0">
                  <p className="font-medium">{item.title}</p>
                  <p className="text-muted-foreground">{item.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default VersionManagerPanel;
