import { Button } from "@/components/ui/button";
import { MapChangeCard } from "@/components/between/map-change-card";
import { de } from "@/lib/de";
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
 * Only versions on this round's ballot are accepted (`vote_options`), so the
 * options are rendered from `voteOptions` in the reducer and never from
 * anything a screen has kept lying around.
 */
export function Ballot({
  options,
  onPick,
  disabled = false,
}: {
  options: VoteOption[];
  /** null is "so lassen". */
  onPick: (versionId: number | null) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <div className="grid gap-10 sm:grid-cols-2">
        {options.map((option) => (
          <MapChangeCard key={option.id} option={option}>
            <div>
              <Button
                onClick={() => onPick(option.id)}
                disabled={disabled}
                className="w-full sm:w-auto"
              >
                {de.vote.pick}
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
        >
          {de.vote.keep}
        </Button>
        <p className="mt-3 text-sm text-muted-foreground">{de.vote.keepHint}</p>
      </div>
    </div>
  );
}
