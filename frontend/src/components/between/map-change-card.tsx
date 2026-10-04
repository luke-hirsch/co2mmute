import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import type { VoteOption } from "@/lib/game/events";

/**
 * One thing the class can vote onto the map.
 *
 * `poll_text` and `name` are the map maker's own German (they come out of
 * `MapVersion`), so nothing here rewrites them — the only word this component
 * contributes is what `is_rollback` means, and it says it in words rather than
 * printing the English `rollback` badge the old screen did.
 *
 * **What the option changes is shown on the stage's map**, behind the toggle:
 * the stage asks for the option's graph and draws its difference from the map
 * the game is on (`lib/map/version-diff.ts`). Until the version comparison that
 * was a PNG somebody had to draw per change (`change_img`), the toggle existed
 * only where one was stored, and the shipped map had none — so the class voted
 * on the poll text alone. Now every option has the toggle, computed from the
 * data, and the picture is read by nothing in the game.
 */
export function MapChangeCard({
  option,
  changeShown = false,
  onToggleChange,
  children,
  className,
}: {
  option: VoteOption;
  /** Whether the stage's map is showing this option's change right now. */
  changeShown?: boolean;
  onToggleChange?: () => void;
  /** The control that acts on this option, when there is one. */
  children?: ReactNode;
  className?: string;
}) {
  return (
    <article
      className={cn(
        "flex flex-col gap-4 border-t-[3px] border-primary pt-5",
        className,
      )}
    >
      <div>
        <h3 className="text-xl font-medium hyphens-auto">{option.name}</h3>
        {option.is_rollback ? (
          <p className="mt-1 font-mono text-xs tracking-[0.12em] text-brandaccent uppercase">
            {de.vote.rollback}
          </p>
        ) : null}
      </div>

      {onToggleChange ? (
        <div>
          <Button
            variant="outline"
            size="sm"
            aria-pressed={changeShown}
            onClick={onToggleChange}
          >
            {changeShown ? de.vote.hideChange : de.vote.showChange}
          </Button>
        </div>
      ) : null}

      <p className="max-w-(--measure-body) text-muted-foreground">
        {option.poll_text}
      </p>

      {children}
    </article>
  );
}
