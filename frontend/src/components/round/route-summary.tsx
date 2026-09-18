import { de } from "@/lib/de";
import { transferCount } from "@/lib/game/round-draft";
import { cn } from "@/lib/utils";
import type { AgentRoute } from "@/types/routeTypes";

/**
 * What a found route costs its passenger: how long, how far, how often they
 * change. CO₂ is deliberately absent — the simulation computes it after the
 * round, and a number here would be a second, worse answer to the same
 * question.
 *
 * Mono for the figures, per the rulebook: numerals are one of the three things
 * mono is reserved for.
 */
export function RouteSummary({
  route,
  className,
}: {
  route: AgentRoute;
  className?: string;
}) {
  const transfers = transferCount(route);

  return (
    <dl className={cn("flex flex-wrap gap-x-6 gap-y-1 text-sm", className)}>
      <Figure value={de.round.duration(route.estimatedTimeMin)} />
      <Figure value={de.round.distance(route.totalDistanceM)} />
      {route.transportMode === "public" && transfers > 0 ? (
        <Figure value={de.round.transfers(transfers)} />
      ) : null}
    </dl>
  );
}

function Figure({ value }: { value: string }) {
  return <dd className="font-mono tabular-nums text-muted-foreground">{value}</dd>;
}
