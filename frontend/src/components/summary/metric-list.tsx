import { ChevronDown } from "lucide-react";

import { LineSwatch } from "@/components/metro/line";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { orderBy, playerValue, roundValue, type SummaryMetric } from "@/lib/game/summary";
import type { SummaryPlayer } from "@/lib/queries/summary";

/** Heading and formatter per metric. Presentation, so it lives here. */
const metrics: Record<
  SummaryMetric,
  { title: string; format: (value: number) => string }
> = {
  // Kilos, not `between.grams`: every figure in a list is read against the one
  // above it, and a list that says "0 g" over "4.794 kg" makes the reader
  // convert units to see which is bigger.
  co2: { title: de.summary.cleanest, format: (kg) => de.summary.kgExact(kg) },
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
 * Expanding a name shows that list's own metric round by round, plus what they
 * travelled with — `<details>` rather than an accordion component, because the
 * behaviour is native, needs no state and no dependency, and keyboard and
 * screen readers already know it.
 */
export function MetricList({
  players,
  metric,
  seatId,
}: {
  players: readonly SummaryPlayer[];
  metric: SummaryMetric;
  /** This device's seat, marked in every list. Null for the host. */
  seatId: string | null;
}) {
  const { title, format } = metrics[metric];
  const ordered = orderBy(players, metric);

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
                  </span>
                  <span className="shrink-0 font-mono tabular-nums">
                    {format(playerValue(player, metric))}
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
                          {format(roundValue(round, metric))}
                        </dd>
                      </div>
                    ))}
                  </dl>

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
