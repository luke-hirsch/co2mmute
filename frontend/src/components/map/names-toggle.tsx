import { useState } from "react";

import { de } from "@/lib/de";
import { useBigScreen } from "@/lib/use-big-screen";

/**
 * Whether the names on the map are shown. Until the viewer chooses it follows
 * the screen: shown on a big one, hidden on a phone, where they cover the map.
 * Not remembered across visits.
 */
export function useNamesShown(): [boolean, (shown: boolean) => void] {
  const big = useBigScreen();
  const [chosen, setChosen] = useState<boolean | null>(null);
  return [chosen ?? big, setChosen];
}

/** The switch under a map that shows or hides its names. */
export function NamesToggle({
  shown,
  onChange,
}: {
  shown: boolean;
  onChange: (shown: boolean) => void;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
      <input
        type="checkbox"
        role="switch"
        checked={shown}
        onChange={(event) => onChange(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className="relative h-5 w-9 rounded-full border border-border bg-card transition-colors peer-checked:bg-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary after:absolute after:top-0.5 after:left-0.5 after:size-3.5 after:rounded-full after:bg-foreground after:transition-transform peer-checked:after:translate-x-4 peer-checked:after:bg-primary-foreground"
      />
      {de.map.names}
    </label>
  );
}
