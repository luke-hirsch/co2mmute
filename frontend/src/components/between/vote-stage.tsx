import { useState, type ReactNode } from "react";

import GameMapViewer from "@/components/game/GameMapViewer";
import { Ballot } from "@/components/between/ballot";
import { MapLayoutToggle } from "@/components/layout/map-layout-toggle";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { useVoteMap } from "@/hooks/use-vote-map";
import type { VoteOption } from "@/lib/game/events";
import type { MapLayout } from "@/lib/game/map-layout";

/**
 * The map the class is deciding about — on its own.
 *
 * Either the live network with last round's traffic on it, or, when an option's
 * toggle is on, that option's change picture. The picture is a PNG somebody
 * highlighted by hand because an SVG diff of one bus lane is not something a
 * room can see; it is only ever offered when the version has one stored.
 */
export function VoteMap({ changeImage }: { changeImage?: VoteOption | null }) {
  const { graph, jam, isLoading } = useVoteMap();

  return (
    <section aria-label={de.vote.mapTitle}>
      {changeImage?.change_img_url ? (
        <figure>
          <img
            src={changeImage.change_img_url}
            alt={de.vote.changeAlt(changeImage.name)}
            className="w-full rounded-md border border-border bg-subtle object-contain dark:bg-darksubtle"
          />
          <figcaption className="mt-3 text-sm text-muted-foreground">
            {de.vote.changeCaption(changeImage.name)}
          </figcaption>
        </figure>
      ) : (
        <GameMapViewer mapGraph={graph} isLoading={isLoading} compact jam={jam} />
      )}
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
  const [changeShownId, setChangeShownId] = useState<number | null>(null);
  // Looked up rather than trusted: a ballot that is redrawn after a tie may no
  // longer hold the option that was toggled.
  const shown = options.find((option) => option.id === changeShownId) ?? null;

  return (
    <MapStage
      layout={layout}
      onLayoutChange={onLayoutChange}
      map={<VoteMap changeImage={shown} />}
    >
      <Ballot
        options={options}
        onPick={onPick}
        disabled={disabled}
        stacked={layout === "beside"}
        changeShownId={shown?.id ?? null}
        onToggleChange={(id) =>
          setChangeShownId((current) => (current === id ? null : id))
        }
      />
    </MapStage>
  );
}
