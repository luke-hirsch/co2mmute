import { useState } from "react";

import { Co2Bar } from "@/components/metro/co2-bar";
import { NumbersExplainerDialog } from "@/components/numbers/numbers-explainer";
import { ScaleSwitch } from "@/components/numbers/scale-switch";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { co2Unit, type Scale } from "@/lib/game/scale";
import type { RoundResult } from "@/lib/game/game-state";

/**
 * What the last round cost, per player (Z-01).
 *
 * Shared by the player's stats screen and the host's — so the figures are
 * formatted in exactly one place. Nothing is recomputed here: the simulation's
 * arithmetic is the backend's, and **both scales come off the payload** rather
 * than one being divided out of the other. A screen dividing a figure that has
 * already been rounded for display by a thousand is dividing noise.
 *
 * Three things on it were invisible before S4 and are the point of this table:
 *
 * - **which scale a row is on.** Every figure here used to be class scale with
 *   nothing saying so, so a 2 km drive read as 334 kg. The switch flips the two
 *   number columns; the sentence under it names the factor.
 * - **the gap between the rows and the total.** A PT line emits because it runs,
 *   so a round where nobody took the bus still carries its timetable — in the
 *   footer and in no row. Unexplained, that reads as an arithmetic bug.
 * - **what anybody actually paid**, against what the round cost. The difference
 *   is the subsidy, which is the argument the PT fare exists to make.
 *
 * Time never switches: `time_min` is already a mean over the seat's Gruppen,
 * and a sum of travel times is not a quantity anybody has.
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
  const [scale, setScale] = useState<Scale>("person");
  const perPerson = scale === "person";

  const cells = round.playerStats.map((stat) =>
    perPerson ? stat.co2_g_per_person : stat.emissions_g,
  );
  // The rows decide the column's unit; the footer is class scale whatever the
  // switch says, so it carries its own.
  const unit = co2Unit(cells);
  const footUnit = co2Unit([round.emissionsG, round.unriddenCo2G]);

  const people = round.peoplePerAgent || 1;
  const note = perPerson
    ? de.numbers.perPersonNote(people.toLocaleString("de-DE"))
    : de.numbers.classNote(people.toLocaleString("de-DE"));

  const own = seatId
    ? round.playerStats.find((stat) => stat.player_id === seatId)
    : undefined;

  return (
    <section>
      {!round.simulationUsed ? (
        <p className="mb-6 border-l-[3px] border-brandaccent pl-4 max-w-(--measure-body)">
          {de.between.noSimulation}
        </p>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <ScaleSwitch
          value={scale}
          onChange={setScale}
          name={`round-${round.roundNumber}-scale`}
        />
        <NumbersExplainerDialog />
      </div>

      <p className="mb-6 max-w-(--measure-body) text-sm text-muted-foreground">
        {note}
      </p>

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
                    {de.between.co2Figure(
                      perPerson ? stat.co2_g_per_person : stat.emissions_g,
                      unit,
                    )}
                  </td>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {de.between.eur(
                      perPerson ? stat.cost_eur_per_person : stat.cost_eur,
                    )}
                  </td>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {de.round.duration(stat.time_min)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="text-muted-foreground">
            {/*
              Class scale on both rows, whatever the switch says — the budget is
              the class's and is spent in kilograms. The first row is why the
              second is larger than the rows above it.
            */}
            {round.unriddenCo2G > 0 ? (
              <tr>
                <th scope="row" className="pt-3 text-left font-normal">
                  {de.between.unridden}
                </th>
                <td className="pt-3 text-right font-mono tabular-nums">
                  {de.between.co2Figure(round.unriddenCo2G, footUnit)}
                </td>
                <td className="pt-3 text-right font-mono tabular-nums">
                  {de.between.eur(round.unriddenCostEur)}
                </td>
                <td />
              </tr>
            ) : null}
            <tr className="text-foreground">
              <th scope="row" className="pt-3 text-left font-medium">
                {de.between.roundTotal}
                {/* Named only where it differs from the rows above it. In class
                    scale the rows already add up to this line, and saying it
                    twice would suggest they do not. */}
                {perPerson ? (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {de.between.everyone}
                  </span>
                ) : null}
              </th>
              <td className="pt-3 text-right font-mono tabular-nums">
                {de.between.co2Figure(round.emissionsG, footUnit)}
              </td>
              <td className="pt-3 text-right font-mono tabular-nums">
                {de.between.eur(round.costEur)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      {round.unriddenCo2G > 0 ? (
        <p className="mt-4 max-w-(--measure-body) text-sm text-muted-foreground">
          {de.between.unriddenHint}
        </p>
      ) : null}

      {/*
        What it cost against what was paid — the subsidy, in one line. Personal
        where this device holds a seat, the class's on the projector.
      */}
      {round.paidEur > 0 ? (
        <p className="mt-4 max-w-(--measure-body) text-sm text-muted-foreground">
          {own
            ? de.between.paidYou(
                de.between.eur(own.paid_eur_per_person),
                de.between.eur(own.cost_eur_per_person),
              )
            : de.between.paidSelf(
                de.between.eur(round.paidEur),
                // The commutes, not the round: the timetable nobody rode is
                // already named on its own line, and leaving it in here would
                // put it inside the gap and make it read as subsidy.
                de.between.eur(round.costEur - round.unriddenCostEur),
              )}
        </p>
      ) : null}

      {budget ? (
        <Co2Bar usedG={totalEmissionsG} maxG={maxCo2LevelG} className="mt-10" />
      ) : null}
    </section>
  );
}
