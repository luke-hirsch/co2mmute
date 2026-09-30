import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The editor's sidebar kit.
 *
 * Seven panels wrote the same panel out seven times —
 * `bg-subtle dark:bg-darksubtle rounded-lg p-4 border border-subtle
 * dark:border-darksubtle space-y-3` — and the same dense input eleven times, and
 * the same `text-xs text-mutedtext dark:text-darkmutedtext` label about forty.
 * Repetition on that scale is where drift comes from: the panels had already
 * split into two surfaces (`bg-subtle` and `bg-body`) with nothing saying which
 * meant what, and the version tab bar reached for `bg-darkaccent` and
 * `dark:bg-darkbg`, **neither of which is a token** — so its selected tab had no
 * background at all in dark mode.
 *
 * So the four shapes are written once, in the semantic names the rest of the SPA
 * uses. The panel is a card, its controls sit one step denser than the app's
 * default because a sidebar beside a canvas is not a form page, and the only
 * colour any of them carries is the accent on a note that has to be read.
 */

/**
 * One panel in the sidebar.
 *
 * `attention` is for the two panels that are a mode rather than a view — a line
 * being drawn, a version being built. They used to be `border-amber-300
 * dark:border-amber-700`; the accent is that colour and it is what the rulebook
 * spends on "this is live, finish it or cancel it".
 */
export function EditorPanel({
  title,
  action,
  attention = false,
  className,
  children,
}: {
  title?: ReactNode;
  action?: ReactNode;
  attention?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border bg-card p-4 text-card-foreground",
        attention && "border-destructive",
        className,
      )}
    >
      {title ? (
        <header className="mb-3 flex items-center justify-between gap-2">
          <h2 className="font-semibold">{title}</h2>
          {action}
        </header>
      ) : null}
      <div className="space-y-3">{children}</div>
    </section>
  );
}

/** A labelled control. The value on the right is for a slider or a number. */
export function EditorField({
  label,
  value,
  children,
}: {
  label: ReactNode;
  value?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 flex justify-between gap-2 text-xs text-muted-foreground">
        <span>{label}</span>
        {value !== undefined ? (
          <span className="font-mono">{value}</span>
        ) : null}
      </label>
      {children}
    </div>
  );
}

/** A read-only fact: what a label sits above when there is nothing to type in. */
export function EditorFact({
  label,
  children,
}: {
  label: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="mt-0.5 text-sm">{children}</div>
    </div>
  );
}

/**
 * A line of small print under a control.
 *
 * `tone="attention"` is a refusal or a warning and is the accent — there is no
 * red in this palette and no green either, so a failure and a hint differ by
 * weight of colour, not by hue. A *success* ("Gespeichert.") is deliberately
 * `muted`: the panels used to answer a save with `text-green-600`, which was the
 * bike line's hex, and the rulebook dropped the signal ramps for exactly that
 * reason.
 */
export function EditorNote({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "attention";
  children: ReactNode;
}) {
  return (
    <p
      className={cn(
        "text-xs",
        tone === "attention" ? "font-medium text-destructive" : "text-muted-foreground",
      )}
    >
      {children}
    </p>
  );
}

/**
 * The dense input the sidebar uses everywhere.
 *
 * A className rather than a component, because these are plain `<input>`s with
 * `type="number"`, `type="range"` and `type="text"` between them and `ui/input`
 * is sized for a form page (`h-10`, `text-base`). Passing this to `Input` would
 * work too; it is spelled out so a `<textarea>` and a `<select>` can share it.
 */
export const editorControl =
  "w-full rounded-md border border-input bg-transparent px-2 py-1.5 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

/** The same, for the number boxes that sit at the end of a properties row. */
export const editorControlNarrow = cn(editorControl, "w-16 text-xs");
