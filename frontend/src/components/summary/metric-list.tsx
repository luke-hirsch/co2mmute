import { ChevronDown } from "lucide-react";

import { LineSwatch } from "@/components/metro/line";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { co2Unit, type Co2Unit, type Scale } from "@/lib/game/scale";
import { orderBy, playerValue, roundValue, type SummaryMetric } from "@/lib/game/summary";
import type { SummaryPlayer } from "@/lib/queries/summary";

/** Heading per metric, and how a figure in that column is written. */
const metrics: Record<
  SummaryMetric,
  { title: string; format: (value: number, unit: Co2Unit) => string }
> = {
  // The unit is picked once for the whole column (`lib/game/scale.ts`): every
  // figure in a list is read against the one above it, and a list that says
  // "0 g" over "4.794 kg" makes the reader convert units to see which is bigger.
  co2: { title: de.summary.cleanest, format: (g, unit) => de.between.co2Figure(g, unit) },
  cost: { title: de.summary.cheapest, format: (eur) => de.between.eur(eur) },
  time: { title: de.summary.fastest, format: (min) => de.round.duration(min) },
};

/**
 * One of the three lists: everybody who played, ordered by one metric.
 *
 * **Nothing is numbered and nobody is first.** The order carries the finding
 * and that is all it is allowed to do — the research group's position is that
 * the game has no winner, or that who won is what the class talks about now.
 * A "1." in front of the top name would settle that argument on the screen's
 * authority, which is exactly what it must not do.
 *
 * Rendered three times side by side, so a reader can follow one name across
 * all three and watch it move from the top to the bottom. That is the whole
 * argument: the three orders disagree, because less CO₂ costs time.
 *
 * **The order follows the scale the reader chose, and the default is per
 * commute.** It has to be: the three totals are sums over agent-trips and this
 * list contains the people who left, so ranked on the sums whoever played least
 * comes out cleanest, cheapest *and* fastest. A leaver is marked, because that is
 * the one case where the class-scale order says something true that reads as a
 * ranking.
 *
 * Expanding a name shows that list's own metric round by round, plus what they
 * travelled with — `<details>` rather than an accordion component, because the
 * behaviour is native, needs no state and no dependency, and keyboard and
 * screen readers already know it. In the cost list it also shows what was
 * actually paid, which is where the subsidy is legible.
 */
export function MetricList({
  players,
  metric,
  scale,
  seatId,
}: {
  players: readonly SummaryPlayer[];
  metric: SummaryMetric;
  scale: Scale;
  /** This device's seat, marked in every list. Null for the host. */
  seatId: string | null;
}) {
  const { title, format } = metrics[metric];
  const ordered = orderBy(players, metric, scale);
  const unit = co2Unit(players.map((player) => playerValue(player, "co2", scale)));

  return (
    <section>
      <h3 className="border-t border-border pt-4 text-sm font-medium text-muted-foreground">
        {title}
      </h3>

      <ul className="mt-2">
        {ordered.map((player) => {
          const isMe = !!seatId && player.player_id === seatId;

          return (
            <li key={player.player_id} className="border-b border-border/60">
              <details className="group">
                <summary
                  className={cn(
                    "flex cursor-pointer list-none items-baseline gap-3 py-2.5",
                    "[&::-webkit-details-marker]:hidden",
                    isMe && "font-medium",
                  )}
                >
                  <ChevronDown
                    aria-hidden
                    className="size-4 shrink-0 self-center text-muted-foreground transition-transform group-open:rotate-180"
                  />
                  <span className="min-w-0 flex-1 truncate">
                    {player.name}
                    {isMe ? (
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        {de.between.you}
                      </span>
                    ) : null}
                    {player.left ? (
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        {de.summary.leftEarly}
                      </span>
                    ) : null}
                  </span>
                  <span className="shrink-0 font-mono tabular-nums">
                    {format(playerValue(player, metric, scale), unit)}
                  </span>
                </summary>

                <div className="pb-4 pl-7 text-sm text-muted-foreground">
                  <p className="font-medium">{de.summary.perRound}</p>
                  <dl className="mt-1">
                    {player.rounds.map((round) => (
                      <div
                        key={round.round_number}
                        className="flex items-baseline justify-between gap-3 py-0.5"
                      >
                        <dt>{de.summary.arcRound(round.round_number)}</dt>
                        <dd className="font-mono tabular-nums">
                          {format(roundValue(round, metric, scale), unit)}
                        </dd>
                      </div>
                    ))}
                  </dl>

                  {/*
                    Only in the cost list, and only per person: "was du zahlst"
                    against "was es kostet" is the subsidy, and it is a figure
                    about one commuter. Multiplied up by the class it stops being
                    a sentence anybody can check.
                  */}
                  {metric === "cost" && scale === "person" ? (
                    <div className="mt-3 flex items-baseline justify-between gap-3">
                      <span>{de.summary.paid}</span>
                      <span className="font-mono tabular-nums">
                        {de.between.eur(player.paid_eur_per_person)}
                      </span>
                    </div>
                  ) : null}

                  {player.modes_used.length > 0 ? (
                    <>
                      <p className="mt-3 font-medium">{de.summary.modes}</p>
                      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                        {player.modes_used.map((mode) => (
                          <li key={mode} className="flex items-center gap-2">
                            {/* The swatch carries the mode's own pattern —
                                solid, dashed, dotted — so the four modes stay
                                apart without relying on hue. */}
                            <LineSwatch mode={mode} />
                            {de.modes[mode]}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </div>
              </details>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
