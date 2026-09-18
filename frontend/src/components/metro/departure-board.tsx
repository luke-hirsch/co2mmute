import type { ReactNode } from "react";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * The dark amber-on-black panel from the landing page, carried into the app.
 *
 * It is where codes live: the game id someone types after scanning a QR code,
 * and the six-character seat code from 1.7 that moves a player to another
 * device. Both are read off a projector at the front of a room, which is why
 * they are set in mono at a size you can see from the back, and why this panel
 * stays dark in both themes — it is a display, not a surface.
 */
export function DepartureBoard({
  label,
  footnote,
  children,
  className,
}: {
  label: string;
  footnote?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl bg-darkbody p-5 text-brandaccent shadow-[inset_0_0_0_1px_rgb(255_255_255/0.08)] dark:bg-black",
        className,
      )}
    >
      <p className="font-mono text-xs tracking-[0.2em] uppercase opacity-80">
        {label}
      </p>
      <div className="mt-3">{children}</div>
      {footnote ? (
        <p className="mt-3 border-t border-white/10 pt-3 text-xs text-white/50">
          {footnote}
        </p>
      ) : null}
    </div>
  );
}

/**
 * A code the reader types in. Uppercased by the browser so a phone keyboard's
 * lower case still looks right; the backend uppercases too.
 */
export function CodeInput({
  value,
  onValueChange,
  maxLength = 6,
  className,
  ...props
}: Omit<React.ComponentProps<"input">, "onChange" | "value"> & {
  value: string;
  onValueChange: (value: string) => void;
  maxLength?: number;
}) {
  return (
    <input
      {...props}
      value={value}
      onChange={(event) => onValueChange(event.target.value.toUpperCase())}
      maxLength={maxLength}
      autoCapitalize="characters"
      autoCorrect="off"
      spellCheck={false}
      placeholder={de.code.placeholder}
      className={cn(
        "w-full rounded-md border border-white/15 bg-white/5 px-4 py-3 font-mono text-xl tracking-[0.3em] text-brandaccent uppercase outline-none",
        "placeholder:text-brandaccent/30 focus-visible:border-brandaccent/60 focus-visible:ring-2 focus-visible:ring-brandaccent/30",
        className,
      )}
    />
  );
}

/** A code being shown rather than typed — the host's screen, the projector. */
export function CodeDisplay({
  code,
  className,
}: {
  code: string;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-mono text-3xl tracking-[0.3em] break-all text-brandaccent uppercase sm:text-4xl",
        className,
      )}
    >
      {code}
    </p>
  );
}
