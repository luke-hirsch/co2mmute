import { Button } from "@/components/ui/button";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { StatsPanel } from "@/components/between/stats-panel";
import { de } from "@/lib/de";
import { useGame } from "@/components/game/game-context";
import { usePhase } from "@/hooks/use-phase";

/**
 * The round is through, here is what it cost (Z-01, Z-02).
 *
 * One button, and the phase ends when everybody has pressed it
 * (`phases._advance_from_stats`). Nothing says *who* is still missing — no event
 * carries the acks — so the waiting line is deliberately vague rather than
 * inventing a name.
 *
 * Pressing it again after a reload is harmless: `StatsAck` is a `get_or_create`
 * on the seat, so a second ack is a no-op, which is why this screen does not
 * have to remember anything across a page load.
 */
export function StatsScreen() {
  const { state, seatId } = useGame();
  const phase = usePhase();

  return (
    <Screen>
      <ScreenHeading
        title={de.between.statsTitle(
          state.lastRound?.roundNumber ?? state.currentRound,
        )}
        lead={de.between.statsLead}
      />

      {state.lastRound ? (
        <StatsPanel
          round={state.lastRound}
          seatId={seatId}
          totalEmissionsG={state.totalEmissionsG}
          maxCo2LevelG={state.maxCo2LevelG}
        />
      ) : (
        // The stats phase without a `round.completed` behind it: this client
        // connected into the phase and `game.state` carries the phase but not
        // the figures. The button still has to work, or the game stops here.
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.app.empty}
        </p>
      )}

      <div className="mt-12">
        {phase.acked ? (
          <div>
            <p className="font-medium">{de.between.acked}</p>
            <p className="mt-2 max-w-(--measure-body) text-muted-foreground">
              {de.between.ackedBody}
            </p>
          </div>
        ) : (
          <Button size="lg" onClick={phase.ackStats} disabled={!!state.pausedAt}>
            {de.between.ack}
          </Button>
        )}
      </div>
    </Screen>
  );
}
