import { de, type TransportMode } from "@/lib/de";
import { cn } from "@/lib/utils";
import { modeOrder, modeStyle } from "./mode";

/**
 * A short piece of line in a mode's colour. The same stroke the landing page
 * uses in its legend: a top border rather than a filled box, so a dotted line
 * reads as dotted.
 */
export function LineSwatch({
  mode,
  className,
}: {
  mode: TransportMode;
  className?: string;
}) {
  const style = modeStyle[mode];
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-0 w-6 shrink-0 border-t-[5px]",
        style.border,
        style.dotted && "border-dotted",
        className,
      )}
    />
  );
}

/** Swatch plus name. Use wherever a mode is named in running text or a list. */
export function ModeLabel({
  mode,
  className,
}: {
  mode: TransportMode;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LineSwatch mode={mode} />
      {de.modes[mode]}
    </span>
  );
}

/**
 * A mode as a compact chip — for agent cards and stats rows, where the name
 * sits next to numbers and needs an outline to hold its own.
 */
export function ModeBadge({
  mode,
  className,
}: {
  mode: TransportMode;
  className?: string;
}) {
  const style = modeStyle[mode];
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full border-2 py-1 pr-3 pl-2.5 text-xs font-medium",
        style.border,
        style.dotted && "border-dotted",
        className,
      )}
    >
      <span aria-hidden className={cn("size-2 rounded-full", style.bg)} />
      {de.modes[mode]}
    </span>
  );
}

/** All four lines with their names — the key to any screen that colours by mode. */
export function LineLegend({ className }: { className?: string }) {
  return (
    <ul className={cn("flex flex-wrap gap-x-6 gap-y-2", className)}>
      {modeOrder.map((mode) => (
        <li key={mode} className="flex items-center gap-2.5 text-sm">
          <LineSwatch mode={mode} />
          <span className="text-muted-foreground">{de.modes[mode]}</span>
        </li>
      ))}
    </ul>
  );
}
