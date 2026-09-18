import { MapChangeCard } from "@/components/between/map-change-card";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";
import { useGame } from "@/components/game/game-context";

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
 */
export function DiscussionScreen() {
  const { state } = useGame();

  return (
    <Screen>
      <ScreenHeading
        title={de.between.discussionTitle}
        lead={de.between.discussionLead}
      />

      {state.voteOptions.length === 0 ? (
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.between.noOptions}
        </p>
      ) : (
        <div className="grid gap-10 sm:grid-cols-2">
          {state.voteOptions.map((option) => (
            <MapChangeCard key={option.id} option={option} />
          ))}
        </div>
      )}

      <p className="mt-12 text-muted-foreground">
        {de.between.discussionWaiting}
      </p>
    </Screen>
  );
}
