import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Co2Bar } from "@/components/metro/co2-bar";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { StatsPanel } from "@/components/between/stats-panel";
import { de } from "@/lib/de";
import { displayKg } from "@/lib/co2";
import { useGame } from "@/components/game/game-context";

/**
 * The game is over (E-01, E-02, E-04).
 *
 * Small on purpose. F6 is the summary — per player across every round, from
 * `GET api/game/<id>/summary/` — and this is what has to stand in the meantime,
 * because F5 deletes the pre-rewrite screen that used to own this route and the
 * last screen of a game must not be a blank one.
 *
 * So it says only what the reducer already knows: why it ended, how far it got,
 * what the budget did, and the last round's table. No query, nothing new to get
 * wrong, and everything on it is already proven by the events F2 reduced.
 *
 * The names on it are real until anonymisation runs, 24 h after the end (1.3) —
 * which is deliberate: the debrief happens in the lesson, the names go later.
 */
export function EndScreen() {
  const navigate = useNavigate();
  const { state, seatId } = useGame();

  return (
    <Screen>
      <ScreenHeading
        title={de.summary.title}
        lead={
          state.endReason ? de.summary.reason[state.endReason] : de.summary.lead
        }
      />

      <dl className="mb-12 grid gap-8 sm:grid-cols-2">
        <div>
          <dt className="text-sm text-muted-foreground">{de.summary.total}</dt>
          <dd className="mt-1 font-mono text-3xl tabular-nums">
            {de.summary.kg(displayKg(state.totalEmissionsG))}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">
            {de.summary.budget}
          </dt>
          <dd className="mt-1 font-mono text-3xl tabular-nums">
            {de.summary.kg(displayKg(state.maxCo2LevelG))}
          </dd>
        </div>
      </dl>

      <Co2Bar
        usedG={state.totalEmissionsG}
        maxG={state.maxCo2LevelG}
        className="mb-4"
      />
      <p className="text-sm text-muted-foreground">
        {de.summary.roundsPlayed(state.currentRound)}
      </p>

      {state.lastRound ? (
        <section className="mt-16">
          <h2 className="mb-6 text-2xl font-semibold">
            {de.summary.lastRound(state.lastRound.roundNumber)}
          </h2>
          <StatsPanel
            round={state.lastRound}
            seatId={seatId}
            totalEmissionsG={state.totalEmissionsG}
            maxCo2LevelG={state.maxCo2LevelG}
            budget={false}
          />
        </section>
      ) : null}

      <div className="mt-16">
        <Button variant="outline" onClick={() => void navigate({ to: "/join" })}>
          {de.summary.home}
        </Button>
      </div>
    </Screen>
  );
}
