import { useState } from "react";

import type { VoteOption } from "@/lib/game/events";

/**
 * Which option's change the stage's map is showing, and the toggle for it.
 *
 * Looked up rather than trusted: a ballot that is redrawn after a tie may no
 * longer hold the option that was toggled.
 */
export function useShownChange(options: VoteOption[]) {
  const [shownId, setShownId] = useState<number | null>(null);
  const shown = options.find((option) => option.id === shownId) ?? null;
  const toggle = (id: number) =>
    setShownId((current) => (current === id ? null : id));
  return { shown, toggle };
}
