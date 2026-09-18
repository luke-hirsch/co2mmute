import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";
import { useGame } from "@/components/game/game-context";
import { usePhase } from "@/hooks/use-phase";

/**
 * The vote tied: vote again, or leave the map as it is (Z-06, Z-07, Z-08).
 *
 * The phase is only ever entered once per round. `MAX_STALEMATES` is 2 and
 * `_tally_if_complete` only claims this phase while `stalemate_count` is below
 * it — so a second tie is not asked about, it just leaves the map alone. Which
 * is why the screen can say flatly that this is the last vote, without carrying
 * a counter around to work it out.
 *
 * A majority for "nochmal" reopens the **same** ballot with the votes deleted
 * (`_reopen_vote`); anything else starts the next round unchanged.
 */
export function StalemateScreen() {
  const { state, seatId } = useGame();
  const phase = usePhase();

  const answered = phase.hasAnswered(seatId);
  const blocked = !seatId || !!state.pausedAt;

  return (
    <Screen narrow>
      <ScreenHeading
        title={de.vote.tieTitle}
        lead={
          <>
            {de.vote.tieLead}{" "}
            <span className="text-foreground">{de.vote.tieLast}</span>
          </>
        }
      />

      {phase.refused ? (
        <Alert className="mb-10">
          <AlertDescription>{phase.refused}</AlertDescription>
        </Alert>
      ) : null}

      {answered ? (
        <p className="font-medium">{de.vote.tieAnswered}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-4">
          <Button
            size="lg"
            onClick={() => seatId && phase.answerTie(seatId, true)}
            disabled={blocked}
          >
            {de.vote.revote}
          </Button>
          <Button
            variant="outline"
            size="lg"
            onClick={() => seatId && phase.answerTie(seatId, false)}
            disabled={blocked}
          >
            {de.vote.leaveAsIs}
          </Button>
        </div>
      )}

      {state.stalemate ? (
        <p className="mt-12 font-mono text-sm tabular-nums text-muted-foreground">
          {de.vote.tieProgress(state.stalemate.cast, state.stalemate.needed)}
        </p>
      ) : null}
    </Screen>
  );
}
