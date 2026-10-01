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
 * `change_img_url` is a media path from `_get_delta_img_url`, and it is the part
 * that actually explains the change: the map with what it touches highlighted.
 * It is optional — a version without one is normal — so the card stands up
 * without it. Where the card is read-only (the discussion) the picture sits in
 * the card, as it always did. On the ballot, since S24, the card is handed a
 * toggle instead and the picture goes to the stage's map (`VoteStage`); **the
 * toggle exists only when an image is stored.** It is used as sent: the path is
 * relative and the SPA is served from the same origin as `/media`.
 */
export function MapChangeCard({
  option,
  changeShown = false,
  onToggleChange,
  children,
  className,
}: {
  option: VoteOption;
  /** Whether the stage is showing this option's change picture right now. */
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

      {option.change_img_url && !onToggleChange ? (
        <img
          src={option.change_img_url}
          alt=""
          loading="lazy"
          className="w-full rounded-md border border-border bg-subtle object-contain dark:bg-darksubtle"
        />
      ) : null}

      {option.change_img_url && onToggleChange ? (
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
