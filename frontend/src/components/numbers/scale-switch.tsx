import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { scales, type Scale } from "@/lib/game/scale";

/**
 * "pro Person" / "alle Pendler" — the switch that decides which of a figure's
 * two scales is on screen (Lukas, 2026-09-27).
 *
 * The wide label said "ganze Klasse" until 2026-09-29, which was wrong on the
 * merits and not only in tone: the sum over every Gruppe is
 * `district_commuters`, a property of the map, and it does not shrink when half
 * the class is away.
 *
 * Every kg and euro in this game exists twice: once multiplied by
 * `people_per_agent`, which is what the CO₂ budget is spent out of, and once
 * divided back down to one commuter making one commute, which is the only figure
 * a student can hold against their own morning. Showing both at once doubles the
 * height of every table; showing only one hides the factor. A switch teaches it
 * instead — you flip it and watch a commute become a district.
 *
 * Two radio inputs rather than buttons, because that is what this is: one choice
 * out of two, and a keyboard and a screen reader already know how to work it.
 * The chrome is drawn on the labels, so nothing is reimplemented.
 */
export function ScaleSwitch<Extra extends string = never>({
  value,
  onChange,
  /** Unique per instance: two switches on one screen must not share a name. */
  name,
  className,
  extra,
}: {
  // Inferred from `extra` alone, so a two-way switch stays a `Scale` one.
  value: Scale | NoInfer<Extra>;
  onChange: (value: Scale | NoInfer<Extra>) => void;
  name: string;
  className?: string;
  /**
   * A third option after the two scales, where a screen has one: "Meine
   * Gruppen" on the end screen of a game that dealt Pendlertypen. Not a scale
   * but another reading of the same game, and the group asked for it here,
   * on the switch the debrief already uses.
   */
  extra?: { value: Extra; label: string };
}) {
  const options: { value: Scale | Extra; label: string }[] = [
    ...scales.map((scale) => ({ value: scale, label: de.numbers[scale] })),
    ...(extra ? [extra] : []),
  ];
  return (
    <fieldset className={cn("inline-block", className)}>
      <legend className="sr-only">{de.numbers.scaleLegend}</legend>
      <div className="flex rounded-full border border-border p-0.5">
        {options.map((option) => (
          <label
            key={option.value}
            className={cn(
              "cursor-pointer rounded-full px-3 py-1 text-sm transition-colors",
              "focus-within:outline focus-within:outline-2 focus-within:outline-offset-2",
              "focus-within:outline-primary",
              option.value === value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
