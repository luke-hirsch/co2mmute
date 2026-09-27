import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { scales, type Scale } from "@/lib/game/scale";

/**
 * "pro Person" / "ganze Klasse" — the switch that decides which of a figure's
 * two scales is on screen (Lukas, 2026-09-27).
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
export function ScaleSwitch({
  value,
  onChange,
  /** Unique per instance: two switches on one screen must not share a name. */
  name,
  className,
}: {
  value: Scale;
  onChange: (scale: Scale) => void;
  name: string;
  className?: string;
}) {
  return (
    <fieldset className={cn("inline-block", className)}>
      <legend className="sr-only">{de.numbers.scaleLegend}</legend>
      <div className="flex rounded-full border border-border p-0.5">
        {scales.map((scale) => (
          <label
            key={scale}
            className={cn(
              "cursor-pointer rounded-full px-3 py-1 text-sm transition-colors",
              "focus-within:outline focus-within:outline-2 focus-within:outline-offset-2",
              "focus-within:outline-primary",
              scale === value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <input
              type="radio"
              name={name}
              value={scale}
              checked={scale === value}
              onChange={() => onChange(scale)}
              className="sr-only"
            />
            {de.numbers[scale]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
