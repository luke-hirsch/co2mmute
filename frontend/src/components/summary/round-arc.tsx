import { Track, TrackStop } from "@/components/metro/track";
import { de } from "@/lib/de";
import type { ArcStop } from "@/lib/game/summary";

/**
 * What the class emitted, round by round.
 *
 * This is the one chart on the screen, and it answers the question the whole
 * game is played against: did changing the map do anything? The rounds are a
 * sequence, so it is drawn the way every sequence in this interface is drawn —
 * a line with stops on it — rather than as a plot with axes.
 *
 * Decisions worth naming, because charts go wrong in predictable ways:
 *
 * - **One series, one colour.** Every bar is the primary. Colouring the big
 *   ones darker would double-encode length as hue and spend the only free
 *   channel on something the bar already says.
 * - **Every stop is labelled**, which is normally a mistake and is right here:
 *   there are at most a handful of rounds, there is no axis to read a value
 *   off, and no tooltip either — this screen is looked at on a projector and
 *   on phones, where hovering does not exist. The figures *are* the reading.
 * - **The bars are scaled against the biggest round, not the budget.** The job
 *   here is comparing the rounds with each other; the budget is already drawn
 *   once, in the head of the screen, as the bar it belongs on.
 * - **Under two rounds there is no arc.** One bar is not a chart — it is the
 *   headline figure, and the head of the screen is already showing it.
 */
export function RoundArc({ stops }: { stops: ArcStop[] }) {
  if (stops.length < 2) return null;

  const peak = Math.max(...stops.map((stop) => stop.co2Kg));

  return (
    <section>
      <h2 className="text-2xl font-semibold">{de.summary.arcTitle}</h2>
      <p className="mt-4 max-w-(--measure-body) text-muted-foreground">
        {de.summary.arcLead}
      </p>

      <Track className="mt-10">
        {stops.map((stop, index) => (
          <TrackStop
            key={stop.roundNumber}
            // The last round is the one the game ended on, so it is the filled
            // stop — the same language the round screens speak.
            state={index === stops.length - 1 ? "current" : "done"}
            title={
              <span className="flex items-baseline justify-between gap-4">
                <span>{de.summary.arcRound(stop.roundNumber)}</span>
                <span className="font-mono tabular-nums">
                  {de.summary.kgExact(stop.co2Kg)}
                </span>
              </span>
            }
          >
            <div
              className="h-1.5 rounded-full bg-primary"
              style={{
                width: `${peak > 0 ? Math.max((stop.co2Kg / peak) * 100, 2) : 0}%`,
              }}
            />
          </TrackStop>
        ))}
      </Track>
    </section>
  );
}
