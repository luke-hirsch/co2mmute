import { useMemo, type ReactNode } from "react";

import GameMapViewer from "@/components/game/GameMapViewer";
import { Ballot } from "@/components/between/ballot";
import { MapLayoutToggle } from "@/components/layout/map-layout-toggle";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { useShownChange } from "@/hooks/use-shown-change";
import { useVoteMap } from "@/hooks/use-vote-map";
import { VersionDiffLegend } from "@/components/map/version-diff-layer";
import { diffGraphs } from "@/lib/map/version-diff";
import { useMapGraph } from "@/lib/queries/map-graph";
import type { VoteOption } from "@/lib/game/events";
import type { MapLayout } from "@/lib/game/map-layout";

/**
 * The map the class is deciding about — on its own.
 *
 * The live network with last round's traffic on it, or, when an option's
 * toggle is on, the same map with what that option changes drawn over it: the
 * option's graph against the one the game is on (`lib/map/version-diff.ts`),
 * streets in the primary, Bus & Bahn in the accent, what goes hollow. It used to
 * swap the map for a PNG somebody had highlighted by hand, on the argument that
 * an SVG diff of one bus lane is not something a room can see; drawn heavier
 * than a route on a quiet network, it is, and it needs nobody to draw it.
 */
export function VoteMap({ change }: { change?: VoteOption | null }) {
  const { graph, jam, isLoading, mapId } = useVoteMap();
  // Only fetched while an option is shown; the graph has no traffic attached,
  // and the diff never reads any.
  const option = useMapGraph(change ? mapId : undefined, change?.id);
  const diff = useMemo(
    () => (change && graph && option.data ? diffGraphs(graph, option.data) : null),
    [change, graph, option.data],
  );

  return (
    <section aria-label={de.vote.mapTitle}>
      <GameMapViewer
        mapGraph={graph}
        isLoading={isLoading}
        compact
        jam={jam}
        change={diff}
      />
      {change ? (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-muted-foreground">
            {!diff
              ? de.vote.changeLoading
              : diff.empty
                ? de.map.diff.nothing
                : de.vote.changeCaption(change.name)}
          </p>
          {diff && !diff.empty ? <VersionDiffLegend diff={diff} /> : null}
        </div>
      ) : null}
    </section>
  );
}

/**
 * A map and what the class is deciding about, in the layout the person at the
 * screen picked — the discussion, the ballot and the host's vote overview.
 *
 * The layout belongs to the caller because the page width does: a `Screen` has to
 * go `full` for the half-and-half, and only the screen can say so.
 */
export function MapStage({
  layout,
  onLayoutChange,
  map,
  children,
}: {
  layout: MapLayout;
  onLayoutChange: (layout: MapLayout) => void;
  map: ReactNode;
  children: ReactNode;
}) {
  const beside = layout === "beside";

  return (
    <div
      className={cn(beside && "lg:grid lg:grid-cols-2 lg:items-start lg:gap-12")}
    >
      <div className={cn("mb-10", beside && "lg:sticky lg:top-8 lg:mb-0")}>
        <MapLayoutToggle layout={layout} onChange={onLayoutChange} />
        <div className="lg:mt-3">{map}</div>
      </div>
      <div>{children}</div>
    </div>
  );
}

/** The map and the ballot. */
export function VoteStage({
  layout,
  onLayoutChange,
  options,
  onPick,
  disabled,
}: {
  layout: MapLayout;
  onLayoutChange: (layout: MapLayout) => void;
  options: VoteOption[];
  onPick: (versionId: number | null) => void;
  disabled?: boolean;
}) {
  const { shown, toggle } = useShownChange(options);

  return (
    <MapStage
      layout={layout}
      onLayoutChange={onLayoutChange}
      map={<VoteMap change={shown} />}
    >
      <Ballot
        options={options}
        onPick={onPick}
        disabled={disabled}
        stacked={layout === "beside"}
        changeShownId={shown?.id ?? null}
        onToggleChange={toggle}
      />
    </MapStage>
  );
}
