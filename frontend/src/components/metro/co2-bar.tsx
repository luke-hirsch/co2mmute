import {
  budgetLevel,
  budgetShare,
  displayKg,
  exceededBudget,
} from "@/lib/co2";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

const fill: Record<ReturnType<typeof budgetLevel>, string> = {
  ok: "bg-primary",
  attention: "bg-brandaccent",
};

/**
 * The shared CO2 budget — the thing the whole game is played against.
 *
 * Takes grams, because that is what the websocket sends. See lib/co2.ts for why
 * that matters.
 */
export function Co2Bar({
  usedG,
  maxG,
  className,
}: {
  usedG: number;
  maxG: number;
  className?: string;
}) {
  const share = budgetShare(usedG, maxG);
  const level = budgetLevel(usedG, maxG);
  const over = exceededBudget(usedG, maxG);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium">{de.co2.label}</span>
        <span
          className={cn(
            "font-mono text-sm tabular-nums",
            over ? "font-medium text-foreground" : "text-muted-foreground",
          )}
        >
          {over ? de.co2.exceeded : de.co2.used(displayKg(usedG), displayKg(maxG))}
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={displayKg(maxG)}
        aria-valuenow={displayKg(usedG)}
        aria-label={de.co2.label}
        className="h-2 w-full overflow-hidden rounded-full bg-subtle dark:bg-darksubtle"
      >
        <div
          className={cn("h-full rounded-full transition-[width]", fill[level])}
          style={{ width: `${share * 100}%` }}
        />
      </div>
    </div>
  );
}
