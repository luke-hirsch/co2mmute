import { Button } from "@/components/ui/button";
import { MapChangeCard } from "@/components/between/map-change-card";
import { cn } from "@/lib/utils";
import { de } from "@/lib/de";
import { KeyHint } from "@/components/between/key-hint";
import { useVoteKeys } from "@/hooks/use-vote-keys";
import type { VoteOption } from "@/lib/game/events";

/**
 * The ballot itself: the options on it, plus "so lassen".
 *
 * Shared by the player's own vote and by the host casting one for a seat at the
 * machine — the ballot is the same piece of paper either way, only the seat it
 * is filed under differs. That is the same reason `RoundScreen` takes a seat
 * instead of reading "me" (F3).
 *
 * **"So lassen" is an option, not an abstention.** `submit_vote` takes
 * `version_id: null` as a vote for leaving the map as it is, and it counts
 * towards the tally like any other — which is exactly how a tie happens. It is
 * therefore a button of equal standing, below the cards rather than beside
 * them, because it is the one choice that is always available.
 *
 * **It can be filled in from the keyboard** (S24): `1`, `2`, … for the cards,
 * `0` for "so lassen". A mouse crossing a projected screen tells the room how
 * you are about to vote; a key press does not. The keys are printed on the
 * buttons so nobody has to be told.
 *
 * Only versions on this round's ballot are accepted (`vote_options`), so the
 * options are rendered from `voteOptions` in the reducer and never from
 * anything a screen has kept lying around.
 */
export function Ballot({
  options,
  onPick,
  disabled = false,
  stacked = false,
  changeShownId = null,
  onToggleChange,
}: {
  options: VoteOption[];
  /** null is "so lassen". */
  onPick: (versionId: number | null) => void;
  disabled?: boolean;
  /** One column from `lg` up — the ballot is half a screen wide (S24). */
  stacked?: boolean;
  /** The option whose change picture the stage is showing, if any. */
  changeShownId?: number | null;
  onToggleChange?: (versionId: number) => void;
}) {
  useVoteKeys(options, onPick, disabled);

  return (
    <div>
      <div className={cn("grid gap-10 sm:grid-cols-2", stacked && "lg:grid-cols-1")}>
        {options.map((option, index) => (
          <MapChangeCard
            key={option.id}
            option={option}
            changeShown={changeShownId === option.id}
            onToggleChange={
              onToggleChange ? () => onToggleChange(option.id) : undefined
            }
          >
            <div>
              <Button
                onClick={() => onPick(option.id)}
                disabled={disabled}
                className="w-full sm:w-auto"
                aria-keyshortcuts={String(index + 1)}
              >
                {de.vote.pick}
                <KeyHint>{index + 1}</KeyHint>
              </Button>
            </div>
          </MapChangeCard>
        ))}
      </div>

      <div className="mt-10 border-t border-border pt-6">
        <Button
          variant="outline"
          onClick={() => onPick(null)}
          disabled={disabled}
          aria-keyshortcuts="0"
        >
          {de.vote.keep}
          <KeyHint>0</KeyHint>
        </Button>
        <p className="mt-3 text-sm text-muted-foreground">{de.vote.keepHint}</p>
      </div>
    </div>
  );
}
