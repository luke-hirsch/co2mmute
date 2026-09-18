import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";
import { playingSeats } from "@/lib/game/game-state";

/**
 * After the turn is sent: what is still being waited for.
 *
 * That this seat has submitted is not stored here or anywhere else on the
 * client — it is `seat.status === "waiting"` in the roster. Which is why this
 * panel is still correct after a reload, after a reconnect, and when the seat
 * was submitted from another device (F4, R-11).
 *
 * Names appear here because the roster is exactly the list of who is in the
 * room, and the players can see each other. They must not reach a log, a toast
 * or an error string (CLAUDE.md → players are minors).
 */
export function SubmittedPanel() {
  const { state } = useGame();

  const outstanding = playingSeats(state).filter(
    (seat) => seat.status !== "waiting",
  );

  return (
    <section className="border-t border-border pt-8">
      <h2 className="text-2xl font-semibold">{de.round.submitted}</h2>
      <p className="mt-4 max-w-(--measure-body) text-muted-foreground">
        {de.round.submittedBody}
      </p>

      {state.simulation ? (
        <SimulationLine
          status={state.simulation.status}
          percent={state.simulation.percent}
        />
      ) : outstanding.length > 0 ? (
        <div className="mt-8">
          <h3 className="text-sm text-muted-foreground">{de.round.waitingFor}</h3>
          <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
            {outstanding.map((seat) => (
              <li
                key={seat.player_id}
                className="rounded-full border border-border px-3 py-1 text-sm"
              >
                {seat.name}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/**
 * `simulation.progress` — one of the seven events nothing read for months.
 *
 * The bar runs in the primary: this is progress, not attention. A failed run is
 * the accent, like every other thing that wants looking at.
 */
function SimulationLine({
  status,
  percent,
}: {
  status: "starting" | "running" | "failed";
  percent: number;
}) {
  if (status === "failed") {
    return (
      <p className="mt-8 border-l-[3px] border-brandaccent pl-4 max-w-(--measure-body)">
        {de.round.simulationFailed}
      </p>
    );
  }

  return (
    <div className="mt-8">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm">{de.round.simulation}</span>
        <span className="font-mono text-sm tabular-nums text-muted-foreground">
          {Math.round(percent)}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
        aria-label={de.round.simulation}
        className="mt-2 h-2 w-full overflow-hidden rounded-full bg-subtle dark:bg-darksubtle"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
        />
      </div>
    </div>
  );
}
