import { Alert, AlertDescription } from "@/components/ui/alert";
import { Ballot } from "@/components/between/ballot";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";
import { useGame } from "@/components/game/game-context";
import { usePhase } from "@/hooks/use-phase";

/**
 * One vote, for this device's own seat (Z-05).
 *
 * The count under it is the backend's (`vote.recorded` → `votes_cast` /
 * `votes_needed`), which is the same counting rule the round uses — playing
 * seats on both sides, seats at the host machine included. It is deliberately
 * not derived from the roster here; deriving it a second way is how the backend
 * ended up with that rule written out nine times.
 *
 * Whether *this* seat has voted is this device's own note (see `use-phase.ts`),
 * with the server's refusal as the backstop: vote twice — or vote after a
 * reload has forgotten the first one — and the screen says the vote is already
 * in rather than showing an error.
 */
export function VotingScreen() {
  const { state, seatId } = useGame();
  const phase = usePhase();

  const voted = phase.hasVoted(seatId);

  return (
    <Screen>
      <ScreenHeading title={de.vote.title} lead={de.vote.lead} />

      {phase.refused ? (
        <Alert className="mb-10">
          <AlertDescription>{phase.refused}</AlertDescription>
        </Alert>
      ) : null}

      {voted ? (
        <div>
          <p className="font-medium">{de.vote.cast}</p>
          <p className="mt-2 max-w-(--measure-body) text-muted-foreground">
            {de.vote.castBody}
          </p>
        </div>
      ) : (
        <Ballot
          options={state.voteOptions}
          onPick={(versionId) => {
            if (seatId) phase.vote(seatId, versionId);
          }}
          disabled={!seatId || !!state.pausedAt}
        />
      )}

      {state.votes ? (
        <p className="mt-12 font-mono text-sm tabular-nums text-muted-foreground">
          {de.vote.progress(state.votes.cast, state.votes.needed)}
        </p>
      ) : null}
    </Screen>
  );
}
