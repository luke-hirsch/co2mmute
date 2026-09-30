import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The page frame every SPA screen sits in.
 *
 * It exists so the two rules that are easiest to forget are written once: the
 * vertical rhythm (`py-20 lg:py-28`, never `py-12`) and a side gutter that
 * survives a 390px phone. `narrow` is for the screens that are a single column
 * of text and one control — join, lobby, the revoked notice — where a full
 * content width would leave the form floating in the middle of nothing.
 *
 * `wide` is the opposite case and there is exactly one of it: a screen whose
 * subject is **a drawing**. The map detail page puts a graph beside a panel, and
 * a graph capped at a text measure is a graph you cannot read. It is a width,
 * not a licence — the rhythm and the gutter still apply, and body text on such
 * a screen still caps itself with `max-w-(--measure-body)`.
 */
export function Screen({
  children,
  narrow = false,
  wide = false,
  className,
}: {
  children: ReactNode;
  narrow?: boolean;
  wide?: boolean;
  className?: string;
}) {
  return (
    <main
      className={cn(
        "min-h-dvh bg-background px-4 py-20 text-foreground sm:px-6 lg:py-28",
        className,
      )}
    >
      <div
        className={cn(
          "mx-auto w-full",
          narrow ? "max-w-xl" : wide ? "max-w-7xl" : "max-w-5xl",
        )}
      >
        {children}
      </div>
    </main>
  );
}

/**
 * A screen heading and its lead.
 *
 * Display sizes step *down* to weight 500 — large type carries less weight
 * better, and nothing in this codebase goes above 600. `hyphens-auto` is here
 * for the same reason the legal pages have it: German compounds do not fit a
 * 390px line otherwise.
 */
export function ScreenHeading({
  title,
  lead,
  className,
}: {
  title: ReactNode;
  lead?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("mb-10", className)}>
      <h1 className="text-3xl font-medium hyphens-auto sm:text-4xl">{title}</h1>
      {lead ? (
        <p className="mt-4 max-w-(--measure-lead) text-muted-foreground">
          {lead}
        </p>
      ) : null}
    </header>
  );
}
