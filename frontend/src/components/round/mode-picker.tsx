import { de } from "@/lib/de";
import { modeOrder, modeStyle } from "@/components/metro/mode";
import { cn } from "@/lib/utils";
import type { TransportMode } from "@/types/routeTypes";

/**
 * The four lines, as the choice a passenger makes.
 *
 * Drawn as lines rather than buttons with icons: each option carries its mode's
 * stroke — car solid, bike dashed, walk dotted — which is the one thing that
 * tells them apart at a glance, and keeps telling them apart for a colour-blind
 * reader (`.claude/design/rulebook.md` §5).
 *
 * A radiogroup, not four buttons: it is one choice out of four, and arrow keys
 * should move through it.
 */
export function ModePicker({
  value,
  onPick,
  disabled = false,
  className,
}: {
  value: TransportMode | null;
  onPick: (mode: TransportMode) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={de.round.pickMode}
      className={cn("grid grid-cols-2 gap-2 sm:grid-cols-4", className)}
    >
      {modeOrder.map((mode) => {
        const style = modeStyle[mode];
        const selected = value === mode;
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onPick(mode)}
            className={cn(
              "flex flex-col items-start gap-2 rounded-lg border px-3 py-3 text-left text-sm transition-colors",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              "disabled:cursor-not-allowed disabled:opacity-50",
              selected
                ? "border-foreground bg-muted font-medium"
                : "border-border hover:border-strong dark:hover:border-darkstrong",
            )}
          >
            {/* The line itself, at the width it is drawn everywhere else. */}
            <span
              aria-hidden
              className={cn(
                "block h-0 w-full border-t-[5px]",
                style.border,
                style.stroke,
              )}
            />
            <span>{de.modes[mode]}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * The alternatives under a chosen mode — fastest, shortest, greenest for the
 * car; fastest, fewest changes, no bus for PT.
 *
 * Deliberately a quiet row rather than a second menu. The old screen made this
 * a required step between picking a mode and seeing a route, which is two
 * decisions for one intention; here the default is already computed and this is
 * for the people who want to change it.
 */
export function OptimizationRow<T extends string>({
  options,
  value,
  onPick,
  disabled = false,
}: {
  options: Record<T, string>;
  value: T;
  onPick: (option: T) => void;
  disabled?: boolean;
}) {
  const entries = Object.entries(options) as [T, string][];

  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
      <span className="mr-1 text-xs text-muted-foreground">
        {de.round.otherRoute}
      </span>
      {entries.map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          disabled={disabled}
          onClick={() => onPick(key)}
          className={cn(
            "rounded-full px-3 py-1 text-xs transition-colors",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            "disabled:cursor-not-allowed disabled:opacity-50",
            value === key
              ? "border border-foreground font-medium"
              : "border border-transparent text-muted-foreground hover:border-border",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
