import { Button } from "@/components/ui/button";
import { de } from "@/lib/de";
import type { MapLayout } from "@/lib/game/map-layout";

/**
 * Map above or map beside, for the screens that have a map and a list (S24).
 *
 * Drawn from `lg` up only. Below that there is one column and nothing to choose,
 * and a switch that does nothing is worse than none. It is not drawn *for* a
 * beamer either — it is how the person at one turns the side-by-side off,
 * because Tailwind cannot tell a projector from a monitor.
 */
export function MapLayoutToggle({
  layout,
  onChange,
}: {
  layout: MapLayout;
  onChange: (layout: MapLayout) => void;
}) {
  return (
    <div
      role="group"
      aria-label={de.mapLayout.label}
      className="hidden items-center justify-end gap-2 lg:flex"
    >
      <span className="text-sm text-muted-foreground">{de.mapLayout.label}</span>
      {(["below", "beside"] as const).map((value) => (
        <Button
          key={value}
          size="sm"
          variant={layout === value ? "default" : "outline"}
          aria-pressed={layout === value}
          onClick={() => onChange(value)}
        >
          {de.mapLayout[value]}
        </Button>
      ))}
    </div>
  );
}
