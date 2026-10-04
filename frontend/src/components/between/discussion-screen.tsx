import { MapChangeCard } from "@/components/between/map-change-card";
import { MapStage, VoteMap } from "@/components/between/vote-stage";
import { useShownChange } from "@/hooks/use-shown-change";
import { NumbersExplainerPanel } from "@/components/numbers/numbers-explainer";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { useGame } from "@/components/game/game-context";
import { useMapLayout } from "@/hooks/use-map-layout";
import type { MapLayout } from "@/lib/game/map-layout";

/**
 * The options, before anybody votes (Z-04).
 *
 * The phase exists so the class talks about the change with the picture in
 * front of them, and it ends only when the host opens the vote
 * (`phases.open_vote`, and only from here). For a player there is nothing to
 * press, which the screen says plainly instead of showing a disabled button.
 *
 * The host sees the same cards with the opening control under them — that is
 * `host-between-screen.tsx`, not a role flag in this file.
 *
 * The explain-the-numbers text is here in full, and this is the screen it was
 * written for: the class is arguing about the map with nothing to press, and the
 * two facts that decide the argument — one Gruppe is a hundred people, a line
 * emits whether it is ridden or not — belong in front of them **before** the
 * ballot rather than beside it (Lukas, 2026-09-22). Next to the vote it hands
 * them a conclusion; here it hands them the question.
 */
export function DiscussionScreen() {
  const [layout, setLayout] = useMapLayout();

  return (
    <Screen full={layout === "beside"}>
      <ScreenHeading
        title={de.between.discussionTitle}
        lead={de.between.discussionLead}
      />

      <DiscussionStage layout={layout} onLayoutChange={setLayout} />

      <p className="mt-12 text-muted-foreground">
        {de.between.discussionWaiting}
      </p>

      <NumbersExplainerPanel className="mt-16 border-t border-border pt-8" />
    </Screen>
  );
}

/**
 * The map with the round just played on it, and the options beside or under it
 * (F3) — for the phone and, in `host-between-screen.tsx`, for the projector.
 *
 * The map is the same one the ballot shows, so the class argues over the picture
 * it will vote on — and each card can put its change on that map, as on the
 * ballot. On the projector that is the moment the room sees what a bus lane
 * actually takes.
 */
export function DiscussionStage({
  layout,
  onLayoutChange,
}: {
  layout: MapLayout;
  onLayoutChange: (layout: MapLayout) => void;
}) {
  const { state } = useGame();
  const { shown, toggle } = useShownChange(state.voteOptions);

  return (
    <MapStage
      layout={layout}
      onLayoutChange={onLayoutChange}
      map={<VoteMap change={shown} />}
    >
      {state.voteOptions.length === 0 ? (
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.between.noOptions}
        </p>
      ) : (
        <div
          className={cn(
            "grid gap-10 sm:grid-cols-2",
            layout === "beside" && "lg:grid-cols-1",
          )}
        >
          {state.voteOptions.map((option) => (
            <MapChangeCard
              key={option.id}
              option={option}
              changeShown={shown?.id === option.id}
              onToggleChange={() => toggle(option.id)}
            />
          ))}
        </div>
      )}
    </MapStage>
  );
}
