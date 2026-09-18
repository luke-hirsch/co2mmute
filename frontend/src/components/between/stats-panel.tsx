import { Co2Bar } from "@/components/metro/co2-bar";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import type { RoundResult } from "@/lib/game/game-state";

/**
 * What the last round cost, per player (Z-01).
 *
 * Shared by the player's stats screen, the host's, and the end screen — so the
 * figures are formatted in exactly one place. The numbers come straight off
 * `round.completed`; nothing is recomputed here, because the simulation's
 * arithmetic is the backend's and a second opinion on it would only ever be
 * wrong (`people_per_agent`, grams vs. kilos — see `lib/co2.ts`).
 *
 * Names appear because the roster is the room: everybody can see everybody. The
 * line they must never cross is a log, a toast or an error string
 * (CLAUDE.md → players are minors).
 *
 * The table scrolls sideways in its own box rather than pushing the page — four
 * columns of numbers do not fit 390px, and the page body must never scroll
 * horizontally.
 */
export function StatsPanel({
  round,
  seatId,
  totalEmissionsG,
  maxCo2LevelG,
  budget = true,
}: {
  round: RoundResult;
  /** This device's seat, marked in the list. Null for the host. */
  seatId: string | null;
  totalEmissionsG: number;
  maxCo2LevelG: number;
  /**
   * The running budget under the table. Off where the screen already shows it
   * once — the end screen leads with it, and a second bar saying the same thing
   * reads as a second number.
   */
  budget?: boolean;
}) {
  return (
    <section>
      {!round.simulationUsed ? (
        <p className="mb-6 border-l-[3px] border-brandaccent pl-4 max-w-(--measure-body)">
          {de.between.noSimulation}
        </p>
      ) : null}

      {/*
        The four columns fit a 390px phone at this size, and the scroller is
        here for the case they do not — a long name, or a browser with larger
        type. It scrolls inside its own box either way, because the page body
        must never scroll sideways.
      */}
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <table className="w-full min-w-[19rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th scope="col" className="pb-2 font-normal">
                {de.between.player}
              </th>
              <th scope="col" className="pb-2 text-right font-normal">
                {de.between.co2}
              </th>
              <th scope="col" className="pb-2 text-right font-normal">
                {de.between.cost}
              </th>
              <th scope="col" className="pb-2 text-right font-normal">
                {de.between.time}
              </th>
            </tr>
          </thead>
          <tbody>
            {round.playerStats.map((stat) => {
              const isMe = !!seatId && stat.player_id === seatId;
              return (
                <tr
                  key={stat.player_id}
                  className={cn(
                    "border-b border-border/60",
                    isMe && "font-medium",
                  )}
                >
                  <th
                    scope="row"
                    className={cn(
                      "py-2 text-left",
                      // A `th` is bold by default and preflight does not reset
                      // it; 700 is above this codebase's ceiling.
                      isMe ? "font-medium" : "font-normal",
                    )}
                  >
                    {stat.player_name}
                    {isMe ? (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {de.between.you}
                      </span>
                    ) : null}
                  </th>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {de.between.grams(stat.emissions_g)}
                  </td>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {de.between.eur(stat.cost_eur)}
                  </td>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {de.round.duration(stat.time_min)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="pt-3 text-left font-medium">
                {de.between.roundTotal}
              </th>
              <td className="pt-3 text-right font-mono tabular-nums">
                {de.between.grams(round.emissionsG)}
              </td>
              <td className="pt-3 text-right font-mono tabular-nums">
                {de.between.eur(round.costEur)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      {budget ? (
        <Co2Bar usedG={totalEmissionsG} maxG={maxCo2LevelG} className="mt-10" />
      ) : null}
    </section>
  );
}
