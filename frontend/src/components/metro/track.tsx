import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A line with stations on it. This is the landing page's idea carried into the
 * app: anything that is a sequence — the rounds of a game, the steps of a turn,
 * the phases between rounds — is drawn as a line and its stops, not as a
 * progress bar or a row of numbered circles.
 *
 * The landing page's own .metro-* CSS is not reused here. That geometry exists
 * to fan four lines out into columns across a whole page; a screen needs one
 * line and its stops, which is cheaper to draw directly.
 */

type StopState = "done" | "current" | "todo";

export function Track({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <ol className={cn("relative flex flex-col gap-7 pl-9", className)}>
      {/* The line itself. Insets top and bottom so it starts and ends at the
          first and last marker rather than running past them. */}
      <span
        aria-hidden
        className="absolute top-3 bottom-3 left-[9px] w-0 border-l-[5px] border-mode-pt"
      />
      {children}
    </ol>
  );
}

export function TrackStop({
  state = "todo",
  title,
  children,
  className,
}: {
  state?: StopState;
  title: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <li className={cn("relative", className)}>
      <span
        aria-hidden
        className={cn(
          "absolute top-[0.5lh] left-[-2.25rem] -translate-y-1/2 rounded-full border-[3px] transition-colors",
          // The current stop is the filled one, so the eye lands on it first.
          state === "current"
            ? "size-[22px] border-mode-pt bg-mode-pt"
            : "size-[18px] border-foreground bg-background",
          state === "done" && "border-mode-pt",
        )}
      />
      <p
        className={cn(
          "font-medium",
          state === "todo" && "text-muted-foreground",
        )}
      >
        {title}
      </p>
      {children ? (
        <div className="mt-1.5 max-w-(--measure-body) text-sm text-muted-foreground">
          {children}
        </div>
      ) : null}
    </li>
  );
}
