import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Co2Bar } from "@/components/metro/co2-bar";
import { MetricList } from "@/components/summary/metric-list";
import { RoundArc } from "@/components/summary/round-arc";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { Skeleton } from "@/components/ui/skeleton";
import { classArc, summaryMetrics } from "@/lib/game/summary";
import { de } from "@/lib/de";
import { displayKg, kgToGrams } from "@/lib/co2";
import { useGame } from "@/components/game/game-context";
import { useGameSummary } from "@/lib/queries/summary";

/**
 * The game is over (E-01 … E-04), and this is the debrief (E-03).
 *
 * **This is the one screen where REST outranks the socket**, and the reason is
 * the backend's: `ws_auth.resolve_player` refuses a socket for a game that has
 * an `ended_at` (4403, "game-ended"). So the moment a player reloads here there
 * is no socket at all, and the reducer holds only what the lobby snapshot could
 * seed — no total, no end reason, and never more than the last round.
 *
 * So `GET api/game/<id>/summary/` is authoritative for everything it carries,
 * and the reducer is the fallback for the instant before it lands (and for the
 * end reason, where the live `game.ended` is the better of the two — the
 * payload recomputes it and gets an idle-ended game wrong).
 *
 * Nothing is invalidated and nothing polls. The game is over: there is no
 * second opinion to reconcile, only one source that arrives slightly late.
 *
 * The names on it are real until anonymisation runs, 24 h after the end (1.3) —
 * deliberately, because the debrief happens in the lesson and the names go
 * after it. They stay on the screen: never a log, a toast or an error string.
 */
export function EndScreen() {
  const navigate = useNavigate();
  const { state, seatId, isHost } = useGame();
  const summary = useGameSummary(state.gameId, !!state.endedAt);

  const endReason = state.endReason ?? summary.data?.end_reason ?? null;
  const players = summary.data?.players ?? [];

  /**
   * The totals come from the payload once it lands, and only fall back to the
   * reducer before that.
   *
   * It is the other way round on every other screen, and this one has to be the
   * exception: `ws_auth.resolve_player` refuses a socket for a game that has
   * ended, so a player who reloads the summary has no socket at all and the
   * lobby snapshot carries no emissions. The reducer's total was then still 0
   * while the lists underneath said 6.222 kg — two numbers on one screen
   * disagreeing, which is worse than either being late.
   */
  const totalG =
    summary.data !== undefined
      ? kgToGrams(summary.data.total_co2_kg)
      : state.totalEmissionsG;
  const budgetG =
    summary.data !== undefined
      ? kgToGrams(summary.data.max_co2_kg)
      : state.maxCo2LevelG;

  return (
    <Screen>
      <ScreenHeading
        title={de.summary.title}
        lead={endReason ? de.summary.reason[endReason] : de.summary.lead}
      />

      <dl className="mb-12 grid gap-8 sm:grid-cols-2">
        <div>
          <dt className="text-sm text-muted-foreground">{de.summary.total}</dt>
          <dd className="mt-1 font-mono text-3xl tabular-nums">
            {de.summary.kg(displayKg(totalG))}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">{de.summary.budget}</dt>
          <dd className="mt-1 font-mono text-3xl tabular-nums">
            {de.summary.kg(displayKg(budgetG))}
          </dd>
        </div>
      </dl>

      <Co2Bar usedG={totalG} maxG={budgetG} className="mb-4" />
      <p className="text-sm text-muted-foreground">
        {/*
          The payload counts *completed* rounds; `currentRound` counts the one
          that was open. They differ whenever the host ends a game mid-round,
          which is a normal way for a lesson to finish — so the reducer's value
          is only the fallback for a reload before the query lands.
        */}
        {de.summary.roundsPlayed(summary.data?.rounds_played ?? state.currentRound)}
      </p>

      <div className="mt-20 space-y-16 lg:mt-28 lg:space-y-20">
        {summary.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : summary.isError ? (
          // The head above still stands, so this is a partial screen rather
          // than a dead end. Nothing of the failure reaches a toast.
          <p className="max-w-(--measure-body) border-l-[3px] border-brandaccent pl-4">
            {de.summary.failed}
          </p>
        ) : players.length === 0 ? (
          // A real answer, not a failure: the host ended the game during
          // round 1, so no round was ever completed.
          <p className="max-w-(--measure-body) text-muted-foreground">
            {de.summary.empty}
          </p>
        ) : (
          <>
            <RoundArc stops={classArc(players)} />

            <section>
              <h2 className="text-2xl font-semibold">{de.summary.listsTitle}</h2>

              {/* Three orders of the same people, side by side on a wide
                  screen and stacked on a phone. Side by side is what makes
                  the point readable: one name near the top of one list and
                  the bottom of another, without a word being said about it. */}
              <div className="mt-8 grid gap-x-10 gap-y-10 lg:grid-cols-3">
                {summaryMetrics.map((metric) => (
                  <MetricList
                    key={metric}
                    players={players}
                    metric={metric}
                    seatId={seatId}
                  />
                ))}
              </div>

              <p className="mt-10 max-w-(--measure-body) text-muted-foreground">
                {de.summary.noWinner}
              </p>
            </section>
          </>
        )}
      </div>

      <div className="mt-20">
        {isHost ? (
          // Out of the SPA: a host starts a game on the Django page, which is
          // where "new game" has to land.
          <Button variant="outline" asChild>
            <a href="/game/create/">{de.summary.hostHome}</a>
          </Button>
        ) : (
          <Button variant="outline" onClick={() => void navigate({ to: "/join" })}>
            {de.summary.home}
          </Button>
        )}
      </div>
    </Screen>
  );
}
